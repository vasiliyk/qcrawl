import posixpath

from yarl import URL


def _canonical_netloc(u: URL) -> tuple[str | None, int | None, str]:
    """Return (host, port, scheme) normalized for building canonical netloc."""
    scheme = (u.scheme or "").lower()
    host = u.host or None
    if host is not None:
        host = host.lower()
    port = u.port
    # drop default ports
    if port is not None and (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        port = None
    return host, port, scheme


def get_domain(url: str) -> str:
    """Return normalized domain string for `url`: `host` or `host:port` (lower-cased, no userinfo)."""
    try:
        u = URL(url)
        host, port, _ = _canonical_netloc(u)
        if not host:
            return ""
        return host if port is None else f"{host}:{port}"
    except Exception:
        # If yarl fails to parse, return empty domain to indicate unknown host.
        return ""


def get_domain_base(url: str) -> str:
    """Return a base URL suitable for robots.txt lookups: scheme://host

    - If host is missing return a permissive default 'https://'
    - Uses same canonicalization as `get_domain` for scheme/host lowercasing
    - Omits userinfo and default ports
    """
    try:
        u = URL(url)
        host, _, scheme = _canonical_netloc(u)
        if not host:
            return "https://"
        scheme = scheme or "https"
        return f"{scheme}://{host}"
    except Exception:
        # Conservative default when parsing fails
        return "https://"


def normalize_url(url: str) -> str:
    """Normalize a URL for canonical comparison.

    Behaviors:
      - Lower-case scheme and host
      - Strip userinfo
      - Remove default ports (80/443)
      - Collapse duplicate slashes and resolve . / ..
      - Remove trailing slash except for root
      - Remove fragment
      - Preserve query string as-is
    """
    u = URL(url)

    host, port, scheme = _canonical_netloc(u)

    # Normalize path: collapse // and resolve . and .. while keeping leading slash
    raw_path = u.path or "/"
    norm_path = posixpath.normpath(raw_path)
    if not norm_path.startswith("/"):
        norm_path = "/" + norm_path
    if norm_path != "/" and norm_path.endswith("/"):
        norm_path = norm_path.rstrip("/")

    query = u.query_string or ""

    # If we have a host, build a full absolute URL; otherwise return path[?query]
    if host:
        built = URL.build(scheme=scheme or "", host=host, port=port, path=norm_path, query=query)
        return str(built)  # fragment omitted by construction
    else:
        return norm_path + (f"?{query}" if query else "")


def join_and_normalize(base_url: str, href: str) -> str:
    """Resolve `href` against `base_url` and normalize the resulting URL."""
    try:
        joined = URL(base_url).join(URL(href))
        joined_str = str(joined)
    except Exception:
        # Try interpreting href alone (it may already be absolute)
        try:
            joined_str = str(URL(href))
        except Exception:
            # Last-resort fallback to a simple path concatenation
            joined_str = base_url.rstrip("/") + "/" + href.lstrip("/")

    return normalize_url(joined_str)
