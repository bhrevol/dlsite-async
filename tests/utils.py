"""Testing utilities."""

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from typing import Any, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

from curl_cffi import Response

from dlsite_async.api import BaseAPI


_T = TypeVar("_T")


@contextmanager
def mock_responses(
    api: BaseAPI[_T], status_code: int = 200, **kwargs: Any
) -> Generator[None, None, None]:
    response = MagicMock(spec=Response)
    response.status_code = status_code
    if "json" in kwargs:
        v = kwargs.pop("json")
        response.json = MagicMock(return_value=v)
    for k, v in kwargs.items():
        setattr(response, k, v)
    method = AsyncMock(return_value=response)
    with ExitStack() as stack:
        stack.enter_context(patch.object(api.session, "get", method))
        stack.enter_context(patch.object(api.session, "post", method))
        yield
