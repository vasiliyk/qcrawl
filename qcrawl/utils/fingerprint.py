from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from yarl import URL

from qcrawl.utils.url import normalize_url

if TYPE_CHECKING:
    from qcrawl.core.request import Request


class RequestFingerprinter:
    """Generate unique fingerprints for requests to enable smart deduplication.

    Features:
      - ignore_query_params: set of param names to remove
      - keep_query_params: whitelist mode (only these params are kept)
      - Full URL normalization via your existing normalize_url()
      - Method + normalized URL + body hashing
      - blake2b (fast) or any hashlib algorithm
    """

    def __init__(
        self,
        ignore_query_params: set[str] | None = None,
        keep_query_params: set[str] | None = None,
    ):
        self.ignore_query_params = ignore_query_params or set()
        self.keep_query_params = keep_query_params or set()

        if self.keep_query_params and self.ignore_query_params:
            raise ValueError(
                "Cannot use both ignore_query_params and keep_query_params simultaneously"
            )

    def fingerprint_bytes(
        self,
        request: Request,
        digest_size: int = 16,
        algorithm: str = "blake2b",
    ) -> bytes:
        """Generate unique fingerprint for request using the serialized bytes
        returned by Request.to_bytes().

        Args:
            request: Request instance to fingerprint.
            digest_size: Number of bytes for BLAKE2b digest (only used for blake2b).
            algorithm: Hash algorithm name ('blake2b' (default), 'sha256', or any
                       name accepted by hashlib.new).
        """
        method = (getattr(request, "method", "GET") or "GET").upper()
        method_bytes = method.encode("ascii", "ignore")

        url_bytes = self._normalized_url(str(getattr(request, "url", ""))).encode("utf-8")

        body = getattr(request, "body", None)
        body_bytes = b""
        if body:
            if isinstance(body, (bytes, bytearray)):
                body_bytes = bytes(body)
            else:
                body_bytes = str(body).encode("utf-8")

        data = b"\x00".join(filter(None, [method_bytes, url_bytes, body_bytes]))

        algo = (algorithm or "blake2b").lower()
        if algo == "blake2b":
            return hashlib.blake2b(data, digest_size=digest_size).digest()
        return hashlib.new(algo, data).digest()

    def _filter_query_params(self, url: str) -> str:
        """Filter query parameters using yarl.URL before final normalization."""
        u = URL(url)
        if not u.query:
            return url

        items: list[tuple[str, str]] = list(u.query.items())
        if self.keep_query_params:
            filtered = [(k, v) for k, v in items if k in self.keep_query_params]
        else:
            filtered = [(k, v) for k, v in items if k not in self.ignore_query_params]

        return str(u.with_query(filtered))

    def _normalized_url(self, url: str) -> str:
        """Apply query filtering + full canonical normalization."""
        return normalize_url(self._filter_query_params(url))
