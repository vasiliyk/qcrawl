import gzip
import logging
import zlib
from typing import TYPE_CHECKING

from qcrawl.middleware.base import DownloaderMiddleware, MiddlewareResult

if TYPE_CHECKING:
    from qcrawl.core.request import Request
    from qcrawl.core.response import Page
    from qcrawl.core.spider import Spider

logger = logging.getLogger(__name__)

# Prefer stdlib compression.zstd (Python 3.14+), fallback to zstandard package
_ZSTD_STD = None
_ZSTD_ZSTANDARD = None
try:
    # Python 3.14+: compression.zstd
    from compression import zstd as _ZSTD_STD  # type: ignore
except Exception:
    _ZSTD_STD = None

if _ZSTD_STD is None:
    try:
        import zstandard as _ZSTD_ZSTANDARD  # type: ignore
    except Exception:
        _ZSTD_ZSTANDARD = None


def _decompress_zstd(data: bytes) -> bytes:
    if _ZSTD_STD is not None:
        # Try simple API first, then ZstdDecompressor
        try:
            # Some stdlib proposals expose a simple decompress() helper
            return _ZSTD_STD.decompress(data)
        except Exception:
            try:
                dec = _ZSTD_STD.ZstdDecompressor()
                return dec.decompress(data)
            except Exception as exc:  # pragma: no cover - defensive
                raise RuntimeError("compression.zstd decompress failed") from exc
    if _ZSTD_ZSTANDARD is not None:
        try:
            dec = _ZSTD_ZSTANDARD.ZstdDecompressor()
            return dec.decompress(data)
        except Exception as exc:
            raise RuntimeError("zstandard decompression failed") from exc
    raise RuntimeError("zstd support not available")


class HttpCompressionMiddleware(DownloaderMiddleware):
    """Decompress responses with Content-Encoding: gzip, deflate, zstd.

    - Adds 'Accept-Encoding' header to requests.
    - Replaces Page with decompressed content and adjusts headers.
    - Configuration is provided via constructor only (enable_zstd boolean).
    """

    def __init__(self, enable_zstd: bool = True) -> None:
        # Respect explicit constructor argument only; detect runtime support for zstd.
        self.enable_zstd = bool(enable_zstd) and (
            _ZSTD_STD is not None or _ZSTD_ZSTANDARD is not None
        )

    async def process_request(self, request: "Request", spider: "Spider") -> MiddlewareResult:
        # Add Accept-Encoding header (preserve existing headers)
        request.headers = dict(request.headers or {})
        encs = ["gzip", "deflate"]
        if self.enable_zstd:
            encs.append("zstd")
        request.headers.setdefault("Accept-Encoding", ", ".join(encs))
        return MiddlewareResult.continue_()

    async def process_response(
        self, request: "Request", response: "Page", spider: "Spider"
    ) -> MiddlewareResult:
        # Inspect Content-Encoding (case-insensitive)
        ce = ""
        try:
            # response.headers is a dict[str, str]
            for k, v in (response.headers or {}).items():
                if k.lower() == "content-encoding":
                    ce = v or ""
                    break
        except Exception:
            ce = ""

        if not ce:
            return MiddlewareResult.keep(response)

        encs = [e.strip().lower() for e in ce.split(",") if e.strip()]

        body = response.content
        try:
            # Support single or stacked encodings by applying in order
            for enc in encs:
                if enc in ("gzip", "x-gzip"):
                    body = gzip.decompress(body)
                elif enc in ("deflate",):
                    # Try raw zlib then raw deflate fallback
                    try:
                        body = zlib.decompress(body)
                    except zlib.error:
                        body = zlib.decompress(body, -zlib.MAX_WBITS)
                elif enc in ("zstd", "zstandard"):
                    if not self.enable_zstd:
                        logger.debug(
                            "Received zstd content but zstd support unavailable; skipping decompression"
                        )
                        # Cannot decompress - keep original response
                        return MiddlewareResult.keep(response)
                    body = _decompress_zstd(body)
                else:
                    # Unknown encoding: skip processing and return as-is
                    logger.debug(
                        "Unknown Content-Encoding %r for %s; skipping decompression",
                        enc,
                        request.url,
                    )
                    return MiddlewareResult.keep(response)
        except Exception:
            logger.exception("Failed to decompress %s (encodings=%r)", request.url, encs)
            return MiddlewareResult.keep(response)

        # Build a new Page with decompressed body. Preserve url/status_code/request.
        from qcrawl.core.response import Page

        new_headers = dict(response.headers or {})
        # remove content-encoding and update content-length
        new_headers.pop("Content-Encoding", None)
        new_headers.pop("content-encoding", None)
        if "Content-Length" in new_headers:
            new_headers["Content-Length"] = str(len(body))
        elif "content-length" in new_headers:
            new_headers["content-length"] = str(len(body))

        new_page = Page(
            url=getattr(response, "url", ""),
            content=body,
            status_code=getattr(response, "status_code", 0),
            headers=new_headers,
            request=getattr(response, "request", None),
            encoding=None,
        )

        logger.debug("Decompressed %s: removed %s", request.url, ce)
        return MiddlewareResult.keep(new_page)

    async def process_exception(
        self, request: "Request", exception: BaseException, spider: "Spider"
    ) -> MiddlewareResult:
        # No special exception handling
        return MiddlewareResult.continue_()
