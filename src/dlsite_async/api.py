"""DLsite API classes."""
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import datetime
from typing import Any, AsyncContextManager, Dict, Optional

from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager

from ._scraper import parse_circle_html, parse_work_html
from .circle import Circle
from .exceptions import DlsiteError
from .work import AgeCategory, BookType, Work, WorkType


def _datetime_from_timestamp(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")


class DlsiteAPI(AsyncContextManager["DlsiteAPI"]):
    """DLsite API session.

    Arguments:
        locale: Optional locale. Defaults to ja_JP.
    """

    def __init__(self, locale: Optional[str] = None):
        self.locale = locale
        self._exit_stack = AsyncExitStack()
        self.session = ClientSession(cookies={"adultchecked": "1"})
        self._exit_stack.push_async_exit(self.session)

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close this API session."""
        async with self._exit_stack:
            pass

    @property
    def _common_params(self) -> Dict[str, str]:
        return {"locale": self.locale} if self.locale else {}

    def get(self, *args: Any, **kwargs: Any) -> _RequestContextManager:
        """Perform get request."""
        if "params" in kwargs:
            kwargs["params"].update(self._common_params)
        else:
            kwargs["params"] = self._common_params
        return self.session.get(*args, **kwargs)

    async def get_work(self, product_id: str) -> Work:
        """Return the specified work.

        Arguments:
            product_id: DLsite product ID.

        Returns: Complete work information.
        """
        work = await self.product_info(product_id)
        return await self._fill_work_details(work)

    async def product_info(self, product_id: str) -> Work:
        """Return ajax API product info.

        Arguments:
            product_id: DLsite product ID.

        Returns: Minimal product information.

        Raises:
            DlsiteError: Failed to get product info.
        """
        url = "https://www.dlsite.com/maniax/product/info/ajax"
        params = {"product_id": product_id}
        async with self.get(url, params=params) as response:
            data = await response.json()
        if not data or product_id not in data:
            raise DlsiteError(f"Failed to get product info for {product_id}")
        info = data[product_id]
        info["product_id"] = product_id
        info["age_category"] = AgeCategory(info["age_category"])
        info["work_type"] = WorkType(info["work_type"])
        if info.get("book_type"):
            info["book_type"] = BookType(info["book_type"]["value"])
        if info.get("regist_date"):
            info["regist_date"] = _datetime_from_timestamp(info["regist_date"])
        return Work.from_dict(info)

    async def _fill_work_details(self, work: Work) -> Work:
        html = await self._fetch_work_html(work)
        if not html:
            return work
        details = parse_work_html(html)
        return replace(work, **details)

    async def _fetch_work_html(self, work: Work) -> Optional[str]:
        urls = [
            (
                f"https://www.dlsite.com/{work.site_id}/{typ}"
                f"/=/product_id/{work.product_id}.html"
            )
            for typ in ("work", "announce")
        ]
        html: Optional[str] = None
        for url in urls:
            async with self.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    break
        return html

    async def get_circle(self, maker_id: str) -> Circle:
        """Return the specified circle.

        Arguments:
            maker_id: DLsite maker ID.

        Returns: Circle information.

        Raises:
            DlsiteError: Failed to fetch circle information.
        """
        html = await self._fetch_circle_html(maker_id)
        if not html:
            raise DlsiteError(f"Failed to get circle {maker_id}")
        info = parse_circle_html(html)
        info["maker_id"] = maker_id
        return Circle.from_dict(info)

    async def _fetch_circle_html(self, maker_id: str) -> Optional[str]:
        url = (
            f"https://www.dlsite.com/maniax/circle/profile"
            f"/=/maker_id/{maker_id}.html"
        )
        async with self.get(url) as response:
            if response.status == 200:
                return await response.text()
        return None
