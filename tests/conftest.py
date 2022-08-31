"""Test fixtures."""
from typing import AsyncGenerator

import pytest

from dlsite_async.api import DlsiteAPI


@pytest.fixture
async def api() -> AsyncGenerator[DlsiteAPI, None]:
    """API test fixture."""
    async with DlsiteAPI() as api:
        yield api
