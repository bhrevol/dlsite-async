"""DLsite Play API tests."""
import re
from datetime import datetime, timedelta, timezone

from aioresponses import aioresponses

from dlsite_async.play.api import PlayAPI
from dlsite_async.play.models import (
    DownloadToken,
    PlayFile,
    ZipTree,
    _TreeFile,
    _TreeFolder,
)


_URL_PATTERN = re.compile(r"^https://play(\.dl)?\.dlsite\.com")

_TEST_WORKNO = "RJ123456"
_TEST_DOWNLOAD_TOKEN_JSON = {
    "url": "https://play.dl.dlsite.com/content/work/doujin/RJ123000/RJ123456/",
    "cookies": {
        "CloudFront-Policy": "abcd1234",
        "CloudFront-Signature": "abcd1234",
        "CloudFront-Key-Pair-Id": "ABCD1234",
    },
    "expires": "2022-09-24T17:42:01+0900",
}
_TEST_DOWNLOAD_TOKEN = DownloadToken(  # noqa: S106
    expires_at=datetime(2022, 9, 24, 17, 42, 1, tzinfo=timezone(timedelta(hours=9))),
    url="https://play.dl.dlsite.com/content/work/doujin/RJ123000/RJ123456/",
)
_TEST_ZIPTREE_JSON = {
    "hash": "123456abcdef",
    "playfile": {
        "123456abcdef.jpg": {
            "image": {
                "files": {
                    "crypt": False,
                    "name": "123456abcdef.jpg",
                    "length": 1234,
                    "size": "1234.0B",
                },
                "optimized": {
                    "crypt": True,
                    "name": "optimized.jpg",
                    "length": 123,
                    "size": "123.0B",
                },
            },
            "length": 1234,
            "size": "1234.0B",
            "type": "image",
        }
    },
    "tree": [
        {
            "type": "folder",
            "children": [
                {
                    "type": "folder",
                    "children": [
                        {
                            "type": "file",
                            "name": "baz.jpg",
                            "hashname": "123456abcdef.jpg",
                        },
                    ],
                    "name": "bar",
                    "path": "foo/bar",
                },
            ],
            "name": "foo",
            "path": "foo",
        },
    ],
    "workno": _TEST_WORKNO,
}
_TEST_PLAYFILE = PlayFile(
    length=1234,
    type="image",
    files={
        "files": {
            "crypt": False,
            "name": "123456abcdef.jpg",
            "length": 1234,
            "size": "1234.0B",
        },
        "optimized": {
            "crypt": True,
            "name": "optimized.jpg",
            "length": 123,
            "size": "123.0B",
        },
    },
    hashname="123456abcdef.jpg",
)
_TEST_ZIPTREE = ZipTree(
    hash="123456abcdef",
    playfile={"123456abcdef.jpg": _TEST_PLAYFILE},
    tree=[
        _TreeFolder(
            children=[
                _TreeFolder(
                    children=[
                        _TreeFile(
                            hashname="123456abcdef.jpg",
                            name="baz.jpg",
                        ),
                    ],
                    name="bar",
                    path="foo/bar",
                )
            ],
            name="foo",
            path="foo",
        )
    ],
    workno=_TEST_WORKNO,
)


async def test_playfile() -> None:
    """Properties should be filled."""
    playfile = _TEST_PLAYFILE
    assert playfile.size == "1.2KB"
    assert playfile.optimized_name == "optimized.jpg"
    assert playfile.optimized_length == 123


async def test_download_token(play_api: PlayAPI) -> None:
    """Download token should be returned."""
    with aioresponses() as m:
        m.get(
            _URL_PATTERN,
            payload=_TEST_DOWNLOAD_TOKEN_JSON,
        )
        assert _TEST_DOWNLOAD_TOKEN == await play_api.download_token(_TEST_WORKNO)


async def test_ziptree(play_api: PlayAPI) -> None:
    """Ziptree should be returned."""
    token = _TEST_DOWNLOAD_TOKEN
    with aioresponses() as m:
        m.get(
            _URL_PATTERN,
            payload=_TEST_ZIPTREE_JSON,
        )
        ziptree = await play_api.ziptree(token)
        assert _TEST_ZIPTREE == ziptree
        assert {"foo/bar/baz.jpg": _TEST_PLAYFILE} == ziptree._dict
