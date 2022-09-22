"""Test fixtures."""
from typing import TYPE_CHECKING, AsyncGenerator

import pytest


if TYPE_CHECKING:
    from dlsite_async.api import DlsiteAPI
    from dlsite_async.play.api import PlayAPI


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
