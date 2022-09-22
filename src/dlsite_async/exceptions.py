"""Exception classes."""


class DlsiteError(Exception):
    """Base DLsite exception."""


class InvalidIDError(DlsiteError):
    """Invalid DLsite ID error."""


class ScrapingError(DlsiteError):
    """HTML scraping error."""


class AuthenticationError(DlsiteError):
    """Authentication error."""
