import asyncio
import inspect
import logging
import weakref
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

SUPPORTED_SIGNALS: list[str] = [
    # Spider lifecycle
    "spider_opened",
    "spider_closed",
    "spider_idle",
    "spider_error",
    # Request/Response lifecycle
    "request_scheduled",
    "request_dropped",
    "request_reached_downloader",
    "request_failed",
    "response_received",
    # Item lifecycle
    "item_scraped",
    "item_dropped",
    "item_error",
    # Bytes/headers tracking
    "bytes_received",
    "headers_received",
]


class _HandlerRef:
    """Lightweight wrapper representing a registered signal handler.

    Features:
      - Hold either a strong reference to the callable or a weak reference
        (WeakMethod for bound methods / weakref ref for functions) to avoid leaks.
      - Track `priority` used for ordering delivery (higher executes first).
      - Optionally restrict delivery to a single `sender_filter` (identity match).
    """

    def __init__(
        self,
        fn: Callable[..., Awaitable[object | None]],
        *,
        weak: bool = True,
        priority: int = 0,
        sender_filter: object = None,  # CrawlEngine | Downloader | Spider | Scheduler | None
    ) -> None:
        self._strong: Callable[..., Awaitable[object | None]] | None = None
        self._ref: weakref.ref[Callable[..., Awaitable[object | None]]] | None = None
        self.priority: int = priority
        self.sender_filter: object = sender_filter

        if weak:
            if hasattr(fn, "__self__") and fn.__self__ is not None:
                self._ref = weakref.WeakMethod(fn)
            else:
                self._ref = weakref.ref(fn)
        else:
            self._strong = fn

    def resolve(self) -> Callable[..., Awaitable[object | None]] | None:
        if self._strong is not None:
            return self._strong
        if self._ref is None:
            return None
        return self._ref()

    def equals(self, other_fn: Callable[..., Awaitable[object | None]]) -> bool:
        cur = self.resolve()
        return cur is other_fn

    def matches_sender(self, sender: object) -> bool:
        if self.sender_filter is None:
            return True
        return self.sender_filter is sender


class SignalRegistry:
    """Central registry of signal handlers and executor for dispatching signals.

    Features:
      - Maintain handler lists per supported signal with sender-based filtering
        and priority ordering.
      - Provide sequential or concurrent delivery with optional concurrency limiting.
      - Perform cleanup of dead (garbage-collected) weak references.

    Features:
        - Priority-based handler execution
        - Sender filtering
        - Return value collection
        - Weak/strong references
        - Concurrent delivery with rate limiting

    Notes:
      - Handlers must be `async def` coroutines; connect() enforces this.
      - Sender filtering is by identity (``is``).
      - Weak references are cleaned lazily during handler collection.
    """

    def __init__(self, *, max_concurrency: int | None = None) -> None:
        self._handlers: dict[str, list[_HandlerRef]] = {name: [] for name in SUPPORTED_SIGNALS}
        self._max_concurrency: int | None = max_concurrency

    def connect(
        self,
        signal: str,
        handler: Callable[..., Awaitable[object | None]],
        *,
        weak: bool = True,
        priority: int = 0,
        sender: object = None,  # CrawlEngine | Downloader | Spider | Scheduler | None
    ) -> None:
        """Register an async handler for `signal`.

        Args:
            signal: Name of the signal (must be in SUPPORTED_SIGNALS).
            handler: Async callable invoked as `await handler(sender, *args, **kwargs)`.
            weak: Store a weak reference to the handler when possible (default True).
            priority: Handlers with higher priority run earlier.
            sender: If provided, the handler only receives events for that exact sender.

        Raises:
            ValueError: if signal is unknown.
            TypeError: if handler is not an async function.
        """
        if signal not in self._handlers:
            raise ValueError(f"Unknown signal: {signal!r}")
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("Signal handlers must be `async def` callables")

        # Avoid duplicates
        for hr in self._handlers[signal]:
            if hr.equals(handler) and hr.sender_filter is sender:
                return

        ref = _HandlerRef(handler, weak=weak, priority=priority, sender_filter=sender)
        self._handlers[signal].append(ref)
        self._handlers[signal].sort(key=lambda h: h.priority, reverse=True)

    def disconnect(
        self,
        signal: str,
        handler: Callable[..., Awaitable[object | None]],
        *,
        sender: object = None,
    ) -> None:
        """Unregister a previously connected handler.

        If `sender` is provided only remove the registration that matches that sender
        (identity). Dead (collected) handler references are ignored/cleaned.
        """
        if signal not in self._handlers:
            return
        self._handlers[signal] = [
            hr
            for hr in self._handlers[signal]
            if not (hr.equals(handler) and (sender is None or hr.sender_filter is sender))
            if hr.resolve() is not None
        ]

    def disconnect_all(self, signal: str, *, sender: object = None) -> None:
        """Remove all handlers for `signal`. If `sender` is provided only handlers
        registered for that sender are removed.
        """
        if signal not in self._handlers:
            return
        if sender is None:
            self._handlers[signal] = []
        else:
            self._handlers[signal] = [
                hr
                for hr in self._handlers[signal]
                if hr.sender_filter is not sender or hr.resolve() is None
            ]

    def _collect_handlers(
        self, signal: str, sender: object
    ) -> list[Callable[..., Awaitable[object | None]]]:
        """Return a list of live handler callables for `signal` filtered by `sender`.

        Also performs cleanup of dead/collected handler references.
        """
        if signal not in self._handlers:
            return []

        out: list[Callable[..., Awaitable[object | None]]] = []
        alive: list[_HandlerRef] = []
        needs_cleanup = False

        for hr in self._handlers[signal]:
            fn = hr.resolve()
            if fn is None:
                needs_cleanup = True
                continue
            alive.append(hr)
            if hr.matches_sender(sender):
                out.append(fn)

        if needs_cleanup:
            self._handlers[signal] = alive

        return out

    async def send_async(
        self,
        signal: str,
        *args: object,
        concurrent: bool = False,
        max_concurrency: int | None = None,
        sender: object = None,
        raise_exceptions: bool = False,
        **kwargs: object,
    ) -> list[object]:
        """Emit `signal` to matching handlers and collect non-None results.

        Args:
            signal: Signal name.
            *args/**kwargs: Payload forwarded to each handler after the `sender` arg.
            concurrent: If False (default) call handlers sequentially in priority order.
                        If True run handlers concurrently.
            max_concurrency: Optional limit for concurrent handler coroutines (overrides registry default).
            sender: Sender object used for sender-filtering (identity).
            raise_exceptions: If True propagate exceptions.md from handlers; otherwise exceptions.md are logged and swallowed.

        Returns:
            List of non-None values returned by handlers (order preserved for sequential delivery,
            unspecified order for concurrent delivery).
        """
        handlers = self._collect_handlers(signal, sender)
        if not handlers:
            return []

        async def _execute(handler: Callable[..., Awaitable[object | None]]) -> object | None:
            try:
                coro = handler(sender, *args, **kwargs)
                if not inspect.isawaitable(coro):
                    logger.warning("Handler for %s didn't return awaitable", signal)
                    return None
                return await coro
            except Exception as exc:
                logger.exception("Signal handler %s failed", signal, exc_info=exc)
                if raise_exceptions:
                    raise
                return None

        if not concurrent:
            results: list[object] = []
            for h in handlers:
                res = await _execute(h)
                if res is not None:
                    results.append(res)
            return results

        limit = max_concurrency if max_concurrency is not None else self._max_concurrency
        sem = asyncio.Semaphore(limit) if limit else None

        async def _run(h: Callable[..., Awaitable[object | None]]) -> object | None:
            if sem:
                async with sem:
                    return await _execute(h)
            return await _execute(h)

        handler_results = await asyncio.gather(
            *[_run(h) for h in handlers], return_exceptions=False
        )
        return [r for r in handler_results if r is not None]

    def for_sender(self, sender: object) -> "SignalDispatcher":
        """Return a SignalDispatcher bound to `sender`. The dispatcher proxies connect/disconnect/send
        calls and defaults sender parameters to the bound sender.
        """
        return SignalDispatcher(self, sender, max_concurrency=self._max_concurrency)


class SignalDispatcher:
    """Sender-bound proxy that forwards connect/disconnect/send calls to a SignalRegistry.

    Features:
      - Reduce boilerplate by defaulting `sender` arguments to the dispatcher's bound sender.
      - Optionally carry a dispatcher-level `max_concurrency` override for concurrent sends.

    Notes:
      - connect/ disconnect/ disconnect_all mirror the registry API but default `sender=None`
        to the dispatcher's bound sender.
      - send_async(...) forwards to SignalRegistry.send_async with `sender` set to the bound sender
        and uses the dispatcher's `max_concurrency` when caller does not provide one.
    """

    def __init__(
        self,
        registry: SignalRegistry,
        sender: object,
        *,
        max_concurrency: int | None = None,
    ) -> None:
        self._registry = registry
        self._sender = sender
        self._max_concurrency = max_concurrency

    def connect(
        self,
        signal: str,
        handler: Callable[..., Awaitable[object | None]],
        *,
        weak: bool = True,
        priority: int = 0,
        sender: object = None,
    ) -> None:
        """Connect handler for `signal`. If `sender` is None it defaults to the dispatcher's bound sender."""
        filt = self._sender if sender is None else sender
        self._registry.connect(signal, handler, weak=weak, priority=priority, sender=filt)

    def disconnect(
        self,
        signal: str,
        handler: Callable[..., Awaitable[object | None]],
        *,
        sender: object = None,
    ) -> None:
        """Disconnect handler for `signal`. If `sender` is None it defaults to the dispatcher's bound sender."""
        filt = self._sender if sender is None else sender
        self._registry.disconnect(signal, handler, sender=filt)

    def disconnect_all(self, signal: str) -> None:
        """Remove all handlers registered for this dispatcher's bound sender for `signal`."""
        self._registry.disconnect_all(signal, sender=self._sender)

    async def send_async(
        self,
        signal: str,
        *args: object,
        concurrent: bool = False,
        max_concurrency: int | None = None,
        raise_exceptions: bool = False,
        **kwargs: object,
    ) -> list[object]:
        """Send `signal` filtered to the dispatcher's bound sender.

        Forwards arguments to SignalRegistry.send_async, using the dispatcher's
        `max_concurrency` as the default concurrency limit if `max_concurrency` is omitted.
        """
        return await self._registry.send_async(
            signal,
            *args,
            concurrent=concurrent,
            max_concurrency=max_concurrency or self._max_concurrency,
            sender=self._sender,
            raise_exceptions=raise_exceptions,
            **kwargs,
        )


# === Global Instance ===
signals_registry = SignalRegistry()
signals_dispatcher = signals_registry.for_sender(None)  # global fallback


# === Public API ===
__all__ = [
    "SignalRegistry",
    "SignalDispatcher",
    "signals_registry",
    "signals_dispatcher",
    "SUPPORTED_SIGNALS",
]
