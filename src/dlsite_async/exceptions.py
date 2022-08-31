"""Exception classes."""


class DLsiteError(Exception):
    """Base DLsite exception."""


class ScrapingError(DLsiteError):
    """HTML scraping error."""
