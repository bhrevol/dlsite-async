"""API tests."""
import re
from copy import copy
from dataclasses import fields, replace
from datetime import datetime

from aioresponses import aioresponses
from pytest_mock import MockerFixture

from dlsite_async.api import DlsiteAPI
from dlsite_async.circle import Circle
from dlsite_async.work import AgeCategory, BookType, Work, WorkType


_URL_PATTERN = re.compile(r"^https://www\.dlsite\.com")

_TEST_PRODUCT = "RJ1234"
_TEST_INFO = {
    _TEST_PRODUCT: {
        "site_id": "maniax",
        "maker_id": "RG1234",
        "work_name": "Test Work",
        "age_category": 3,
        "work_type": "SOU",
        "regist_date": "2022-01-01 00:00:00",
        "book_type": {"value": "comic"},
    }
}
_TEST_INFO_WORK = Work(
    product_id=_TEST_PRODUCT,
    site_id="maniax",
    maker_id="RG1234",
    work_name="Test Work",
    age_category=AgeCategory.R18,
    work_type=WorkType.VOICE_ASMR,
    regist_date=datetime(2022, 1, 1, 0, 0, 0),
    book_type=BookType.BOOK,
)
_TEST_HTML_WORK = replace(
    _TEST_INFO_WORK,
    modified_date=datetime(2022, 1, 1, 0, 0, 0),
    page_count=123,
    circle="Test Circle",
    voice_actor=["Test Seiyuu 1", "Test Seiyuu 2"],
    series="Test Series",
)
_WORK_TEST_HTML = r"""
<html>
<head />
<body>
<table id="work_maker">
  <tbody>
    <tr>
      <th>サークル名</th>
      <td>
        <span itemprop="brand" class="maker_name">
          <a href="https://www.dlsite.com/maniax/circle/profile/=/maker_id/">
            Test Circle
          </a>
        </span>
        <div class="btn_follow">
          <span class="add_follow">
            <a href="/maniax/mypage/followlist/add/=/follow_key/RG1234/>
              フォローする
            </a>
        </div>
      </td>
    </tr>
  </tbody>
</table>
<table cellspacing="0" id="work_outline">
  <tbody>
    <tr>
      <th>更新情報</th>
      <td>
        2022年01月01日
        <div class="btn_ver_up"><a href="#version_up">更新情報</a></div>
      </td>
    </tr>
    <tr>
      <th>シリーズ名</th>
      <td>
        <a href="https://www.dlsite.com/maniax/fsr/=/keyword_work_name/">
          Test Series
        </a>
      </td>
    </tr>
    <tr>
      <th>声優</th>
      <td>
        <a href="https://www.dlsite.com/maniax/fsr/=/keyword_creater/">
          Test Seiyuu 1
        </a>
        /
        <a href="https://www.dlsite.com/maniax/fsr/=/keyword_creater/">
          Test Seiyuu 2
        </a>
      </td>
    </tr>
    <tr>
      <th>ページ数</th>
      <td>123</td>
    </tr>
    <tr>
    <th>作品形式</th>
    <td>
      <div class="work_genre" id="category_type">
        <a href="https://www.dlsite.com/maniax/works/type/=/work_type/SOU/">
          <span class="icon_SOU" title="ボイス・ASMR">ボイス・ASMR</span>
        </a>
      </div>
    </td>
  </tr>
  </tbody>
</table>
</body>
</html>
"""

_TEST_MAKER = "RG1234"
_TEST_CIRCLE = Circle(
    maker_id=_TEST_MAKER,
    maker_name="Test Circle",
)
_CIRCLE_TEST_HTML = r"""
<html>
<head />
<body>
<table cellspacing="0">
  <tbody>
    <tr>
      <th>サークル名</th>
      <td>
        <div class="prof_maker_box">
        <strong class="prof_maker_name">Test Circle</strong>
        <div class="btn_follow">
          <span class="add_follow">
            <a href="#" class="_show_follow_login btn_follow btn_follow_in">
              フォロー済み
            </a>
          </span>
        </div>
      </td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


def _check_work_eq(expected: Work, actual: Work) -> None:
    for field in fields(expected):
        name = field.name
        value = getattr(expected, name, None)
        if value is not None:
            assert getattr(actual, name, None) == value


def _check_circle_eq(expected: Circle, actual: Circle) -> None:
    for field in fields(expected):
        name = field.name
        value = getattr(expected, name, None)
        if value is not None:
            assert getattr(actual, name, None) == value
    assert expected.maker_type == actual.maker_type


async def test_cookies() -> None:
    """18+ cookie should be set."""
    async with DlsiteAPI() as api:
        assert any(
            cookie.key == "adultchecked" and cookie.value == "1"
            for cookie in api.session.cookie_jar
        )


async def test_locale(mocker: MockerFixture) -> None:
    """Locale query param should be set."""
    locale = "ja_JP"
    async with DlsiteAPI(locale=locale) as api:
        m = mocker.patch.object(api.session, "get")
        api.get("http://foo/")
        expected = {"locale": locale}
        assert m.call_args.kwargs.get("params") == expected
        m.reset_mock()

        api.get("http://foo/", params={"foo": "bar"})
        expected.update({"foo": "bar"})
        assert m.call_args.kwargs.get("params") == expected


async def test_product_info(api: DlsiteAPI) -> None:
    """Ajax API info should be filled."""
    with aioresponses() as m:
        m.get(
            _URL_PATTERN,
            payload=_TEST_INFO,
        )
        work = await api.product_info(_TEST_PRODUCT)
        _check_work_eq(_TEST_INFO_WORK, work)


async def test_fill_work_details(api: DlsiteAPI) -> None:
    """Full product info should be filled."""
    work = copy(_TEST_INFO_WORK)
    with aioresponses() as m:
        m.get(
            _URL_PATTERN,
            body=_WORK_TEST_HTML,
        )
        work = await api._fill_work_details(work)
        _check_work_eq(_TEST_HTML_WORK, work)


async def test_get_circle(api: DlsiteAPI) -> None:
    """Full circle info should be filled."""
    with aioresponses() as m:
        m.get(
            _URL_PATTERN,
            body=_CIRCLE_TEST_HTML,
        )
        circle = await api.get_circle(_TEST_MAKER)
        _check_circle_eq(_TEST_CIRCLE, circle)
