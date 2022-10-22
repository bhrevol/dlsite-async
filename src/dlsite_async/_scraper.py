"""HTML scraper."""
import logging
import unicodedata
from abc import ABC, abstractmethod
from datetime import date, datetime
from html import unescape
from typing import Any, Iterable, Optional, cast

from lxml import html
from lxml.html import soupparser

from .exceptions import ScrapingError


logger = logging.getLogger()


def _unescape(content: str) -> str:
    """Return unescaped and normalized HTML content."""
    return unicodedata.normalize("NFKC", unescape(content)).strip()


class _RowParser(ABC):
    """Work outline table row parser."""

    def __init__(self, field: str, headers: Iterable[str]):
        self.field = field
        self.headers = set(headers)

    def can_parse(self, th: html.HtmlElement) -> bool:
        """Return whether or not row can be parsed based on header."""
        header = _unescape(th.text_content())
        return header in self.headers

    @abstractmethod
    def parse_value(self, td: html.HtmlElement) -> Any:
        """Parse the specfied table cell value."""
        return _unescape(td.text_content())


class _DateRowParser(_RowParser):
    """Date row parser."""

    def parse_value(self, td: html.HtmlElement) -> date:
        """Parse the specfied table cell value."""
        value = cast(str, super().parse_value(td))
        return self._to_date(value.split()[0])

    @staticmethod
    def _to_date(value: str) -> date:
        for fmt in ("%Y年%m月%d日", "%b/%d/%Y", "%B/%d/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:  # pragma: no cover
                pass
        raise ScrapingError(f"Failed to parse date string {value}")


class _IntRowParser(_RowParser):
    """Integer row parser."""

    def parse_value(self, td: html.HtmlElement) -> int:
        """Parse the specfied table cell value."""
        try:
            value = super().parse_value(td)
            return int(value)
        except ValueError as e:  # pragma: no cover
            raise ScrapingError(f"Failed to parse integer {value}") from e


class _MakerRowParser(_RowParser):
    """Maker row parser."""

    def parse_value(self, td: html.HtmlElement) -> str:
        """Parse the specfied table cell value."""
        try:
            span = td.xpath('//span[@class="maker_name"]')[0]
        except IndexError as e:  # pragma: no cover
            raise ScrapingError(f"Failed to parse cell {td}") from e
        return _unescape(cast(str, span.text_content()))


class _ListRowParser(_RowParser):
    """Item list row parser."""

    def parse_value(self, td: html.HtmlElement) -> list[str]:
        """Parse the specfied table cell value."""
        return [_unescape(a.text_content()) for a in td.xpath(".//a")]


class _TextRowParser(_RowParser):
    """Text row parser."""

    def parse_value(self, td: html.HtmlElement) -> str:
        """Parse the specfied table cell value."""
        return cast(str, super().parse_value(td))


_parsers = [
    _DateRowParser("announce_date", ("予告開始日", "Published date")),
    _DateRowParser(
        "modified_date",
        ("最終更新日", "更新情報", "Last updated", "Update information"),
    ),
    _IntRowParser("page_count", ("ページ数", "Page count")),
    _MakerRowParser("brand", ("ブランド名", "Brand")),
    _MakerRowParser("circle", ("サークル名", "Circle")),
    _MakerRowParser("publisher", ("出版社名", "Publisher")),
    _MakerRowParser("label", ("レーベル", "Label")),
    _ListRowParser("author", ("作者", "著者", "Author")),
    _ListRowParser("event", ("イベント", "Event")),
    _ListRowParser("file_format", ("ファイル形式", "File format")),
    _ListRowParser("illustration", ("イラスト", "Illustration")),
    _ListRowParser("genre", ("ジャンル", "Genre")),
    _ListRowParser("music", ("音楽", "Music")),
    _ListRowParser("scenario", ("シナリオ", "Scenario")),
    _ListRowParser("voice_actor", ("声優", "Voice Actor")),
    _ListRowParser("writer", ("作家", "Writer")),
    _TextRowParser("file_size", ("ファイル容量", "File size")),
    _TextRowParser("series", ("シリーズ名", "Series", "Series name")),
]


def parse_work_html(content: str) -> dict[str, Any]:
    """Parse work HTML."""
    tree = html.soupparser.fromstring(content)
    info: dict[str, Any] = {}
    for table in (
        '//table[@id="work_maker"]//tr',
        '//table[@id="work_outline"]//tr',
    ):
        info.update(_parse_work_outline_rows(cast(html.HtmlElement, tree.xpath(table))))
    return info


def _parse_work_outline_rows(trs: Iterable[html.HtmlElement]) -> Any:
    for tr in trs:
        try:
            th = tr.xpath(".//th")[0]
            td = tr.xpath(".//td")[0]
        except IndexError:  # pragma: no cover
            logger.exception(f"Failed to parse outline row: {tr}")
            continue
        for parser in _parsers:
            if parser.can_parse(th):
                try:
                    yield parser.field, parser.parse_value(td)
                except ScrapingError:  # pragma: no cover
                    pass
                break
        else:
            logger.debug(f"No matching parser for outline row: {tr}")


def parse_circle_html(content: str) -> dict[str, Any]:
    """Parse circle HTML."""
    tree = soupparser.fromstring(content)
    for strong in tree.xpath('//strong[@class="prof_maker_name"]'):
        info: dict[str, Any] = {
            "maker_name": _unescape(cast(html.HtmlElement, strong).text_content())
        }
        return info
    raise ScrapingError("Failed to find maker name")  # pragma: no cover


def parse_login_token(content: str) -> str:
    """Parse login form token."""
    tree = soupparser.fromstring(content)
    for input_ in cast(html.HtmlElement, tree.xpath('.//input[@name="_token"]')):
        token: Optional[str] = input_.get("value")
        if token is not None:
            return token
    raise ScrapingError("Failed to find login form token.")
