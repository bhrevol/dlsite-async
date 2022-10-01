"""DLsite Play API classes."""
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Union

from ..api import BaseAPI
from .models import DownloadToken, PlayFile, ZipTree
from .scramble import descramble as _descramble


logger = logging.getLogger(__name__)


class PlayAPI(BaseAPI["PlayAPI"]):
    """DLsite Play API session."""

    async def login(self, *args: Any, **kwargs: Any) -> None:
        """Login to DLsite Play."""
        await super().login()
        url = "https://play.dlsite.com/login/"
        async with self.get(url) as response:
            await response.read()
        url = "https://play.dlsite.com/api/authorize"
        async with self.get(
            url, headers={"Referer": "https://play.dlsite.com/"}
        ) as response:
            await response.read()

    async def download_token(self, workno: str) -> DownloadToken:
        """Return a download token for the specified workno.

        Args:
            workno: DLsite product ID.

        Returns:
            A new download token.
        """
        url = "https://play.dlsite.com/api/download_token"
        async with self.get(url, params={"workno": workno}) as response:
            return DownloadToken.from_json(await response.json())

    async def ziptree(self, token: DownloadToken) -> ZipTree:
        """Return ziptree for the specified download.

        Args:
            token: A download token returned from `download_token`.

        Returns:
            A new zip tree.
        """
        url = f"{token.url}ziptree.json"
        async with self.get(url, params=token.params) as response:
            return ZipTree.from_json(await response.json())

    async def download_playfile(
        self,
        token: DownloadToken,
        playfile: PlayFile,
        dest: Union[str, Path],
        mkdir: bool = False,
        force: bool = False,
        descramble: bool = False,
    ) -> None:
        """Download playfile to the specified location.

        Args:
            token: A download token returned from `download_token`.
            playfile: PlayFile to download.
            dest: Destination path to write the downloaded file.
            mkdir: Create ``dest`` parent directories if they do not already
                exist.
            force: Overwrite `dest` if it already exists.
            descramble: Descramble downloaded images (requires optional
                ``dlsite-async[pil]`` dependency packages).

        Raises:
            FileExistsError: ``dest`` already exists.
        """
        if isinstance(dest, str):
            dest = Path(dest)
        try:
            url = f"{token.url}optimized/{playfile.optimized_name}"
        except KeyError:
            logger.warn(
                f"Could not download {dest}: no web-optimized version available."
            )
            return
        if mkdir and not dest.parent.exists():
            dest.parent.mkdir()
        if not force and dest.exists():
            raise FileExistsError(str(dest))
        async with self.get(
            url, params=token.params, timeout=self._DL_TIMEOUT
        ) as response:
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=dest.name, dir=dest.parent, delete=False
                ) as temp:
                    async for chunk in response.content.iter_chunked(
                        self._DL_CHUNK_SIZE
                    ):
                        temp.write(chunk)
            except Exception:
                temp.close()
                os.remove(temp)
                raise
        os.replace(temp.name, dest)
        if (
            playfile.type == "image"
            and playfile.files["optimized"].get("crypt")
            and descramble
        ):
            _descramble(dest, playfile)
