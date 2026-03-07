"""DLsite Play CSR viewer."""

import asyncio
import json
import logging
import os
import tempfile
import time
import urllib.parse
import zipfile
from base64 import b64encode, b64decode
from collections.abc import Iterable, Iterator, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from enum import IntEnum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Self
from typing_extensions import deprecated

from aiohttp import ClientResponseError
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization
from lxml import etree

from ..exceptions import DlsiteError
from .models import CSRReflowableToken, CSRToken, PlayFile, ZipTree

if TYPE_CHECKING:
    from .api import PlayAPI


logger = logging.getLogger(__name__)


class _Mode(IntEnum):
    DL_XML = 0
    DL_JPEG = 1
    DL_FACE_XML = 7
    DL_PAGE_XML = 8
    DL_AUTH_KEY = 999


class _RequestType(IntEnum):
    FILE = 0
    AUTH_FIRST = 1


class _ViewMode(IntEnum):
    KOMA = 1
    VERTICAL = 2
    HYBRID = 4


@dataclass(frozen=True)
class _PagePart:
    part_no: str
    scramble: bool


@dataclass(frozen=True)
class _PageInfo:
    page_no: int
    total_part_size: int
    parts: list[_PagePart]
    scramble: list[int]


@dataclass(frozen=True)
class _PreprocessSettings:
    obfuscate_text: bool
    obfuscate_image: bool
    obfuscate_image_key: int | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            data["obfuscateText"], data["obfuscateImage"], data.get("obfuscateImageKey")
        )


class EpubFixedSession(AbstractAsyncContextManager["EpubFixedSession"]):
    """DLsite Play CSR (fixed-layout epub) Viewer Session.

    Args:
        play_api: Parent PlayAPI session.
        ziptree: DLsite Play ZipTree for the work. Must contain an ``epub`` playfile
            entry.
        playfile: PlayFile entry for the epub to open in ``ziptree``.
        workno: DLsite product ID for the epub work (defaults to `ziptree.workno`).
    """

    def __init__(
        self,
        play_api: "PlayAPI",
        ziptree: ZipTree,
        playfile: PlayFile,
        workno: str | None = None,
    ):
        self._play = play_api
        self.ziptree = ziptree
        self.playfile = playfile
        self.workno = workno or ziptree.workno
        if not self.workno:
            raise ValueError("workno must be specified")
        if not self.playfile.is_epub_fixed:
            raise ValueError("Unsupported epub type: {self.playfile.type}")
        self._token: CSRToken | None = None
        self._total_page: int | None = None
        self._start_page: int | None = None
        self._version: str | None = None
        self._scramble_size: tuple[int, int] | None = None
        self._wake_up: int | None = None

    @property
    def page_count(self) -> int:
        return self._total_page if self._total_page is not None else 0

    def __len__(self) -> int:
        return self.page_count

    async def __aenter__(self) -> "EpubFixedSession":
        await self.load()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def load(self) -> None:
        if self._token is None:
            self._token = await self._download_token()
        if (
            self._total_page is None
            or self._start_page is None
            or self._version is None
            or self._scramble_size is None
        ):
            self._wake_up = int(time.time() * 1000 % 1e7)
            params = {
                "mode": _Mode.DL_AUTH_KEY.value,
                "file": "",
                "reqtype": _RequestType.AUTH_FIRST.value,
                "vm": _ViewMode.HYBRID.value,
                "param": self._token.param,
                "time": self._wake_up,
            }
            async with self._play.get(self._token.cgi, params=params) as response:
                response.raise_for_status()

            params["mode"] = _Mode.DL_JPEG.value
            params["file"] = "extend_info.json"
            params["reqtype"] = _RequestType.FILE.value
            async with self._play.get(
                self._token.cgi, params=params, raise_for_status=False
            ) as response:
                # TODO: handle extended info if a work that requires it is found.
                # This request 404's for all works used in testing but we do it to
                # match the viewer auth->face xml request flow
                pass

            params["mode"] = _Mode.DL_FACE_XML.value
            params["file"] = "face.xml"
            params["reqtype"] = _RequestType.FILE.value
            async with self._play.get(self._token.cgi, params=params) as response:
                self._load_face_xml(await response.text())

    def _load_face_xml(self, content: str) -> None:
        root = etree.fromstring(content)
        total_page = root.findtext("TotalPage")
        if total_page is not None:
            self._total_page = int(total_page)
        start_page = root.findtext("StartPage")
        if start_page is not None:
            self._start_page = int(start_page)
        version = root.findtext("Version")
        if version is not None:
            self._version = version
        scramble = root.find("Scramble")
        if scramble is not None:
            width = scramble.findtext("Width")
            height = scramble.findtext("Height")
            if width is not None and height is not None:
                self._scramble_size = (int(width), int(height))

    async def close(self) -> None:
        self._token = None
        self._total_page = None
        self._start_page = None
        self._version = None
        self._scramble_size = None

    async def _download_token(self) -> CSRToken:
        """Return a download token for this work."""
        url = "https://play.dlsite.com/api/v3/csr/token"
        params = {
            "workno": self.workno,
            "hashname": self.playfile.hashname or "",
            "layout": "fixed",
        }
        async with self._play.get(url, params=params) as response:
            data = await response.json()
            return CSRToken.from_json(data["values"])

    async def download_page(
        self,
        index: int,
        dest_dir: str | Path,
        mkdir: bool = False,
        descramble: bool = False,
        force: bool = False,
        **save_kwargs: Any,
    ) -> list[Path]:
        """Download one ebook page to the specified location.

        Args:
            index: Zero-indexed page number to download.
            dest_dir: Destination directory to write the downloaded file.
            mkdir: Create ``dest_dir`` and parent directories if they do not already
                exist.
            force: Overwrite existing destination file if it already exists.
            descramble: Descramble downloaded images (requires optional
                ``dlsite-async[pil]`` dependency packages).
            save_kwargs: Additional arguments to be passed into Pillow ``Image.save()``.
                Only applicable when ``descramble`` is ``True``.

        Returns:
            Downloaded image paths (some pages may consist of multiple images).

        Raises:
            FileExistsError: destination file already exists.
        """
        if self._token is None:
            raise DlsiteError("CSR session has not been loaded")
        page_info = await self._download_page_info(index)
        dest_dir = Path(dest_dir)
        results = []
        for part in page_info.parts:
            index_stem = f"{index:04}"
            part_stem = f"{index_stem}_{part.part_no}"
            if len(page_info.parts) == 1:
                dest = dest_dir / f"{index_stem}.jpg"
            else:
                dest = dest_dir / f"{part_stem}.jpg"
            if mkdir and not dest.parent.exists():
                dest.parent.mkdir(parents=True)
            if not force and dest.exists():
                raise FileExistsError(str(dest))
            params = {
                "mode": _Mode.DL_JPEG.value,
                "file": f"{part_stem}.bin",
                "reqtype": _RequestType.FILE.value,
                "vm": _ViewMode.HYBRID.value,
                "param": self._token.param,
                "time": self._wake_up,
            }
            async with self._play.get(
                self._token.cgi, params=params, timeout=self._play._DL_TIMEOUT
            ) as response:
                with tempfile.NamedTemporaryFile(
                    prefix=dest.stem, suffix=".jpg", dir=dest.parent, delete=False
                ) as temp:
                    try:
                        async for chunk in response.content.iter_chunked(
                            self._play._DL_CHUNK_SIZE
                        ):
                            temp.write(chunk)
                    except Exception:
                        temp.close()
                        os.remove(temp.name)
                        raise
            if descramble and part.scramble and self._scramble_size is not None:
                await asyncio.to_thread(
                    self._descramble,
                    temp.name,
                    self._scramble_size,
                    page_info.scramble,
                    **save_kwargs,
                )
            os.replace(temp.name, dest)
            results.append(dest)
        return results

    async def _download_page_info(self, index: int) -> _PageInfo:
        assert self._token is not None
        assert self._total_page is not None
        assert self._wake_up is not None
        if index >= self._total_page:
            raise ValueError("Invalid page number")
        params = {
            "mode": _Mode.DL_PAGE_XML.value,
            "file": f"{index:04}.xml",
            "reqtype": _RequestType.FILE.value,
            "vm": _ViewMode.HYBRID.value,
            "param": self._token.param,
            "time": self._wake_up,
        }
        async with self._play.get(self._token.cgi, params=params) as response:
            root = etree.fromstring(await response.text())
        page_no = root.findtext("PageNo")
        if page_no is None:
            raise DlsiteError("Unexpected CSR viewer page data")
        total_part_size = root.findtext("TotalPartSize")
        if total_part_size is None:
            raise DlsiteError("Unexpected CSR viewer page data")
        part = root.find("Part")
        if part is None:
            raise DlsiteError("Unexpected CSR viewer page data")
        try:
            parts = [
                _PagePart(
                    part_no=kind.get("No", "0000"),
                    scramble=bool(int(kind.get("scramble", "0"))),
                )
                for kind in part.findall("Kind")
            ]
        except KeyError as e:
            raise DlsiteError("Unexpected CSR viewer page data") from e
        scramble = root.findtext("Scramble")
        return _PageInfo(
            page_no=int(page_no),
            total_part_size=int(total_part_size),
            parts=parts,
            scramble=(
                [int(x.strip()) for x in scramble.split(",")]
                if scramble is not None
                else []
            ),
        )

    def _descramble(
        self,
        path: str | Path,
        scramble_size: tuple[int, int],
        scramble: Sequence[int],
        **save_kwargs: Any,
    ) -> None:
        try:
            from PIL import Image
        except ImportError:
            logger.warn("Image descramble requires installation with dlsite-async[pil]")
            return
        path = Path(path)
        scramble_w, scramble_h = scramble_size
        tile_w, tile_h = (264, 368)
        with Image.open(path) as im:
            tiles = [
                im.crop(
                    (
                        x * tile_w,
                        y * tile_h,
                        (x + 1) * tile_w,
                        (y + 1) * tile_h,
                    )
                )
                for y in range(scramble_w)
                for x in range(scramble_h)
            ]
            new_im = im.copy()
        if len(tiles) < len(scramble):
            raise ValueError("Tile count does not match scramble count")
        for i, src_index in enumerate(scramble):
            tile = tiles[src_index]
            x = i % scramble_w
            y = i // scramble_h
            new_im.paste(tile, (x * tile_w, y * tile_h))
        if path.suffix.lower() in (".jpg", ".jpeg") and "quality" not in save_kwargs:
            save_kwargs["quality"] = "keep"
        new_im.save(path, **save_kwargs)


@deprecated("EpubSession is deprecated, use EpubFixedSession instead.")
class EpubSession(EpubFixedSession):
    pass


class EpubReflowableSession(AbstractAsyncContextManager["EpubReflowableSession"]):
    """DLsite Play CSR-R (reflowable epub) Viewer Session.

    Args:
        play_api: Parent PlayAPI session.
        ziptree: DLsite Play ZipTree for the work. Must contain an ``epub`` playfile
            entry.
        playfile: PlayFile entry for the epub to open in ``ziptree``.
        workno: DLsite product ID for the epub work (defaults to `ziptree.workno`).
    """

    def __init__(
        self,
        play_api: "PlayAPI",
        ziptree: ZipTree,
        playfile: PlayFile,
        workno: str | None = None,
    ):
        self._play = play_api
        self.ziptree = ziptree
        self.playfile = playfile
        self.workno = workno or ziptree.workno
        if not self.workno:
            raise ValueError("workno must be specified")
        if not self.playfile.is_epub_reflowable:
            raise ValueError("Unsupported epub type: {self.playfile.type}")
        self._token: CSRReflowableToken | None = None
        self._deobfuscators: dict[int, "_Deobfuscator"] = {}

    @property
    def page_count(self) -> int:
        return self._total_page if self._total_page is not None else 0

    def __len__(self) -> int:
        return self.page_count

    async def __aenter__(self) -> "EpubReflowableSession":
        await self.load()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def load(self) -> None:
        if self._token is None:
            self._token = await self._download_token()

    async def close(self) -> None:
        self._token = None
        self._total_page = None
        self._start_page = None
        self._version = None
        self._scramble_size = None

    async def _download_token(self) -> CSRReflowableToken:
        """Return a download token for this work."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )
        hashname, _ = os.path.splitext(self.playfile.hashname or "")
        payload = {
            "workno": self.workno,
            "hashname": hashname,
            "revision": self.ziptree.revision or "",
            "public_key": b64encode(
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            ).decode(),
            "play_type": "epub_reflowable",
        }
        url = "https://play.dlsite.com/api/v3/csr/reflowable/token"
        async with self._play.post(url, json=payload) as response:
            data = await response.json()
            values = data["values"]

            ciphertext = b64decode(values["key"])
            plaintext = private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            values["key"] = bytes.fromhex(plaintext.decode())
            return CSRReflowableToken.from_json(values)

    def _decrypt(self, data: bytes, offset: int = 0) -> bytes:
        if self._token is None:
            raise DlsiteError("CSR-R token must be loaded")
        if not self._token.key:
            return data
        return bytes(
            data[i] ^ self._token.key[(offset + i) % len(self._token.key)]
            for i in range(len(data))
        )

    async def download_epub(
        self,
        dest_dir: str | Path,
        mkdir: bool = False,
        force: bool = False,
        **save_kwargs: Any,
    ) -> Path:
        """Download epub file to the specified location.

        Args:
            dest_dir: Destination directory to write the downloaded file.
            mkdir: Create ``dest_dir`` and parent directories if they do not already
                exist.
            force: Overwrite existing destination file if it already exists.

        Returns:
            Downloaded file path.

        Raises:
            FileExistsError: destination file already exists.
        """
        if self._token is None:
            raise DlsiteError("CSR-R session has not been loaded")
        dest = Path(dest_dir) / f"{self.workno}.epub"
        if not force and dest.exists():
            raise FileExistsError(str(dest))
        if mkdir and not dest.parent.exists():
            dest.parent.mkdir(parents=True)
        zinfos: dict[Path, zipfile.ZipInfo] = {}

        with tempfile.TemporaryDirectory(prefix=dest.name, dir=dest.parent) as tempdir:
            tmp_dir = Path(tempdir)

            def _add_entry(entry: tuple[Path, zipfile.ZipInfo]) -> None:
                path, zinfo = entry
                if path in zinfos:
                    return
                zinfos[path] = zinfo

            _add_entry(await self._download_epub_entry(tmp_dir, "mimetype"))
            preprocess_settings, _ = await self._download_epub_entry(
                tmp_dir, "preprocess-settings.json"
            )
            with open(preprocess_settings) as f:
                settings = _PreprocessSettings.from_json(
                    await asyncio.to_thread(json.load, f)
                )
            container, zinfo = await self._download_epub_entry(
                tmp_dir, "META-INF/container.xml"
            )
            _add_entry((container, zinfo))
            opf_entry = await self._get_rootfile(container)
            opf, zinfo = await self._download_epub_entry(tmp_dir, opf_entry)
            _add_entry((opf, zinfo))
            for entry in await self._download_epub_contents(tmp_dir, opf, settings):
                _add_entry(entry)
            await asyncio.to_thread(
                self._zip_epub,
                dest,
                zinfos.items(),
            )
        return dest

    def _zip_epub(
        self, dest: Path, entries: Iterable[tuple[Path, zipfile.ZipInfo]]
    ) -> None:
        with tempfile.NamedTemporaryFile(
            prefix=dest.stem, suffix=dest.suffix, dir=dest.parent, delete=False
        ) as temp:
            with zipfile.ZipFile(temp, mode="w") as zf:
                for path, zinfo in entries:
                    if zinfo.is_dir():
                        zf.mkdir(zinfo)
                    else:
                        with open(path, "rb") as f:
                            zf.writestr(zinfo, f.read())
        os.replace(temp.name, dest)

    async def _download_epub_entry(
        self, tmp_dir: Path, epub_entry: str
    ) -> tuple[Path, zipfile.ZipInfo]:
        if self._token is None:
            raise DlsiteError("CSR-R session has not been loaded")
        dest = tmp_dir / epub_entry
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True)
        url = f"{self._token.base_url}/{epub_entry}"
        async with self._play.get(
            url,
            headers={
                "Authorization": f"Bearer {urllib.parse.quote_plus(self._token.vt)}"
            },
            timeout=self._play._DL_TIMEOUT,
        ) as response:
            with tempfile.NamedTemporaryFile(
                prefix=dest.stem, suffix=dest.suffix, dir=dest.parent, delete=False
            ) as temp:
                offset = 0
                async for chunk in response.content.iter_chunked(
                    self._play._DL_CHUNK_SIZE
                ):
                    temp.write(self._decrypt(chunk, offset=offset))
                    offset += len(chunk)
            last_modified = response.headers.get("Last-Modified")
            if last_modified:
                dt = parsedate_to_datetime(last_modified)
                os.utime(temp.name, (time.time(), dt.timestamp()))
        os.replace(temp.name, dest)
        zipinfo = zipfile.ZipInfo.from_file(
            dest, arcname=str(PurePosixPath(dest.relative_to(tmp_dir)))
        )
        return dest, zipinfo

    @staticmethod
    async def _get_rootfile(container_path: Path) -> str:
        ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        root = await asyncio.to_thread(etree.parse, str(container_path))
        rootfile = root.find(".//c:rootfile", namespaces=ns)
        if rootfile is None:
            raise ValueError("epub container does not contain OPF rootfile")
        full_path = rootfile.get("full-path")
        if not full_path:
            raise ValueError("epub container rootfile missing full-path")
        return full_path

    async def _download_epub_contents(
        self, tmp_dir: Path, opf_path: Path, settings: _PreprocessSettings
    ) -> list[tuple[Path, zipfile.ZipInfo]]:
        ns = {
            "opf": "http://www.idpf.org/2007/opf",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        root = await asyncio.to_thread(etree.parse, str(opf_path))
        contents: list[tuple[Path, zipfile.ZipInfo]] = []
        sem = asyncio.Semaphore(min(32, (os.cpu_count() or 1) + 4))

        async def _download_one(item: etree.Element) -> None:
            href = item.get("href")
            if not href:
                return
            entry = str(opf_path.relative_to(tmp_dir).parent / href)
            async with sem:
                try:
                    mime_type = item.get("media-type")
                    logger.debug(
                        "Downloading opf manifest entry: {}{}",
                        entry,
                        f" ({mime_type})" if mime_type else "",
                    )
                    dest, zinfo = await self._download_epub_entry(tmp_dir, entry)
                    await self._deobfuscate(dest, settings, mime_type=mime_type)
                    if not mime_type or not mime_type.startswith("image/"):
                        zinfo.compress_type = zipfile.ZIP_DEFLATED
                    contents.append((dest, zinfo))
                except ClientResponseError:
                    logger.exception("Failed to download opf manifest entry {entry}")

        await asyncio.gather(
            *(
                _download_one(item)
                for item in root.findall("./opf:manifest/opf:item", namespaces=ns)
            )
        )
        return contents

    async def _deobfuscate(
        self, path: Path, settings: _PreprocessSettings, mime_type: str | None = None
    ) -> None:
        if not mime_type:
            return
        if mime_type.startswith("image/"):
            return await self._deobfuscate_image(path, settings, mime_type)
        return await self._deobfuscate_text(path, settings, mime_type)

    async def _deobfuscate_image(
        self, path: Path, settings: _PreprocessSettings, mime_type: str
    ) -> None:
        if not settings.obfuscate_image:
            return
        formats: dict[str, bytes] = {
            "image/gif": b"GIF8",
            "image/jpeg": b"\xff\xd8",
            "image/png": b"\x89PNG",
        }
        with open(path, "rb") as f:
            data = await asyncio.to_thread(f.read)
        magic = formats.get(mime_type)
        if magic and data[: len(magic)] == magic:
            return

        def _xor() -> Iterator[int]:
            for i, c in enumerate(data):
                if i < 100:
                    yield c ^ (settings.obfuscate_image_key or 0)
                else:
                    yield c

        with tempfile.NamedTemporaryFile(
            prefix=path.stem, suffix=path.suffix, dir=path.parent, delete=False
        ) as temp:
            temp.write(bytes(_xor()))
        os.replace(temp.name, path)

    async def _deobfuscate_text(
        self, path: Path, settings: _PreprocessSettings, mime_type: str
    ) -> None:
        if not settings.obfuscate_text or not mime_type == "application/xhtml+xml":
            return
        ns = {
            "xhtml": "http://www.w3.org/1999/xhtml",
            "epub": "http://www.idpf.org/2007/ops",
        }
        root = etree.parse(
            path, parser=etree.XMLParser(dtd_validation=False, load_dtd=True)
        )
        for span in root.findall(".//xhtml:span", namespaces=ns):
            data_ofs = span.get("data-ofs")
            if (
                not data_ofs
                or not etree.tostring(span, method="text", encoding="utf-8").strip()
            ):
                continue
            seed = int(data_ofs, 36)
            # data_seq_id = span.get("data-seq-id")
            # seq_id = int(data_seq_id, 36) if data_seq_id else -1
            if seed in self._deobfuscators:
                deobfuscator = self._deobfuscators[seed]
            else:
                deobfuscator = _Deobfuscator(seed)
                self._deobfuscators[seed] = deobfuscator

            def _deobfuscate(element: etree.Element) -> None:
                if element.text:
                    element.text = deobfuscator(element.text)
                if element.tail:
                    element.tail = deobfuscator(element.tail)
                for child in element:
                    _deobfuscate(child)

            _deobfuscate(span)

        with tempfile.NamedTemporaryFile(
            prefix=path.stem, suffix=path.suffix, dir=path.parent, delete=False
        ) as temp:
            root.write(
                temp.name,
                pretty_print=True,
                encoding="UTF-8",
                doctype=root.docinfo.doctype,
            )
        os.replace(temp.name, path)


_decoders: dict[int, dict[str, str]] = {}


class _Deobfuscator:
    _HIRAGANA = (
        "あいうえおかがきぎくぐけげこごさざしじすずせぜそぞただちぢつづてでとどなにぬね"
        "のはばぱひびぴふぶぷへべぺほぼぽまみむめもやゆよらりるれろわゐゑをんゔ"
    )
    _KATAKANA = (
        "アイウエオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂツヅテデトドナニヌネ"
        "ノハバパヒビピフブプヘベペホボポマミムメモヤユヨラリルレロワヰヱヲンヴヷヸヹヺ"
    )
    _KANJI = (
        "国人大年生地的日化本会自中一民政分世業者合動法発行方立権間定力成主子出代物体社"
        "対家活時事用戦制上学後第経場文多産内性教関高理入条要利保界現実水治度済結部進同"
        "機金軍議心通義問気見外考東題表数市族約争加原域平品新意連開長下全明支和働府以際"
        "手食労紀不変言調強作質前期情有共海公反資重農量基電安朝使私由所解運図決報住工都"
        "思交目正商近酸統料道形必小取北南西月命集二流設次求領展素在組受諸持配書信最独境"
        "改身面特革"
    )

    def __init__(self, seed: int):
        if seed not in _decoders:
            xorshift = _Xorshift(seed)
            orig = "".join([self._HIRAGANA, self._KATAKANA, self._KANJI])
            shuffled = "".join(
                self.shuffle(s, xorshift)
                for s in (self._HIRAGANA, self._KATAKANA, self._KANJI)
            )
            _decoders[seed] = {shuffled[i]: c for i, c in enumerate(orig)}
        self.decode = _decoders[seed]

    @staticmethod
    def shuffle(s: str, xorshift: "_Xorshift") -> str:
        chars = list(s)
        i = 0
        while i < len(s) - 2:
            j = xorshift(i + 1, len(s) - 1)
            new_j = chars[i]
            chars[i] = chars[j]
            chars[j] = new_j
            i += 1
        return "".join(chars)

    def __call__(self, s: str) -> str:
        return "".join(self.decode.get(c, c) for c in s)


class _Xorshift:
    """Xorshift PRNG."""

    def __init__(self, seed: int):
        self._seed = seed
        self.prng = self._prng()

    @property
    def seed(self) -> int:
        return self._seed

    def __call__(self, seq: int, n: int) -> int:
        return seq + abs(next(self.prng)) % (n + 1 - seq)

    def _prng(self) -> Iterator[int]:
        x = 123456789
        y = 362436069
        z = 521288629
        w = self.seed

        while True:
            t = x ^ (x << 11 & 0xFFFFFFFF)
            x = y
            y = z
            z = w
            w = w ^ w >> 19 ^ t ^ t >> 8
            yield js_int(w)


def js_int(n: int) -> int:
    # mimic JS signed 32-bit integer for bitwise operations
    n &= 0xFFFFFFFF
    if n >= 0x80000000:
        n -= 0x100000000
    return n
