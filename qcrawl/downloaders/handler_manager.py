"""Download handler manager for routing requests to appropriate downloaders."""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from qcrawl import signals
from qcrawl.core.request import Request
from qcrawl.core.response import Page
from qcrawl.downloaders.base import DownloaderProtocol
from qcrawl.utils.settings import resolve_dotted_path

if TYPE_CHECKING:
    from qcrawl.settings import Settings as RuntimeSettings

logger = logging.getLogger(__name__)


class DownloadHandlerManager:
    """Manages multiple download handlers and routes requests appropriately.

    Responsibilities:
      - Route requests to appropriate handler based on meta or URL scheme
      - Lazy-initialize handlers only when needed
      - Implement DownloaderProtocol interface
      - Manage lifecycle (close all handlers)

    Routing Logic:
      1. request.meta['use_handler'] - Explicit handler selection
      2. URL scheme (http, https, ftp, s3, etc.) - Protocol-based routing
      3. Fallback to 'http' handler

    Example Usage:
      # Browser request (requires explicit handler)
      yield Request(url="https://example.com", meta={'use_handler': 'camoufox'})

      # HTTP request (automatic scheme routing)
      yield Request(url="https://example.com")  # → HTTPDownloader

      # FTP request (automatic scheme routing)
      yield Request(url="ftp://files.example.com/data.zip")  # → FTPDownloader

      # S3 request (automatic scheme routing)
      yield Request(url="s3://bucket/key")  # → S3Downloader
    """

    __slots__ = (
        "_handler_configs",
        "_handlers",
        "_settings",
        "_closed",
        "signals",
    )

    def __init__(
        self,
        handler_configs: dict[str, str],
        settings: RuntimeSettings,
    ) -> None:
        """Initialize handler manager with handler configurations.

        Args:
            handler_configs: Mapping of handler name -> dotted path to downloader class
            settings: Runtime settings for handler initialization
        """
        self._handler_configs = handler_configs
        self._settings = settings
        self._handlers: dict[str, DownloaderProtocol] = {}
        self._closed = False
        self.signals = signals.signals_registry.for_sender(self)

    async def fetch(
        self,
        request: Request | str,
        *,
        spider: object | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 180.0,
    ) -> Page:
        """Fetch request by routing to appropriate handler.

        Args:
            request: Request object or URL string
            spider: Spider instance (for accessing runtime settings)
            headers: Additional headers to set
            timeout: Request timeout in seconds

        Returns:
            Page object with response content

        Raises:
            RuntimeError: If manager is closed or no handler available
            Exception: Handler-specific errors during download
        """
        if self._closed:
            raise RuntimeError("Cannot fetch: handler manager is closed")

        if isinstance(request, str):
            request = Request(url=request)

        # Select handler based on routing rules
        handler_name = self._select_handler(request)
        handler = await self._get_or_create_handler(handler_name)

        # Delegate to handler
        try:
            return await handler.fetch(request, spider=spider, headers=headers, timeout=timeout)
        except Exception as exc:
            logger.error(
                "Handler %r failed for %s: %s",
                handler_name,
                getattr(request, "url", None),
                exc,
            )
            raise

    def _select_handler(self, request: Request) -> str:
        """Select handler name based on request meta and URL scheme.

        Priority:
          1. request.meta['use_handler'] - Explicit handler name
          2. URL scheme (http, https, ftp, s3, etc.) - Actual protocol
          3. Fallback to 'http'

        Note: Browser automation requires explicit use_handler since URLs
        are still http/https (e.g., can't use camoufox:// scheme).

        Args:
            request: Request object

        Returns:
            Handler name (key from DOWNLOAD_HANDLERS)
        """
        # Priority 1: Explicit handler selection
        if hasattr(request, "meta") and request.meta.get("use_handler"):
            handler_name = request.meta["use_handler"]
            if handler_name in self._handler_configs:
                return str(handler_name)
            logger.warning(
                "Handler %r specified in meta not found in DOWNLOAD_HANDLERS, falling back to scheme",
                handler_name,
            )

        # Priority 2: URL scheme (for actual protocols)
        try:
            scheme = urlparse(request.url).scheme
            if scheme in self._handler_configs:
                return scheme
        except Exception:
            logger.exception("Error parsing URL scheme from %s", getattr(request, "url", None))

        # Priority 3: Fallback to http
        if "http" in self._handler_configs:
            return "http"

        # Last resort: first available handler
        if self._handler_configs:
            first = next(iter(self._handler_configs.keys()))
            logger.warning(
                "No suitable handler for %s, using first available: %r",
                getattr(request, "url", None),
                first,
            )
            return first

        raise RuntimeError("No download handlers configured in DOWNLOAD_HANDLERS")

    async def _get_or_create_handler(self, handler_name: str) -> DownloaderProtocol:
        """Get existing handler or create it with runtime validation.

        Follows the same pattern as Crawler._resolve_downloader_middleware for consistency.

        Args:
            handler_name: Handler identifier from _handler_configs

        Returns:
            Initialized download handler that implements DownloaderProtocol

        Raises:
            RuntimeError: If handler class not found or initialization fails
            TypeError: If handler doesn't implement DownloaderProtocol
        """
        # Return cached handler if exists
        if handler_name in self._handlers:
            return self._handlers[handler_name]

        # Get handler class path
        handler_path = self._handler_configs.get(handler_name)
        if not handler_path:
            raise RuntimeError(f"Handler {handler_name!r} not configured in DOWNLOAD_HANDLERS")

        # Resolve handler class
        try:
            handler_cls = resolve_dotted_path(handler_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to import handler {handler_name!r} from {handler_path!r}: {exc}"
            ) from exc

        # Runtime validation: ensure it's a class
        if not inspect.isclass(handler_cls):
            raise RuntimeError(
                f"Handler {handler_path!r} resolved to {type(handler_cls)!r}, expected a class"
            )

        # Try to instantiate handler
        handler_instance: DownloaderProtocol

        if hasattr(handler_cls, "create") and inspect.iscoroutinefunction(handler_cls.create):
            # Has async create() classmethod
            try:
                handler_instance = await handler_cls.create(
                    settings=self._get_handler_settings(handler_name)
                )
                logger.debug("Created handler %r via create() classmethod", handler_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to create handler {handler_name!r} via create(): {exc}"
                ) from exc
        elif callable(handler_cls):
            # Regular class instantiation
            try:
                handler_instance = handler_cls()
                logger.debug("Created handler %r via __init__()", handler_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to instantiate handler {handler_name!r}: {exc}"
                ) from exc
        else:
            raise RuntimeError(f"Handler {handler_path!r} is not instantiable")

        # Final validation: ensure it implements the protocol
        # DownloaderProtocol is @runtime_checkable, so isinstance works
        if not isinstance(handler_instance, DownloaderProtocol):
            raise TypeError(
                f"Handler {handler_name!r} does not implement DownloaderProtocol. "
                f"Got {type(handler_instance)!r}"
            )

        # Cache and return
        self._handlers[handler_name] = handler_instance
        return handler_instance

    def _get_handler_settings(self, handler_name: str) -> dict[str, object]:
        """Extract settings relevant to specific handler.

        Args:
            handler_name: Handler identifier

        Returns:
            Settings dict for handler.create() method
        """
        if handler_name == "camoufox":
            # Return Camoufox-specific settings
            return {
                "contexts": self._settings.CAMOUFOX_CONTEXTS,
                "max_contexts": self._settings.CAMOUFOX_MAX_CONTEXTS,
                "max_pages_per_context": self._settings.CAMOUFOX_MAX_PAGES_PER_CONTEXT,
                "default_timeout": self._settings.CAMOUFOX_DEFAULT_NAVIGATION_TIMEOUT,
                "launch_options": self._settings.CAMOUFOX_LAUNCH_OPTIONS,
                "cdp_url": self._settings.CAMOUFOX_CDP_URL,
                "abort_request": self._settings.CAMOUFOX_ABORT_REQUEST,
                "process_request_headers": self._settings.CAMOUFOX_PROCESS_REQUEST_HEADERS,
            }
        elif handler_name in ("http", "https"):
            # Return HTTP downloader settings
            # Note: dict[str, int|bool|float] is compatible with dict[str, object]
            downloader_settings = self._settings.DOWNLOADER_SETTINGS
            return dict(downloader_settings) if downloader_settings else {}
        else:
            # Default: empty settings dict
            return {}

    async def close(self) -> None:
        """Close all active handlers and release resources.

        Safe to call multiple times (idempotent).
        """
        if self._closed:
            return

        self._closed = True

        # Close all handlers
        for name, handler in list(self._handlers.items()):
            try:
                if hasattr(handler, "close"):
                    await handler.close()
                    logger.debug("Closed handler %r", name)
            except Exception:
                logger.exception("Error closing handler %r", name)

        self._handlers.clear()

    async def __aenter__(self) -> DownloadHandlerManager:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Async context manager exit - ensures cleanup."""
        await self.close()
        return False

    @property
    def is_closed(self) -> bool:
        """Check if handler manager is closed."""
        return self._closed


__all__ = ["DownloadHandlerManager"]
