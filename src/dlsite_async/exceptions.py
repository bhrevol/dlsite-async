"""Exception classes."""


class DLsiteError(Exception):
    """Base DLsite exception."""


class InvalidIDError(DLsiteError):
    """Invalid DLsite ID error."""


class ScrapingError(DLsiteError):
    """HTML scraping error."""
