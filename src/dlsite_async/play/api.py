"""DLsite Play API classes."""
from typing import Any

from ..api import BaseAPI
from .models import DownloadToken, ZipTree


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
