"""Test fixtures."""
from typing import TYPE_CHECKING, AsyncGenerator

import pytest


if TYPE_CHECKING:
    from dlsite_async.api import DlsiteAPI


@pytest.fixture
async def api() -> AsyncGenerator["DlsiteAPI", None]:
    """API test fixture."""
    from dlsite_async.api import DlsiteAPI

    async with DlsiteAPI() as api:
        yield api
