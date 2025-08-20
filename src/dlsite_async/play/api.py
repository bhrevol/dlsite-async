"""DLsite Play API classes."""
import logging
import os
import tempfile
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Iterator, Mapping, Optional, Union

from ..api import BaseAPI
from ..work import AgeCategory, Work, WorkType
from ..utils import fromisoformat
from .models import DownloadToken, PlayFile, ZipTree
from .scramble import descramble as _descramble


logger = logging.getLogger(__name__)


class PlayAPI(BaseAPI["PlayAPI"]):
    """DLsite Play API session.

    Args:
        locale: Optional locale. Defaults to ``ja_JP``.
    """

    def __init__(self, locale: Optional[str] = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.locale = locale

    async def login(self, *args: Any, **kwargs: Any) -> None:
        """Login to DLsite Play."""
        await super().login(*args, **kwargs)
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
        url = "https://play.dl.dlsite.com/api/v3/download/sign/cookie"
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
        async with self.get(url) as response:
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
            dest.parent.mkdir(parents=True)
        if not force and dest.exists():
            raise FileExistsError(str(dest))
        async with self.get(url, timeout=self._DL_TIMEOUT) as response:
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

    async def purchases(
        self,
        last: Optional[datetime] = None,
    ) -> AsyncIterator[tuple[Work, Optional[datetime]]]:
        """Iterate over purchased works.

        Work information is populated using the Play API and may not match what would
        be returned when using `DlsiteAPI.get_work()`. Fields which are populated in
        both APIs will match, but not all fields are returned when using the Play API.

        All purchased works will be yielded as long as that work is still downloadable
        or playable in DLsite Play. This may be useful for looking up metadata for works
        which are unavailable in `DlsiteAPI.get_work()` (i.e. time-limited purchase
        benefits or works which have been deleted or hidden by the original creator).

        Purchased works which have been permanently removed will not be yielded (i.e.
        works where the original creator has completely removed their circle/maker
        account).

        Args:
            last: Yield works purchased since `last`. Defaults to returning all works.

        Yields: Tuples of the form (purchased_work, purchase_date).

        Note:
            Play API requests are made concurrently and yielded as they are completed.
            Purchases are not guaranteed to be yielded in historical order.
        """
        url = "https://play.dlsite.com/api/v3/content/works"
        last_ = int(last.timestamp()) if last else 0
        count, _page_limit, _concurrency = await self._get_product_count(last_)
        if count < 1:
            return
        worknos, sales = await self._get_product_sales(last_)

        async def _get_one(page: int) -> Any:
            start = page * 100
            async with self.post(
                url,
                json=[workno for workno in worknos[start : start + 100]],
            ) as response:
                return await response.json()

        # api v3 webapp ignores pagination/concurrency and just requests 100 works at a time
        # api v3 server also does not like high concurrent requests so just do
        # it sequentially
        for works in _batched(worknos, 100):
            async with self.post(url, json=works) as response:
                data = await response.json()
            for work in data.get("works", []):
                purchase, sales_date = _parse_purchase(
                    work, locale=self.locale or "ja_JP"
                )
                yield (purchase, sales_date or sales.get(purchase.product_id))

    async def _get_product_count(self, last: int) -> tuple[int, int, int]:
        url = "https://play.dlsite.com/api/v3/content/count"
        async with self.get(url, params={"last": last}) as response:
            data = await response.json()
        return (
            data.get("user", 0),
            data.get("page_limit", 50),
            data.get("concurrency", 500),
        )

    async def _get_product_sales(
        self, last: int
    ) -> tuple[list[str], dict[str, datetime]]:
        url = "https://play.dlsite.com/api/v3/content/sales"
        async with self.get(url, params={"last": last}) as response:
            data = await response.json()
        works = []
        sales = {}
        for item in data:
            try:
                works.append(item["workno"])
                sales[item["workno"]] = fromisoformat(item["sales_date"])
            except KeyError:
                continue
        return works, sales


def _batched(iterable: Iterable[Any], n: int) -> Iterator[tuple[Any, ...]]:
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


def _parse_purchase(
    d: Mapping[str, Any], locale: str = "ja_JP"
) -> tuple[Work, Optional[datetime]]:
    """Construct Work from purchases API dictionary."""
    d = dict(d)
    d["age_category"] = AgeCategory[d["age_category"].upper()]
    if d.get("author_name"):
        d["authors"] = [author.strip() for author in d["author_name"].split("/")]
    d["maker_id"] = d["maker"]["id"]
    if d["maker_id"].startswith("R"):
        d["circle"] = _localized_name(d["maker"]["name"])
    else:
        d["brand"] = _localized_name(d["maker"]["name"])
    d["work_name"] = _localized_name(d["name"])
    if d.get("regist_date"):
        d["regist_date"] = fromisoformat(d["regist_date"])
    if d.get("sales_date"):
        sales_date: Optional[datetime] = fromisoformat(d["sales_date"])
    else:
        sales_date = None
    tags = d.get("tags") or []
    for tag in tags:
        classes = {
            "created_by": "author",
            "scenario_by": "scenario",
            "illust_by": "illustration",
            "voice_by": "voice_actor",
            "music_by": "music",
        }
        k = classes.get(tag.get("class"))
        if k and tag.get("name"):
            if k not in d:
                d[k] = []
            d[k].append(tag["name"])
    if d.get("upgrade_date"):
        d["modified_date"] = fromisoformat(d["upgrade_date"])
    for k, v in d.get("work_files", {}).items():
        if k == "main":
            d["work_image"] = v
        else:
            if "sample_images" not in d:
                d["sample_images"] = []
            d["sample_images"].append(v)
    if d.get("work_type"):
        d["work_type"] = WorkType(d["work_type"])
    d["product_id"] = d["workno"]
    return Work.from_dict(d), sales_date


def _localized_name(d: Mapping[str, str], locale: str = "ja_JP") -> str:
    return d.get(locale, d["ja_JP"])
