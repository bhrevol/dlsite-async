"""Utils tests."""
import pytest

from dlsite_async.exceptions import InvalidIDError
from dlsite_async.utils import find_maker_id, find_product_id


@pytest.mark.parametrize(
    "s, product_id",
    [
        ("RJ1234", "RJ1234"),
        ("rj1234", "RJ1234"),
        ("[RJ1234] Title", "RJ1234"),
        ("BJ1234", "BJ1234"),
        ("VJ1234", "VJ1234"),
    ],
)
def test_find_product_id(s: str, product_id: str) -> None:
    """Should match expected product ID."""
    assert find_product_id(s) == product_id


@pytest.mark.parametrize("s", ["ARJ1234", "RJ-1234", "RJ", "1234", "some title"])
def test_find_product_id_failed(s: str) -> None:
    """Should fail to match a product ID."""
    with pytest.raises(InvalidIDError):
        find_product_id(s)


@pytest.mark.parametrize(
    "s, maker_id",
    [
        ("RG1234", "RG1234"),
        ("rg1234", "RG1234"),
        ("[RG1234] Title", "RG1234"),
        ("BG1234", "BG1234"),
        ("VG1234", "VG1234"),
    ],
)
def test_find_maker_id(s: str, maker_id: str) -> None:
    """Should match expected maker ID."""
    assert find_maker_id(s) == maker_id


@pytest.mark.parametrize("s", ["ARG1234", "RG-1234", "RG", "1234", "some title"])
def test_find_maker_id_failed(s: str) -> None:
    """Should fail to match a maker ID."""
    with pytest.raises(InvalidIDError):
        find_maker_id(s)
