"""Test fixtures."""

import inspect
from typing import TYPE_CHECKING
from collections.abc import AsyncGenerator
from unittest.mock import Mock

import aiohttp
import pytest


if TYPE_CHECKING:
    from dlsite_async.api import DlsiteAPI
    from dlsite_async.play.api import PlayAPI


# monkeypatch aioresponses to support breaking change in aiohttp 3.14
_response_init = aiohttp.ClientResponse.__init__
if "stream_writer" in inspect.signature(_response_init).parameters:

    def _patched_response_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("stream_writer", Mock(output_size=0))
        _response_init(self, *args, **kwargs)

    aiohttp.ClientResponse.__init__ = _patched_response_init  # type: ignore[method-assign]


@pytest.fixture
async def api() -> AsyncGenerator["DlsiteAPI", None]:
    """API test fixture."""
    from dlsite_async.api import DlsiteAPI

    async with DlsiteAPI() as api:
        yield api


@pytest.fixture
async def play_api() -> AsyncGenerator["PlayAPI", None]:
    """API test fixture."""
    from dlsite_async.play.api import PlayAPI

    async with PlayAPI() as play:
        yield play
