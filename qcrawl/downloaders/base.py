"""Base protocol for pluggable downloaders."""

from typing import Protocol, runtime_checkable

from qcrawl.core.request import Request
from qcrawl.core.response import Page
from qcrawl.signals import SignalDispatcher


@runtime_checkable
class DownloaderProtocol(Protocol):
    """Protocol that all downloaders must implement.

    Downloaders are responsible for:
    - Fetching web pages from URLs
    - Managing connection pooling and resources
    - Emitting signals for monitoring
    - Proper async context management
    """

    signals: SignalDispatcher

    async def fetch(
        self,
        request: Request | str,
        *,
        spider: object | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 180.0,
    ) -> Page:
        """Fetch a page from the given request.

        Args:
            request: Request object or URL string
            spider: Spider instance (for accessing runtime settings)
            headers: Additional headers to set
            timeout: Request timeout in seconds

        Returns:
            Page object with response content and metadata

        Raises:
            Exception: Various network/HTTP errors during download
        """
        ...

    async def close(self) -> None:
        """Close downloader and release resources.

        Should be idempotent (safe to call multiple times).
        """
        ...

    async def __aenter__(self) -> "DownloaderProtocol":
        """Async context manager entry."""
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures cleanup."""
        ...
