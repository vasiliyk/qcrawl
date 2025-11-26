"""Tests for qcrawl.core.queues.memory.MemoryPriorityQueue"""

import asyncio

import pytest

from qcrawl.core.queues.memory import MemoryPriorityQueue
from qcrawl.core.request import Request


def test_init_validation_raises_on_invalid_args() -> None:
    """Test that invalid constructor arguments raise appropriate errors."""
    with pytest.raises(ValueError):
        MemoryPriorityQueue(maxsize=-1)

    with pytest.raises(TypeError):
        # unexpected kwargs should surface as TypeError
        MemoryPriorityQueue(foo=1)


@pytest.mark.asyncio
async def test_put_get_order_and_fifo_tiebreak() -> None:
    q = MemoryPriorityQueue()

    r_low = Request(url="http://low.example")  # → http://low.example/
    r_p5 = Request(url="http://p5.example")  # → http://p5.example/
    r_p1_a = Request(url="http://p1-a.example")  # → http://p1-a.example/
    r_p1_b = Request(url="http://p1-b.example")  # → http://p1-b.example/

    await q.put(r_low, priority=5)
    await q.put(r_p1_a, priority=1)
    await q.put(r_p1_b, priority=1)
    await q.put(r_p5, priority=5)

    # Use the normalized URLs with trailing slash!
    assert (await q.get()).url == "http://p1-a.example/"
    assert (await q.get()).url == "http://p1-b.example/"
    assert (await q.get()).url == "http://low.example/"
    assert (await q.get()).url == "http://p5.example/"


@pytest.mark.asyncio
async def test_clear_and_size_behavior() -> None:
    """Test queue size tracking and clear() functionality."""
    q = MemoryPriorityQueue()

    await q.put(Request(url="http://one"), priority=0)
    await q.put(Request(url="http://two"), priority=0)

    assert await q.size() == 2

    await q.clear()
    assert await q.size() == 0


@pytest.mark.asyncio
async def test_close_makes_put_noop_and_get_raises_cancelled() -> None:
    """Test that close() makes put() a no-op and get() raises CancelledError when empty."""
    q = MemoryPriorityQueue()

    await q.close()

    # put after close is ignored (no-op)
    await q.put(Request(url="http://ignored"), priority=0)
    assert await q.size() == 0

    # get on closed + empty queue raises CancelledError
    with pytest.raises(asyncio.CancelledError):
        await q.get()


@pytest.mark.asyncio
async def test_get_raises_runtimeerror_on_decode_failure() -> None:
    """Test that deserialization failures are caught and raise RuntimeError."""
    q = MemoryPriorityQueue()

    class BrokenRequest(Request):
        def to_bytes(self) -> bytes:
            return b"this-is-not-valid-serial to_bytes"

        @classmethod
        def from_bytes(cls, data: bytes) -> "BrokenRequest":
            raise RuntimeError("Deserialization failed")

    bad_req = BrokenRequest(url="http://broken.example")

    await q.put(bad_req)

    with pytest.raises(RuntimeError, match="Failed to decode in-memory request payload"):
        await q.get()


@pytest.mark.asyncio
async def test_async_iteration_protocol() -> None:
    """Test RequestQueue async iteration protocol (__aiter__, __anext__)."""
    q = MemoryPriorityQueue()

    await q.put(Request(url="http://first.example"), priority=0)
    await q.put(Request(url="http://second.example"), priority=0)
    await q.close()

    urls = []
    async for req in q:
        urls.append(req.url)

    assert len(urls) == 2
    assert "first.example" in urls[0]
    assert "second.example" in urls[1]


def test_repr() -> None:
    """Test RequestQueue.__repr__ shows class name and maxsize."""
    q = MemoryPriorityQueue(maxsize=50)
    repr_str = repr(q)

    assert "MemoryPriorityQueue" in repr_str
    assert "maxsize=50" in repr_str
