"""DLsite Play ebook viewer."""
import os
import importlib.util
import logging
import tempfile
from base64 import b64encode, b64decode
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization

from ..exceptions import DlsiteError
from .models import PlayFile, ViewerToken, ZipTree

if TYPE_CHECKING:
    from .api import PlayAPI


logger = logging.getLogger(__name__)


class EbookSession(AbstractAsyncContextManager["EbookSession"]):
    """DLsite Play Ebook Viewer Session.

    Args:
        play_api: Parent PlayAPI session.
        ziptree: DLsite Play ZipTree for the ebook work. Must contain an ``ebook_fixed``
            playfile entry.
        playfile: PlayFile entry for the ebook to open in ``ziptree``.
        workno: DLsite product ID for the ebook work (defaults to `ziptree.workno`).
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
        if not self.playfile.is_ebook:
            raise ValueError("Unsupported ebook type: {self.playfile.type}")
        self._token: Optional[ViewerToken] = None
        self._meta: dict[str, Any] = {}

    @property
    def _meta_data(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._meta.get("meta_data", {}))

    @property
    def _pages(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self._meta.get("pages", []))

    @property
    def title(self) -> str:
        return cast(str, self._meta_data.get("title", ""))

    @property
    def creators(self) -> list[str]:
        return cast(list[str], self._meta_data.get("creator", []))

    @property
    def page_count(self) -> int:
        return cast(int, self._meta.get("page_count", 0))

    def __len__(self) -> int:
        return self.page_count

    async def __aenter__(self) -> "EbookSession":
        await self.load()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def load(self) -> None:
        if self._token is None:
            self._token = await self._download_token()
        if not self._meta:
            self._meta.update(await self._download_meta())

    async def close(self) -> None:
        self._token = None
        self._meta = {}

    async def _download_token(self) -> ViewerToken:
        """Return a download token for this ebook."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )
        payload = {
            "play_type": "ebook_fixed",
            "revision": self.ziptree.revision or "",
            "public_key": b64encode(
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            ).decode(),
        }
        url = f"https://play.dlsite.com/api/v2/viewer/token/{self.workno}"
        async with self._play.post(url, json=payload) as response:
            data = await response.json()
            ciphertext = b64decode(data["key"])
            plaintext = private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            data["key"] = bytes.fromhex(plaintext.decode())
            data["v"] = self.ziptree.revision or ""
            return ViewerToken.from_json(data)

    async def _download_meta(self) -> dict[str, Any]:
        """Return viewer metadata for this ebook."""
        if self._token is None:
            raise DlsiteError("Ebook session has not been loaded")
        url = f"{self._token.prefix}/{self.playfile.hashname}/viewer-meta.json"
        async with self._play.get(url, params=self._token.params) as response:
            return cast(dict[str, Any], await response.json())

    async def download_page(
        self,
        index: int,
        dest_dir: Union[str, Path],
        mkdir: bool = False,
        convert: Optional[Literal["jpg", "png"]] = None,
        force: bool = False,
    ) -> None:
        """Download one ebook page to the specified location.

        Args:
            index: Zero-indexed page number to download.
            dest_dir: Destination directory to write the downloaded file.
            mkdir: Create ``dest_dir`` and parent directories if they do not already
                exist.
            force: Overwrite existing destination file if it already exists.
            convert: Convert downloaded images to the specified format (requires optional
                ``dlsite-async[pil]`` dependency packages). By default, images are
                downloaded in the original DLsite Play Viewer WebP format.

        Raises:
            FileExistsError: ``dest`` already exists.
        """
        if self._token is None:
            raise DlsiteError("Ebook session has not been loaded")
        if isinstance(dest_dir, str):
            dest_dir = Path(dest_dir)
        try:
            page = self._pages[index]
        except IndexError as e:
            raise ValueError("Invalid page number") from e
        src = Path(page["src"])
        url = f"{self._token.prefix}/{self.playfile.hashname}/{src}"

        if convert:
            if importlib.util.find_spec("PIL.Image") is not None:
                ext: str = convert
            else:
                logger.warn(
                    "Image conversion requires installation with dlsite-async[pil]"
                )
                ext = "webp"
                convert = None
        else:
            ext = "webp"
        dest = dest_dir / f"{src.stem}.{ext}"
        if mkdir and not dest.parent.exists():
            dest.parent.mkdir(parents=True)
        if not force and dest.exists():
            raise FileExistsError(str(dest))
        async with self._play.get(
            url, params=self._token.params, timeout=self._play._DL_TIMEOUT
        ) as response:
            with tempfile.NamedTemporaryFile(
                prefix=dest.stem, suffix=".webp", dir=dest.parent, delete=False
            ) as temp:
                try:
                    offset = 0
                    async for chunk in response.content.iter_chunked(
                        self._play._DL_CHUNK_SIZE
                    ):
                        temp.write(
                            bytes(
                                chunk[i]
                                ^ self._token.key[(offset + i) % len(self._token.key)]
                                for i in range(len(chunk))
                            )
                        )
                        offset += len(chunk)
                except Exception:
                    temp.close()
                    os.remove(temp.name)
                    raise
        if convert:
            _convert(temp.name, dest)
            os.remove(temp.name)
        else:
            os.replace(temp.name, dest)


def _convert(src: Union[str, Path], dest: Union[str, Path]) -> None:
    from PIL import Image

    with Image.open(src) as im:
        im.save(dest)
