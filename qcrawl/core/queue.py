from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qcrawl.core.request import Request


class RequestQueue(ABC):
    """Abstract asynchronous request queue.

    Implementations must provide `put`, `get`, `size` and `clear`. The
    queue is used by the scheduler/engine to enqueue and retrieve
    crawl requests in a prioritized, async-friendly manner.

    Concurrency/semantics:
      - `put()` should be non-blocking or awaitable and accept a `priority`.
      - `get()` must block (await) until an item is available or raise
        `asyncio.CancelledError` when the queue is closed/cancelled.
      - `size()` returns the current number of items queued.
      - `clear()` removes all queued items, releasing resources where needed.
    """

    @abstractmethod
    async def put(self, request: Request, priority: int = 0) -> None:
        """Enqueue *request* with optional *priority*.

        Lower numeric values indicate higher priority (consistent with the
        project's scheduler semantics).
        """
        ...

    @abstractmethod
    async def get(self) -> Request:
        """Await and return the next scheduled Request.

        Implementations should block until an item becomes available or
        raise `asyncio.CancelledError` if the consumer should stop.
        """
        ...

    @abstractmethod
    async def size(self) -> int:
        """Return number of items currently queued."""
        ...

    @abstractmethod
    def maxsize(self) -> int:
        """Return the maximum capacity of the queue (0 = unlimited)."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Remove all items from the queue and release any resources."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close queue and release resources."""
        ...

    def __aiter__(self) -> AsyncIterator[Request]:
        return self

    async def __anext__(self) -> Request:
        try:
            return await self.get()
        except asyncio.CancelledError:
            raise StopAsyncIteration from None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} maxsize={self.maxsize()}>"
