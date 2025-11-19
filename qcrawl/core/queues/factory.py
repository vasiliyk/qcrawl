from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from qcrawl.core.queue import RequestQueue
from qcrawl.core.queues.memory import MemoryPriorityQueue

# Allowed keyword arguments per backend; used to filter `**kwargs` so that
# backend constructors only receive supported parameters.
_ALLOWED_KWARGS: dict[str, Iterable[str]] = {
    "memory": {"maxsize"},
    "redis": {"url", "key", "username", "password", "maxsize"},
}


def _filter_kwargs(allowed: Iterable[str], kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new dict containing only keys from `kwargs` that are in `allowed`."""
    return {k: v for k, v in kwargs.items() if k in allowed}


def create_queue(backend: str = "memory", **kwargs: Any) -> RequestQueue:
    """
    Create and return a `RequestQueue` implementation for the given backend name.

    Args:
        backend: Backend identifier (case-insensitive). Supported values:
            - "memory" (default)
            - "redis"  (optional; requires redis extras to be installed)
        **kwargs: Keyword arguments; only backend-supported keys are forwarded.

    Returns:
        Instance of `RequestQueue`.

    Raises:
        ValueError: If `backend` is unrecognized.
        ImportError: If an optional backend (e.g. redis) is selected but required
                     extras are not installed.
        TypeError/ValueError: Propagated from backend constructor for invalid args.
    """
    if not backend:
        backend = "memory"
    backend_name = backend.lower().strip()

    if backend_name == "memory":
        allowed = _ALLOWED_KWARGS["memory"]
        filtered = _filter_kwargs(allowed, kwargs)
        return MemoryPriorityQueue(**filtered)

    if backend_name == "redis":
        # Lazy import to avoid hard dependency when redis support is optional.
        try:
            from qcrawl.core.queues.redis import RedisQueue  # imported only when needed
        except Exception as exc:  # pragma: no cover - depends on optional extras
            raise ImportError(
                "Redis backend requested but redis extras are not available. "
                "Install with: pip install 'qcrawl[redis]'"
            ) from exc

        allowed = _ALLOWED_KWARGS["redis"]
        filtered = _filter_kwargs(allowed, kwargs)
        return RedisQueue(**filtered)

    # Unknown backend: fail fast with a helpful message listing supported backends.
    supported = ", ".join(sorted(_ALLOWED_KWARGS.keys()))
    raise ValueError(f"Unknown queue backend: {backend!r}. Supported: {supported}")
