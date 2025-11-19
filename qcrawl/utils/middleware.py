from qcrawl.core.request import Request
from qcrawl.utils.url import get_domain


def get_meta(request: Request) -> dict[str, object]:
    """Return the request's meta mapping, failing fast if it's missing or malformed.

    This helper enforces that `request.meta` is an actual `dict` and never
    silently creates or mutates it.

    Args:
        request: A `Request` instance expected to have a `meta` attribute.

    Returns:
        The `request.meta` dictionary.

    Raises:
        TypeError: If `request.meta` is `None` or is present but not a `dict`.
    """
    meta = getattr(request, "meta", None)
    if meta is None:
        raise TypeError("request.meta must be dict, got None")
    if not isinstance(meta, dict):
        raise TypeError(f"request.meta must be dict, got {type(meta).__name__}")
    return meta


def clone_request_with_meta(request: Request, **overrides) -> Request:
    """Clone a Request via Request.copy(...) and copy its meta dict so the clone
    does not share mutable state with the original.
    Any keyword args are forwarded to Request.copy.
    """
    new_req = request.copy(**overrides)
    new_req.meta = dict(new_req.meta or {})
    return new_req


def get_domain_key(url: str) -> str:
    """Return a stable domain key suitable for per-domain maps/semaphores.
    Falls back to 'default' when domain parsing raises TypeError or ValueError.
    """
    try:
        d = get_domain(url)
    except (TypeError, ValueError):
        return "default"
    return d or "default"
