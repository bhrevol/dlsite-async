"""Circle tests."""
import pytest

from dlsite_async.circle import MakerType
from dlsite_async.exceptions import InvalidIDError


def test_maker_type_from_id() -> None:
    """Should return proper maker type."""
    assert MakerType.from_maker_id("RG1234") == MakerType.CIRCLE
    assert MakerType.from_maker_id("BG1234") == MakerType.PUBLISHER
    assert MakerType.from_maker_id("VG1234") == MakerType.BRAND
    with pytest.raises(InvalidIDError):
        MakerType.from_maker_id("XG1234")
