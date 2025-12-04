"""Tests for qcrawl.core.page.PageMethod"""

import pytest

from qcrawl.core.page import PageMethod

# Initialization Tests


def test_pagemethod_init_with_string_method():
    """PageMethod initializes with string method name."""
    pm = PageMethod("click", "#button")

    assert pm.method == "click"
    assert pm.args == ("#button",)
    assert pm.kwargs == {}
    assert pm.timing == "after"
    assert pm.result is None


def test_pagemethod_init_with_kwargs():
    """PageMethod initializes with keyword arguments."""
    pm = PageMethod("screenshot", path="/tmp/page.png", full_page=True)

    assert pm.method == "screenshot"
    assert pm.args == ()
    assert pm.kwargs == {"path": "/tmp/page.png", "full_page": True}
    assert pm.timing == "after"


def test_pagemethod_init_with_mixed_args_kwargs():
    """PageMethod initializes with both positional and keyword arguments."""
    pm = PageMethod("fill", "#input", "text value", timeout=5000)

    assert pm.method == "fill"
    assert pm.args == ("#input", "text value")
    assert pm.kwargs == {"timeout": 5000}


def test_pagemethod_init_with_timing_before():
    """PageMethod initializes with timing='before'."""
    pm = PageMethod("evaluate", "window.scrollTo(0, 0)", timing="before")

    assert pm.method == "evaluate"
    assert pm.args == ("window.scrollTo(0, 0)",)
    assert pm.timing == "before"


def test_pagemethod_init_with_timing_after():
    """PageMethod initializes with timing='after' (explicit)."""
    pm = PageMethod("wait_for_selector", ".content", timing="after")

    assert pm.timing == "after"


# Validation Tests


def test_pagemethod_rejects_invalid_timing():
    """PageMethod raises ValueError for invalid timing."""
    with pytest.raises(ValueError, match="timing must be 'before' or 'after'"):
        PageMethod("click", "#button", timing="invalid")


@pytest.mark.parametrize("invalid_timing", ["BEFORE", "AFTER", "during", ""])
def test_pagemethod_rejects_various_invalid_timings(invalid_timing):
    """PageMethod rejects various invalid timing values."""
    with pytest.raises(ValueError, match="timing must be 'before' or 'after'"):
        PageMethod("click", "#button", timing=invalid_timing)


def test_pagemethod_rejects_callable():
    """PageMethod raises TypeError when method is a callable instead of string."""

    async def custom_action(page):
        await page.click("#button")

    with pytest.raises(
        TypeError, match="PageMethod.method must be a string.*Use camoufox_include_page=True"
    ):
        PageMethod(custom_action)  # type: ignore[arg-type]


# Result Storage Tests


def test_pagemethod_result_starts_none():
    """PageMethod.result starts as None."""
    pm = PageMethod("click", "#button")

    assert pm.result is None


def test_pagemethod_result_can_be_set():
    """PageMethod.result can be set after execution."""
    pm = PageMethod("evaluate", "2 + 2")
    pm.result = 4

    assert pm.result == 4


# Serialization Tests


def test_pagemethod_to_dict_basic():
    """PageMethod.to_dict() serializes basic method."""
    pm = PageMethod("click", "#button")
    data = pm.to_dict()

    assert data == {
        "method": "click",
        "timing": "after",
        "args": ["#button"],
    }


def test_pagemethod_to_dict_with_kwargs():
    """PageMethod.to_dict() serializes keyword arguments."""
    pm = PageMethod("screenshot", path="/tmp/page.png", full_page=True)
    data = pm.to_dict()

    assert data == {
        "method": "screenshot",
        "timing": "after",
        "kwargs": {"path": "/tmp/page.png", "full_page": True},
    }


def test_pagemethod_to_dict_with_timing_before():
    """PageMethod.to_dict() includes timing='before'."""
    pm = PageMethod("evaluate", "console.log('test')", timing="before")
    data = pm.to_dict()

    assert data["timing"] == "before"


def test_pagemethod_to_dict_no_empty_fields():
    """PageMethod.to_dict() omits empty args/kwargs."""
    pm = PageMethod("wait_for_timeout", 1000)
    data = pm.to_dict()

    # Should have args but not kwargs
    assert "args" in data
    assert "kwargs" not in data


# Deserialization Tests


def test_pagemethod_from_dict_basic():
    """PageMethod.from_dict() deserializes basic method."""
    data: dict[str, object] = {"method": "click", "args": ["#button"]}
    pm = PageMethod.from_dict(data)

    assert pm.method == "click"
    assert pm.args == ("#button",)
    assert pm.kwargs == {}
    assert pm.timing == "after"


def test_pagemethod_from_dict_with_kwargs():
    """PageMethod.from_dict() deserializes keyword arguments."""
    data: dict[str, object] = {
        "method": "screenshot",
        "kwargs": {"path": "/tmp/page.png", "full_page": True},
    }
    pm = PageMethod.from_dict(data)

    assert pm.method == "screenshot"
    assert pm.kwargs == {"path": "/tmp/page.png", "full_page": True}


def test_pagemethod_from_dict_with_timing():
    """PageMethod.from_dict() deserializes timing."""
    data: dict[str, object] = {
        "method": "evaluate",
        "args": ["console.log('test')"],
        "timing": "before",
    }
    pm = PageMethod.from_dict(data)

    assert pm.timing == "before"


def test_pagemethod_from_dict_defaults():
    """PageMethod.from_dict() uses defaults for missing fields."""
    data: dict[str, object] = {"method": "click"}
    pm = PageMethod.from_dict(data)

    assert pm.method == "click"
    assert pm.args == ()
    assert pm.kwargs == {}
    assert pm.timing == "after"


def test_pagemethod_from_dict_invalid_args_type():
    """PageMethod.from_dict() handles invalid args type gracefully."""
    data: dict[str, object] = {"method": "click", "args": "not-a-list"}
    pm = PageMethod.from_dict(data)

    # Should default to empty tuple
    assert pm.args == ()


def test_pagemethod_from_dict_invalid_kwargs_type():
    """PageMethod.from_dict() handles invalid kwargs type gracefully."""
    data: dict[str, object] = {"method": "click", "kwargs": ["not", "a", "dict"]}
    pm = PageMethod.from_dict(data)

    # Should default to empty dict
    assert pm.kwargs == {}


def test_pagemethod_from_dict_invalid_timing():
    """PageMethod.from_dict() normalizes invalid timing to 'after'."""
    data: dict[str, object] = {"method": "click", "timing": "invalid"}
    pm = PageMethod.from_dict(data)

    assert pm.timing == "after"


# Round-trip Serialization Tests


def test_pagemethod_serialization_roundtrip():
    """PageMethod can be serialized and deserialized without loss."""
    original = PageMethod("screenshot", path="/tmp/page.png", full_page=True, timing="before")
    data = original.to_dict()
    restored = PageMethod.from_dict(data)

    assert restored.method == original.method
    assert restored.args == original.args
    assert restored.kwargs == original.kwargs
    assert restored.timing == original.timing


@pytest.mark.parametrize(
    "method_spec",
    [
        ("click", ("#button",), {}, "after"),
        ("screenshot", (), {"path": "/tmp/page.png"}, "after"),
        ("evaluate", ("window.scrollTo(0, 0)",), {}, "before"),
        ("wait_for_selector", (".content",), {"timeout": 5000}, "after"),
    ],
)
def test_pagemethod_serialization_roundtrip_parametrized(method_spec):
    """PageMethod roundtrip works for various configurations."""
    method, args, kwargs, timing = method_spec
    original = PageMethod(method, *args, timing=timing, **kwargs)
    restored = PageMethod.from_dict(original.to_dict())

    assert restored.method == original.method
    assert restored.args == original.args
    assert restored.kwargs == original.kwargs
    assert restored.timing == original.timing
