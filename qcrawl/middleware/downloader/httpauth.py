import base64
import hashlib
import logging
import secrets
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from qcrawl.core.request import Request
from qcrawl.core.response import Page
from qcrawl.middleware.base import DownloaderMiddleware, MiddlewareResult
from qcrawl.utils.url import get_domain

if TYPE_CHECKING:
    from qcrawl.core.spider import Spider

logger = logging.getLogger(__name__)


class HttpAuthMiddleware(DownloaderMiddleware):
    """Handle HTTP Basic and Digest authentication.

    Features:
    - Basic authentication (proactive)
    - Digest authentication (reactive with 401 handling)
    - Per-domain credentials
    - Per-request credential override via meta
    - Automatic Authorization header injection

    Configuration:
      - Provide credentials via constructor or call `add_credentials`.
      - Per-request overrides via `request.meta['auth']` and `request.meta['auth_type']`.
    """

    def __init__(
        self,
        credentials: dict[str, tuple[str, str]] | None = None,
        auth_type: str = "basic",
        digest_qop_auth_int: bool = False,
    ):
        if auth_type not in ("basic", "digest"):
            raise ValueError(f"auth_type must be 'basic' or 'digest', got {auth_type!r}")
        self._credentials = credentials or {}
        self.auth_type = auth_type
        self.digest_qop_auth_int = digest_qop_auth_int
        self._digest_challenges: dict[str, dict[str, str]] = {}

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL using canonical helper."""
        return get_domain(url)

    def _encode_basic_auth(self, username: str, password: str) -> str:
        """Encode username:password as Basic auth header value."""
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    def _parse_digest_challenge(self, www_authenticate: str) -> dict[str, str]:
        """Parse WWW-Authenticate: Digest header.

        Example: Digest realm="api", nonce="abc123", qop="auth"
        """
        if not www_authenticate.startswith("Digest "):
            return {}

        params: dict[str, str] = {}
        challenge = www_authenticate[7:].strip()
        parts = [p.strip() for p in challenge.split(",") if p.strip()]
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            params[key.strip()] = value.strip().strip('"')
        return params

    def _build_digest_response(
        self,
        username: str,
        password: str,
        method: str,
        uri: str,
        challenge: dict[str, str],
        request: Request,
    ) -> str | None:
        """Build Digest Authorization header (RFC 2617).

        Supports:
        - qop="" (legacy)
        - qop="auth" (default)
        - qop="auth-int" (optional, opt-in)

        Returns None if unsupported configuration.
        """
        realm = challenge.get("realm", "")
        nonce = challenge.get("nonce", "")
        qop = challenge.get("qop", "")
        algorithm = challenge.get("algorithm", "MD5").upper()
        opaque = challenge.get("opaque", "")

        if algorithm != "MD5":
            logger.warning("Unsupported Digest algorithm: %s, using MD5", algorithm)
            algorithm = "MD5"

        cnonce = secrets.token_hex(8)
        nc = "00000001"

        # HA1
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()

        # HA2
        if qop == "auth-int" and self.digest_qop_auth_int:
            body = request.body or b""
            body_hash = hashlib.md5(body).hexdigest()
            ha2 = hashlib.md5(f"{method}:{uri}:{body_hash}".encode()).hexdigest()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("qop=auth-int: hashed %d-byte body", len(body))
        else:
            ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
            if qop == "auth-int":
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "qop=auth-int requested but disabled (performance). Using qop=auth."
                    )
                qop = "auth"  # downgrade

        # Response
        if qop in ("auth", "auth-int"):
            response_hash = hashlib.md5(
                f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()
            ).hexdigest()
        else:
            response_hash = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
            qop = ""

        # Build header
        auth_parts = [
            f'username="{username}"',
            f'realm="{realm}"',
            f'nonce="{nonce}"',
            f'uri="{uri}"',
            f'response="{response_hash}"',
        ]

        if qop:
            auth_parts.extend([f"qop={qop}", f"nc={nc}", f'cnonce="{cnonce}"'])

        if opaque:
            auth_parts.append(f'opaque="{opaque}"')

        if algorithm != "MD5":
            auth_parts.append(f"algorithm={algorithm}")

        return "Digest " + ", ".join(auth_parts)

    async def process_request(self, request: Request, spider: "Spider") -> MiddlewareResult:
        """Add Authorization header to request if using Basic auth."""
        # Get auth type for this request
        auth_type = request.meta.get("auth_type", self.auth_type)

        # Only add proactive auth for Basic
        if auth_type != "basic":
            return MiddlewareResult.continue_()

        # Check for per-request credentials
        auth_tuple = request.meta.get("auth")
        if auth_tuple is None:
            # Fall back to domain-based credentials
            domain = self._get_domain(request.url)
            auth_tuple = self._credentials.get(domain)

        if auth_tuple is None:
            return MiddlewareResult.continue_()

        # Validate credentials
        if not isinstance(auth_tuple, (tuple, list)) or len(auth_tuple) != 2:
            logger.warning(
                "Invalid auth credentials for %s: expected (username, password) tuple", request.url
            )
            return MiddlewareResult.continue_()

        username, password = auth_tuple

        # Build Authorization header
        auth_header = self._encode_basic_auth(username, password)

        # Add to request headers (make a copy before mutating)
        request.headers = dict(request.headers) if request.headers is not None else {}
        request.headers["Authorization"] = auth_header

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Added HTTP Basic auth for %s (user: %s)", request.url, username)

        return MiddlewareResult.continue_()

    async def process_response(
        self, request: Request, response: Page, spider: "Spider"
    ) -> MiddlewareResult:
        """Handle 401 responses for Digest authentication.

        - Parses WWW-Authenticate: Digest
        - Builds Authorization header
        - Retries request with auth
        - Skips qop=auth-int unless explicitly enabled
        """
        # Only handle 401 for Digest auth
        if response.status_code != 401:
            return MiddlewareResult.keep(response)

        auth_type = request.meta.get("auth_type", self.auth_type)
        if auth_type != "digest":
            return MiddlewareResult.keep(response)

        # Prevent infinite retry loop
        if request.meta.get("_digest_retry"):
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Already retried with Digest auth for %s; not retrying", request.url)

            return MiddlewareResult.keep(response)

        # Get credentials (per-request or per-domain)
        auth_tuple = request.meta.get("auth")
        if auth_tuple is None:
            domain = self._get_domain(request.url)
            auth_tuple = self._credentials.get(domain)

        if auth_tuple is None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("No credentials for 401 response from %s", request.url)

            return MiddlewareResult.keep(response)

        if not isinstance(auth_tuple, (tuple, list)) or len(auth_tuple) != 2:
            logger.warning("Invalid auth tuple for %s: %r", request.url, auth_tuple)
            return MiddlewareResult.keep(response)

        username, password = auth_tuple

        # Parse WWW-Authenticate header
        www_auth = response.headers.get("WWW-Authenticate") or response.headers.get(
            "www-authenticate", ""
        )
        if not isinstance(www_auth, str):
            www_auth = str(www_auth) if www_auth else ""

        if not www_auth.startswith("Digest "):
            logger.warning("Expected Digest challenge, got: %s", www_auth)
            return MiddlewareResult.keep(response)

        # Parse challenge
        challenge = self._parse_digest_challenge(www_auth)
        if not challenge:
            logger.warning("Failed to parse Digest challenge from %s", request.url)
            return MiddlewareResult.keep(response)

        # Cache challenge per domain
        domain = self._get_domain(request.url)
        self._digest_challenges[domain] = challenge

        # Prepare URI and method
        method = (request.method or "GET").upper()
        parsed = urlparse(request.url)
        uri = parsed.path or "/"
        if parsed.query:
            uri += "?" + parsed.query

        # Build Digest response
        auth_header = self._build_digest_response(
            username=username,
            password=password,
            method=method,
            uri=uri,
            challenge=challenge,
            request=request,
        )
        if not auth_header:
            logger.warning("Failed to build Digest Authorization for %s", request.url)
            return MiddlewareResult.keep(response)

        # Clone request with auth header
        new_req = request.copy()
        new_req.headers = dict(new_req.headers or {})
        new_req.headers["Authorization"] = auth_header
        new_req.meta = dict(new_req.meta)
        new_req.meta["_digest_retry"] = True

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Retrying %s with Digest auth (user: %s)", request.url, username)

        return MiddlewareResult.retry(new_req)

    async def process_exception(
        self, request: Request, exception: BaseException, spider: "Spider"
    ) -> MiddlewareResult:
        """No special exception handling for HTTP auth."""
        return MiddlewareResult.continue_()

    def add_credentials(self, domain: str, username: str, password: str):
        """Add credentials for a domain."""
        self._credentials[domain.lower()] = (username, password)

    def remove_credentials(self, domain: str):
        """Remove credentials for a domain."""
        self._credentials.pop(domain.lower(), None)
        self._digest_challenges.pop(domain.lower(), None)

    def clear_credentials(self):
        """Clear all stored credentials."""
        self._credentials.clear()
        self._digest_challenges.clear()

    async def open_spider(self, spider: "Spider") -> None:
        logger.info(
            "credentials: %d domains, auth_type: %s, digest_qop_auth_int: %s",
            len(self._credentials),
            self.auth_type,
            self.digest_qop_auth_int,
        )
