"""Tests for qcrawl.signals - Signal registry and dispatcher behavior

Tests focus on the following behavior:
- Handler registration with weak/strong refs and priority ordering
- Signal emission (sequential vs concurrent) with result collection
- Error handling (invalid signals, non-async handlers, exceptions)
- Weak reference cleanup for garbage-collected handlers
- SignalDispatcher sender-bound proxy
- Sender filtering
"""

import asyncio
import gc

import pytest

from qcrawl.signals import SUPPORTED_SIGNALS, SignalRegistry

# Handler Registration Tests


@pytest.mark.asyncio
async def test_connect_registers_handler():
    """connect() registers async handler for signal."""
    registry = SignalRegistry()
    call_log = []

    async def handler(sender, **kwargs):
        call_log.append("called")

    registry.connect("spider_opened", handler)

    await registry.send_async("spider_opened")

    assert call_log == ["called"]


@pytest.mark.asyncio
async def test_connect_raises_on_unknown_signal():
    """connect() raises ValueError for unknown signal."""
    registry = SignalRegistry()

    async def handler(sender):
        pass

    with pytest.raises(ValueError, match="Unknown signal: 'invalid_signal'"):
        registry.connect("invalid_signal", handler)


@pytest.mark.asyncio
async def test_connect_raises_on_non_async_handler():
    """connect() raises TypeError for non-async handler."""
    registry = SignalRegistry()

    def sync_handler(sender):  # Not async
        pass

    with pytest.raises(TypeError, match="must be `async def` callables"):
        registry.connect("spider_opened", sync_handler)


@pytest.mark.asyncio
async def test_connect_avoids_duplicate_handlers():
    """connect() avoids registering duplicate handler for same signal/sender."""
    registry = SignalRegistry()
    call_count = []

    async def handler(sender):
        call_count.append(1)

    # Register same handler twice
    registry.connect("spider_opened", handler)
    registry.connect("spider_opened", handler)

    await registry.send_async("spider_opened")

    assert len(call_count) == 1, "Should only register handler once"


@pytest.mark.asyncio
async def test_connect_priority_ordering():
    """connect() orders handlers by priority (higher executes first)."""
    registry = SignalRegistry()
    call_order = []

    async def low_priority(sender):
        call_order.append("low")

    async def high_priority(sender):
        call_order.append("high")

    async def medium_priority(sender):
        call_order.append("medium")

    registry.connect("spider_opened", low_priority, priority=1)
    registry.connect("spider_opened", high_priority, priority=10)
    registry.connect("spider_opened", medium_priority, priority=5)

    await registry.send_async("spider_opened")

    assert call_order == ["high", "medium", "low"]


# Sender Filtering Tests


@pytest.mark.asyncio
async def test_sender_filtering_matches_identity():
    """Handlers with sender filter only receive signals from that sender."""
    registry = SignalRegistry()
    sender_a = object()
    sender_b = object()
    calls = []

    async def handler_for_a(sender):
        calls.append(f"a:{id(sender)}")

    async def handler_for_b(sender):
        calls.append(f"b:{id(sender)}")

    async def handler_for_all(sender):
        calls.append("all")

    registry.connect("request_scheduled", handler_for_a, sender=sender_a)
    registry.connect("request_scheduled", handler_for_b, sender=sender_b)
    registry.connect("request_scheduled", handler_for_all)  # No filter

    await registry.send_async("request_scheduled", sender=sender_a)

    assert len(calls) == 2
    assert f"a:{id(sender_a)}" in calls
    assert "all" in calls
    assert f"b:{id(sender_b)}" not in calls


# Signal Emission Tests


@pytest.mark.asyncio
async def test_send_async_sequential_execution():
    """send_async() executes handlers sequentially in priority order."""
    registry = SignalRegistry()
    execution_log = []

    async def handler1(sender):
        execution_log.append("start1")
        await asyncio.sleep(0.01)
        execution_log.append("end1")

    async def handler2(sender):
        execution_log.append("start2")
        await asyncio.sleep(0.01)
        execution_log.append("end2")

    registry.connect("item_scraped", handler1, priority=10)
    registry.connect("item_scraped", handler2, priority=5)

    await registry.send_async("item_scraped", concurrent=False)

    # Sequential: handler1 completes before handler2 starts
    assert execution_log == ["start1", "end1", "start2", "end2"]


@pytest.mark.asyncio
async def test_send_async_concurrent_execution():
    """send_async() with concurrent=True runs handlers concurrently."""
    registry = SignalRegistry()
    execution_log = []

    async def handler1(sender):
        execution_log.append("start1")
        await asyncio.sleep(0.02)
        execution_log.append("end1")

    async def handler2(sender):
        execution_log.append("start2")
        await asyncio.sleep(0.01)
        execution_log.append("end2")

    registry.connect("response_received", handler1)
    registry.connect("response_received", handler2)

    await registry.send_async("response_received", concurrent=True)

    # Concurrent: handler2 finishes before handler1
    assert "start1" in execution_log
    assert "start2" in execution_log
    # Handler2 completes first (shorter sleep)
    assert execution_log.index("end2") < execution_log.index("end1")


@pytest.mark.asyncio
async def test_send_async_collects_non_none_results():
    """send_async() collects and returns non-None handler results."""
    registry = SignalRegistry()

    async def handler_with_result(sender):
        return "result1"

    async def handler_without_result(sender):
        return None

    async def handler_with_result2(sender):
        return "result2"

    registry.connect("bytes_received", handler_with_result)
    registry.connect("bytes_received", handler_without_result)
    registry.connect("bytes_received", handler_with_result2)

    results = await registry.send_async("bytes_received")

    assert results == ["result1", "result2"]


@pytest.mark.asyncio
async def test_send_async_passes_args_and_kwargs():
    """send_async() forwards args and kwargs to handlers."""
    registry = SignalRegistry()
    received_args = []

    async def handler(sender, item, spider, extra=None):
        received_args.append((sender, item, spider, extra))

    registry.connect("item_scraped", handler)

    test_sender = object()
    test_item = {"data": "test"}
    test_spider = "spider_name"

    await registry.send_async(
        "item_scraped", test_item, test_spider, extra="value", sender=test_sender
    )

    assert len(received_args) == 1
    assert received_args[0] == (test_sender, test_item, test_spider, "value")


@pytest.mark.asyncio
async def test_send_async_with_max_concurrency():
    """send_async() respects max_concurrency limit for concurrent execution."""
    registry = SignalRegistry(max_concurrency=2)
    active_count = []
    max_active = [0]  # Use list to allow modification in closure

    async def make_handler(handler_id):
        async def handler(sender):
            active_count.append(handler_id)
            max_active[0] = max(max_active[0], len(active_count))
            await asyncio.sleep(0.01)
            active_count.remove(handler_id)

        return handler

    for i in range(5):
        handler = await make_handler(i)
        registry.connect("spider_idle", handler)

    await registry.send_async("spider_idle", concurrent=True)

    assert max_active[0] <= 2, f"Expected max 2 concurrent, got {max_active[0]}"


# Error Handling Tests


@pytest.mark.asyncio
async def test_send_async_logs_handler_exceptions():
    """send_async() logs and swallows handler exceptions by default."""
    registry = SignalRegistry()
    call_log = []

    async def failing_handler(sender):
        call_log.append("failing")
        raise ValueError("handler error")

    async def succeeding_handler(sender):
        call_log.append("succeeding")
        return "success"

    registry.connect("request_failed", failing_handler)
    registry.connect("request_failed", succeeding_handler)

    results = await registry.send_async("request_failed", raise_exceptions=False)

    # Both handlers executed despite exception
    assert "failing" in call_log
    assert "succeeding" in call_log
    # Only succeeding handler returned result
    assert results == ["success"]


@pytest.mark.asyncio
async def test_send_async_raises_exceptions_when_requested():
    """send_async() propagates exceptions when raise_exceptions=True."""
    registry = SignalRegistry()

    async def failing_handler(sender):
        raise RuntimeError("intentional failure")

    registry.connect("spider_error", failing_handler)

    with pytest.raises(RuntimeError, match="intentional failure"):
        await registry.send_async("spider_error", raise_exceptions=True)


# Disconnect Tests


@pytest.mark.asyncio
async def test_disconnect_removes_handler():
    """disconnect() removes registered handler."""
    registry = SignalRegistry()
    call_log = []

    async def handler(sender):
        call_log.append("called")

    registry.connect("spider_closed", handler)
    await registry.send_async("spider_closed")
    assert len(call_log) == 1

    registry.disconnect("spider_closed", handler)
    await registry.send_async("spider_closed")
    assert len(call_log) == 1, "Handler should not be called after disconnect"


@pytest.mark.asyncio
async def test_disconnect_with_sender_filter():
    """disconnect() with sender removes only matching sender registration."""
    registry = SignalRegistry()
    sender_a = object()
    sender_b = object()
    calls = []

    async def handler(sender):
        calls.append(id(sender))

    registry.connect("request_dropped", handler, sender=sender_a)
    registry.connect("request_dropped", handler, sender=sender_b)

    # Disconnect only sender_a
    registry.disconnect("request_dropped", handler, sender=sender_a)

    await registry.send_async("request_dropped", sender=sender_a)
    await registry.send_async("request_dropped", sender=sender_b)

    # Only sender_b handler should have been called
    assert len(calls) == 1
    assert calls[0] == id(sender_b)


@pytest.mark.asyncio
async def test_disconnect_all_removes_all_handlers():
    """disconnect_all() removes all handlers for signal."""
    registry = SignalRegistry()
    call_count = []

    async def handler1(sender):
        call_count.append(1)

    async def handler2(sender):
        call_count.append(2)

    registry.connect("item_dropped", handler1)
    registry.connect("item_dropped", handler2)

    registry.disconnect_all("item_dropped")

    await registry.send_async("item_dropped")

    assert len(call_count) == 0, "All handlers should be removed"


@pytest.mark.asyncio
async def test_disconnect_all_with_sender_filter():
    """disconnect_all() with sender removes only matching sender handlers."""
    registry = SignalRegistry()
    sender_a = object()
    sender_b = object()
    calls = []

    async def handler1(sender):
        calls.append("1")

    async def handler2(sender):
        calls.append("2")

    registry.connect("headers_received", handler1, sender=sender_a)
    registry.connect("headers_received", handler2, sender=sender_b)

    # Remove all handlers for sender_a
    registry.disconnect_all("headers_received", sender=sender_a)

    await registry.send_async("headers_received", sender=sender_a)
    await registry.send_async("headers_received", sender=sender_b)

    # Only sender_b handler should have been called
    assert calls == ["2"]


# Weak Reference Tests


@pytest.mark.asyncio
async def test_weak_reference_cleanup_on_garbage_collection():
    """Weak references are cleaned up when handler is garbage collected."""
    registry = SignalRegistry()

    class HandlerClass:
        async def handler_method(self, sender):
            pass

    obj = HandlerClass()
    registry.connect("spider_opened", obj.handler_method, weak=True)

    # Delete the object
    del obj
    gc.collect()  # Force garbage collection

    # Signal should have no live handlers
    handlers = registry._collect_handlers("spider_opened", sender=None)
    assert len(handlers) == 0, "Dead weak references should be cleaned up"


@pytest.mark.asyncio
async def test_strong_reference_prevents_cleanup():
    """Strong references prevent handler cleanup on garbage collection."""
    registry = SignalRegistry()
    call_log = []

    class HandlerClass:
        async def handler_method(self, sender):
            call_log.append("called")

    obj = HandlerClass()
    registry.connect("spider_closed", obj.handler_method, weak=False)

    # Delete the object
    del obj
    gc.collect()

    # Handler should still be alive (strong reference)
    await registry.send_async("spider_closed")
    assert len(call_log) == 1, "Strong reference should keep handler alive"


# SignalDispatcher Tests


@pytest.mark.asyncio
async def test_signal_dispatcher_defaults_sender():
    """SignalDispatcher defaults sender to bound sender."""
    registry = SignalRegistry()
    test_sender = object()
    dispatcher = registry.for_sender(test_sender)

    received_senders = []

    async def handler(sender):
        received_senders.append(id(sender))

    dispatcher.connect("item_error", handler)

    await dispatcher.send_async("item_error")

    assert len(received_senders) == 1
    assert received_senders[0] == id(test_sender)


@pytest.mark.asyncio
async def test_signal_dispatcher_connect_with_custom_sender():
    """SignalDispatcher allows overriding sender in connect()."""
    registry = SignalRegistry()
    dispatcher_sender = object()
    custom_sender = object()
    dispatcher = registry.for_sender(dispatcher_sender)

    calls = []

    async def handler(sender):
        calls.append(id(sender))

    # Connect with custom sender (overrides dispatcher's bound sender)
    dispatcher.connect("request_scheduled", handler, sender=custom_sender)

    # Send from dispatcher_sender - should not trigger
    await dispatcher.send_async("request_scheduled")
    assert len(calls) == 0

    # Send from custom_sender - should trigger
    await registry.send_async("request_scheduled", sender=custom_sender)
    assert len(calls) == 1
    assert calls[0] == id(custom_sender)


@pytest.mark.asyncio
async def test_signal_dispatcher_disconnect():
    """SignalDispatcher.disconnect() removes handler for bound sender."""
    registry = SignalRegistry()
    test_sender = object()
    dispatcher = registry.for_sender(test_sender)

    call_log = []

    async def handler(sender):
        call_log.append("called")

    dispatcher.connect("response_received", handler)
    await dispatcher.send_async("response_received")
    assert len(call_log) == 1

    dispatcher.disconnect("response_received", handler)
    await dispatcher.send_async("response_received")
    assert len(call_log) == 1, "Handler should not be called after disconnect"


@pytest.mark.asyncio
async def test_signal_dispatcher_disconnect_all():
    """SignalDispatcher.disconnect_all() removes all handlers for bound sender."""
    registry = SignalRegistry()
    test_sender = object()
    other_sender = object()
    dispatcher = registry.for_sender(test_sender)

    calls = []

    async def handler1(sender):
        calls.append("1")

    async def handler2(sender):
        calls.append("2")

    dispatcher.connect("bytes_received", handler1)
    dispatcher.connect("bytes_received", handler2)
    registry.connect("bytes_received", handler1, sender=other_sender)

    dispatcher.disconnect_all("bytes_received")

    await dispatcher.send_async("bytes_received")
    await registry.send_async("bytes_received", sender=other_sender)

    # Only other_sender handler should be called
    assert calls == ["1"]


# Edge Cases


@pytest.mark.asyncio
async def test_send_async_with_no_handlers():
    """send_async() returns empty list when no handlers registered."""
    registry = SignalRegistry()

    results = await registry.send_async("spider_idle")

    assert results == []


@pytest.mark.asyncio
async def test_send_async_unknown_signal():
    """send_async() returns empty list for unknown signal (no error)."""
    registry = SignalRegistry()

    results = await registry.send_async("nonexistent_signal")

    assert results == []


@pytest.mark.asyncio
async def test_disconnect_unknown_signal_is_noop():
    """disconnect() for unknown signal is a no-op (no error)."""
    registry = SignalRegistry()

    async def handler(sender):
        pass

    # Should not raise
    registry.disconnect("unknown_signal", handler)


@pytest.mark.asyncio
async def test_supported_signals_list():
    """SUPPORTED_SIGNALS contains expected signal names."""
    expected_signals = [
        "spider_opened",
        "spider_closed",
        "request_scheduled",
        "response_received",
        "item_scraped",
        "bytes_received",
    ]

    for signal in expected_signals:
        assert signal in SUPPORTED_SIGNALS


@pytest.mark.asyncio
async def test_registry_initializes_with_supported_signals():
    """SignalRegistry initializes handler lists for all supported signals."""
    registry = SignalRegistry()

    for signal in SUPPORTED_SIGNALS:
        assert signal in registry._handlers
        assert isinstance(registry._handlers[signal], list)
