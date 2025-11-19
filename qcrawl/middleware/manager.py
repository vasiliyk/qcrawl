import inspect
from collections.abc import AsyncGenerator, AsyncIterable
from typing import TYPE_CHECKING

from qcrawl.core.response import Page
from qcrawl.middleware.base import (
    Action,
    DownloaderMiddleware,
    MiddlewareResult,
    SpiderMiddleware,
)

if TYPE_CHECKING:
    from qcrawl.core.item import Item
    from qcrawl.core.request import Request
    from qcrawl.core.spider import Spider


class MiddlewareManager:
    """Coordinate downloader and spider middleware chains.

    The manager accepts two middleware stacks:
      - downloader: list of DownloaderMiddleware — called during request/response/exception phases
        in the same order as registered for `process_request` and in reversed order for
        `process_response`/`process_exception`.
      - spider: list of SpiderMiddleware — called for spider-facing phases. Each spider
        middleware method must return an *async iterable* (async-generator) when it returns
        a non-None value.

    This class performs strict validation of middleware contracts and raises informative
    `TypeError` messages when middleware violates the required return types.
    """

    def __init__(
        self,
        downloader: list[DownloaderMiddleware] | None = None,
        spider: list[SpiderMiddleware] | None = None,
    ) -> None:
        self.downloader: list[DownloaderMiddleware] = downloader or []
        self.spider: list[SpiderMiddleware] = spider or []

    async def process_request(self, request: "Request", spider: "Spider") -> MiddlewareResult:
        """Run downloader `process_request` chain.

        Behavior:
          - Call each downloader middleware in registration order.
          - Each middleware must return a `MiddlewareResult`.
          - If result.action is `Action.CONTINUE` the chain proceeds to the next middleware.
          - Any other action is returned immediately to the caller.
        """
        for mw in self.downloader:
            result = await mw.process_request(request, spider)
            if not isinstance(result, MiddlewareResult):
                raise TypeError(
                    f"{mw!r}.process_request must return MiddlewareResult, got {type(result)!r}"
                )
            if result.action is Action.CONTINUE:
                continue
            return result
        return MiddlewareResult.continue_()

    async def process_response(
        self, request: "Request", response: "Page", spider: "Spider"
    ) -> MiddlewareResult:
        """Run downloader `process_response` chain in reverse order.

        Each middleware may:
        - return `MiddlewareResult.CONTINUE` to let the previous middleware
          in reversed order handle the response,
        - return `MiddlewareResult.KEEP` with a replacement `Page` payload,
        - return `MiddlewareResult.RETRY` or `MiddlewareResult.DROP` to short-circuit.
        """
        current: Page = response

        for mw in reversed(self.downloader):
            result = await mw.process_response(request, current, spider)
            if not isinstance(result, MiddlewareResult):
                raise TypeError(
                    f"{mw!r}.process_response must return MiddlewareResult, got {type(result)!r}"
                )

            if result.action is Action.CONTINUE:
                continue

            if result.action is Action.KEEP:
                payload = result.payload
                if not isinstance(payload, Page):
                    raise TypeError("MiddlewareResult.keep payload must be a Page")
                current = payload
                continue

            if result.action in (Action.RETRY, Action.DROP):
                return result

        return MiddlewareResult.keep(current)

    async def process_exception(
        self, request: "Request", exception: BaseException, spider: "Spider"
    ) -> MiddlewareResult:
        """Run downloader `process_exception` chain in reverse order.

        Behavior:
          - Called when the downloader raised an exception.
          - Middleware may return RETRY/DROP/CONTINUE/KEEP semantics using `MiddlewareResult`.
          - First non-CONTINUE result is returned.
        """

        for mw in reversed(self.downloader):
            result = await mw.process_exception(request, exception, spider)
            if not isinstance(result, MiddlewareResult):
                raise TypeError(
                    f"{mw!r}.process_exception must return MiddlewareResult, got {type(result)!r}"
                )
            if result.action is Action.CONTINUE:
                continue
            return result
        return MiddlewareResult.continue_()

    def process_start_requests(
        self, start_requests: AsyncIterable["Request"], spider: "Spider"
    ) -> AsyncGenerator["Request", None]:
        async def _gen() -> AsyncGenerator["Request", None]:
            ag: AsyncIterable[Request] = start_requests
            for mw in self.spider:
                proc = getattr(mw, "process_start_requests", None)
                if proc is None:
                    continue
                res = proc(ag, spider)
                # Support coroutine-returning implementations by awaiting them
                if inspect.isawaitable(res):
                    res = await res
                if res is None:
                    continue
                if not hasattr(res, "__aiter__"):
                    raise TypeError(f"{mw!r}.process_start_requests must return an async iterable")
                ag = res
            async for request in ag:
                yield request

        return _gen()

    async def process_spider_input(self, response: "Page", spider: "Spider") -> Exception | None:
        """Run spider `process_spider_input` hooks.

        Called before passing a `Page` to the spider parse coroutine. If a middleware
        returns a non-None `Exception`, parsing is short-circuited and the exception is
        propagated to the engine.
        """
        for mw in self.spider:
            result = await mw.process_spider_input(response, spider)
            if result is not None:
                return result
        return None

    def process_spider_output(
        self,
        response: "Page",
        result: AsyncGenerator["Item | Request | str", None],  # ← ONLY AsyncGenerator
        spider: "Spider",
    ) -> AsyncGenerator["Item | Request | str", None]:
        """Apply spider output middlewares to the spider's parse output stream.

        Contract
        - `result` must be an async iterable (an async-generator) yielding `Item | Request | str`.
        - Each spider middleware's `process_spider_output(response, ag, spider)` may:
            - return `None` to indicate "no change" (passthrough), or
            - return an async iterable (async-generator) which replaces/wraps the incoming stream.
        """

        async def _gen() -> AsyncGenerator["Item | Request | str", None]:
            ag: AsyncGenerator[Item | Request | str, None] = result
            for mw in self.spider:
                proc = getattr(mw, "process_spider_output", None)
                if proc is None:
                    continue
                res = proc(response, ag, spider)
                if res is None:
                    continue
                if not hasattr(res, "__aiter__"):
                    raise TypeError(
                        f"{mw!r}.process_spider_output must return async generator or None"
                    )
                ag = res
            async for item in ag:
                yield item

        return _gen()

    async def process_spider_exception(
        self, response: "Page", exception: BaseException, spider: "Spider"
    ) -> AsyncGenerator["Item | Request | str", None] | None:
        """Run spider `process_spider_exception` hooks.

        Behavior:
          - Walk spider middleware in registration order and call `process_spider_exception`.
          - If a middleware returns a non-None value it must be an async iterable; that
            async iterable is returned immediately and will be consumed by the caller.
          - If no middleware handles the exception, returns `None`.
        """
        for mw in self.spider:
            proc = getattr(mw, "process_spider_exception", None)
            if proc is None:
                continue
            res = proc(response, exception, spider)
            # Support coroutine-returning implementations by awaiting them
            if inspect.isawaitable(res):
                res = await res
            if res is None:
                continue
            if not hasattr(res, "__aiter__"):
                raise TypeError(
                    f"{mw!r}.process_spider_exception must return None or an async iterable"
                )

            async def _wrap(
                ag: AsyncIterable["Item | Request | str"],
            ) -> AsyncGenerator["Item | Request | str", None]:
                async for r in ag:
                    yield r

            return _wrap(res)
        return None

    def __repr__(self) -> str:
        return f"MiddlewareManager(downloader={len(self.downloader)}, spider={len(self.spider)})"
