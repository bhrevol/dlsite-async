"""Utilities."""
import re
from datetime import datetime

from .exceptions import InvalidIDError


_PRODUCT_RE = re.compile(r"(?<!\w)[BRV]J\d+", flags=re.IGNORECASE)
_MAKER_RE = re.compile(r"(?<!\w)[BRV]G\d+", flags=re.IGNORECASE)


def find_product_id(s: str) -> str:
    """Find a DLsite product ID in a string.

    Arguments:
        s: String containing a product ID.

    Returns:
        Product ID.

    Raises:
        InvalidIDError: `s` did not contain a valid product ID.
    """
    m = _PRODUCT_RE.search(s)
    if m:
        return m.group().upper()
    raise InvalidIDError(f"No DLsite product ID in string: {s}")


def find_maker_id(s: str) -> str:
    """Find a DLsite maker ID in a string.

    Arguments:
        s: String containing a maker ID.

    Returns:
        Maker ID.

    Raises:
        InvalidIDError: `s` did not contain a valid maker ID.
    """
    m = _MAKER_RE.search(s)
    if m:
        return m.group().upper()
    raise InvalidIDError(f"No DLsite maker ID in string: {s}")


def fromisoformat(timestamp: str) -> datetime:
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        pass
    for pattern in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(timestamp, pattern)
        except ValueError:
            pass
    raise ValueError
