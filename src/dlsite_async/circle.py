"""DLsite circle classes."""
from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any

from .exceptions import InvalidIDError


class MakerType(str, Enum):
    """Maker type."""

    BRAND = "brand"
    CIRCLE = "circle"
    PUBLISHER = "publisher"

    @classmethod
    def from_maker_id(cls, maker_id: str) -> "MakerType":
        """Return MakerType from maker_id.

        Arguments:
            maker_id: Maker ID

        Returns:
            Maker type.

        Raises:
            InvalidIDError: `maker_id` was invalid.
        """
        if maker_id[:2] == "RG":
            return MakerType.CIRCLE
        if maker_id[:2] == "BG":
            return MakerType.PUBLISHER
        if maker_id[:2] == "VG":
            return MakerType.BRAND
        raise InvalidIDError(f"Invalid maker ID {maker_id}")


@dataclass
class Circle:
    """DLsite circle (maker) class."""

    maker_id: str
    maker_name: str

    @property
    def maker_type(self) -> MakerType:
        """Return maker type for this circle."""
        return MakerType.from_maker_id(self.maker_id)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Circle":
        """Construct Circle from a dictionary."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})
