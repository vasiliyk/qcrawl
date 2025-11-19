import asyncio
import contextlib
import logging
from itertools import count

from qcrawl.core.queue import RequestQueue
from qcrawl.core.request import Request

logger = logging.getLogger(__name__)


class MemoryPriorityQueue(RequestQueue):
    """In-memory implementation of `RequestQueue` using `asyncio.PriorityQueue`.

    Storage format:
      - Items are stored as tuples `(priority: int, counter: int, request: Request)`.
      - Lower numeric `priority` values are processed first.
      - `counter` (monotonic integer) preserves FIFO order among items with identical priority.

    Concurrency:
      - Built with asyncio primitives and intended to be used from a single event loop.
      - FIFO tie-breaking for equal priority is preserved even with concurrent producers/consumers.

    Errors:
      - Raises `ValueError` if `maxsize < 0`.
      - Unexpected keyword arguments at construction raise `TypeError`.
    """

    def __init__(self, maxsize: int = 0, **kwargs) -> None:
        if maxsize < 0:
            raise ValueError("maxsize must be >= 0")
        if kwargs:
            keys = ", ".join(str(k) for k in kwargs)
            raise TypeError(f"Unexpected keyword argument(s) for MemoryQueue: {keys}")

        # lower numeric priority => processed first
        self._pq: asyncio.PriorityQueue[tuple[int, int, Request]] = asyncio.PriorityQueue(
            maxsize=maxsize
        )
        self._counter = count()
        self._closed: bool = False

    async def put(self, request: Request, priority: int = 0) -> None:
        """Enqueue `request` with the given `priority`.

        Lower numeric values indicate higher priority. If the queue is closed,
        the call is ignored (no-op). Otherwise this call awaits until space is available.
        """
        if self._closed:
            logger.debug(
                "Put called after close(); ignoring request: %s", getattr(request, "url", None)
            )
            return
        await self._pq.put((priority, next(self._counter), request))

    async def get(self) -> Request:
        """Await and return the next `Request`.

        Behavior:
          - If items exist, return the highest-priority item (lowest numeric priority).
          - If queue is closed and empty, raise `asyncio.CancelledError` to indicate shutdown.

        Note: callers should call `task_done()` semantics are handled internally where possible.
        """
        if self._closed and self._pq.empty():
            raise asyncio.CancelledError
        _, _, request = await self._pq.get()
        try:
            return request
        finally:
            with contextlib.suppress(Exception):
                self._pq.task_done()

    async def size(self) -> int:
        """Return the number of items currently queued (non-blocking)."""
        return int(self._pq.qsize())

    def maxsize(self) -> int:
        """Return the queue's maximum capacity.

        Returns:
            int: Maximum number of items the queue can hold. A value of `0`
            denotes an unbounded queue (no fixed capacity).
        """
        return self._pq.maxsize

    async def clear(self) -> None:
        """Remove all queued items, draining synchronously."""
        while True:
            try:
                self._pq.get_nowait()
                with contextlib.suppress(Exception):
                    self._pq.task_done()
            except asyncio.QueueEmpty:
                break

    async def close(self) -> None:
        """Mark the queue closed.

        After calling:
          - `put()` becomes a no-op.
          - `get()` will return remaining items until the queue is drained, then raise
            `asyncio.CancelledError` to notify consumers to stop.
        """
        self._closed = True

    def __repr__(self) -> str:
        return f"<MemoryQueue size={self._pq.qsize()} maxsize={self._pq.maxsize} closed={self._closed}>"
