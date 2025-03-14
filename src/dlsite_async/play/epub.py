"""DLsite Play CSR viewer."""
import asyncio
import logging
import os
import tempfile
import time
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Sequence, Union

from lxml import etree

from ..exceptions import DlsiteError
from .models import CSRToken, PlayFile, ZipTree

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


class EpubSession(AbstractAsyncContextManager["EpubSession"]):
    """DLsite Play CSR (dlst epub) Viewer Session.

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
        workno: Optional[str] = None,
    ):
        self._play = play_api
        self.ziptree = ziptree
        self.playfile = playfile
        self.workno = workno or ziptree.workno
        if not self.workno:
            raise ValueError("workno must be specified")
        if not self.playfile.is_epub:
            raise ValueError("Unsupported epub type: {self.playfile.type}")
        self._token: Optional[CSRToken] = None
        self._total_page: Optional[int] = None
        self._start_page: Optional[int] = None
        self._version: Optional[str] = None
        self._scramble_size: Optional[tuple[int, int]] = None
        self._wake_up: Optional[int] = None

    @property
    def page_count(self) -> int:
        return self._total_page if self._total_page is not None else 0

    def __len__(self) -> int:
        return self.page_count

    async def __aenter__(self) -> "EpubSession":
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
        url = "https://play.dlsite.com/api/csr/token"
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
        dest_dir: Union[str, Path],
        mkdir: bool = False,
        descramble: bool = False,
        force: bool = False,
    ) -> None:
        """Download one ebook page to the specified location.

        Args:
            index: Zero-indexed page number to download.
            dest_dir: Destination directory to write the downloaded file.
            mkdir: Create ``dest_dir`` and parent directories if they do not already
                exist.
            force: Overwrite existing destination file if it already exists.
            descramble: Descramble downloaded images (requires optional
                ``dlsite-async[pil]`` dependency packages).

        Raises:
            FileExistsError: destination file already exists.
        """
        if self._token is None:
            raise DlsiteError("CSR session has not been loaded")
        page_info = await self._download_page_info(index)
        dest_dir = Path(dest_dir)
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
                    self._descramble, temp.name, self._scramble_size, page_info.scramble
                )
            os.replace(temp.name, dest)

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
        path: Union[str, Path],
        scramble_size: tuple[int, int],
        scramble: Sequence[int],
    ) -> None:
        try:
            from PIL import Image
        except ImportError:
            logger.warn("Image descramble requires installation with dlsite-async[pil]")
            return
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
        new_im.save(path)
