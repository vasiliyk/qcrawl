"""Tests for qcrawl.core.response.Page"""

import pytest

from qcrawl.core.response import Page


def test_init():
    """Page initializes with required params."""
    page = Page(
        url="https://example.com/page",
        content=b"<html>test</html>",
        status_code=200,
        headers={"Content-Type": "text/html"},
    )

    assert page.url == "https://example.com/page"
    assert page.content == b"<html>test</html>"
    assert page.status_code == 200
    assert page.headers == {"Content-Type": "text/html"}
    assert page.request is None


def test_init_with_encoding():
    """Page initializes with pre-set encoding."""
    page = Page(
        url="https://example.com",
        content=b"test",
        status_code=200,
        headers={},
        encoding="utf-8",
    )
    assert page._detected_encoding == "utf-8"


def test_text_with_default_encoding():
    """text() decodes content with auto-detected encoding."""
    page = Page(
        url="https://example.com",
        content=b"Hello World",
        status_code=200,
        headers={},
    )

    text = page.text()
    assert text == "Hello World"


def test_text_with_custom_encoding():
    """text() accepts custom encoding."""
    page = Page(
        url="https://example.com",
        content=b"Hello",
        status_code=200,
        headers={},
    )

    text = page.text(encoding="utf-8")
    assert text == "Hello"


def test_text_with_preset_encoding():
    """text() uses preset encoding if provided."""
    page = Page(
        url="https://example.com",
        content=b"Hello",
        status_code=200,
        headers={},
        encoding="utf-8",
    )

    text = page.text()
    assert text == "Hello"


def test_json_valid():
    """json() parses valid JSON."""
    page = Page(
        url="https://api.example.com",
        content=b'{"key": "value", "count": 42}',
        status_code=200,
        headers={},
    )

    data = page.json()
    assert data == {"key": "value", "count": 42}


def test_json_invalid():
    """json() raises ValueError for invalid JSON."""
    page = Page(
        url="https://api.example.com",
        content=b"not json",
        status_code=200,
        headers={},
    )

    with pytest.raises(ValueError, match="Failed to parse JSON"):
        page.json()


def test_follow():
    """follow() resolves relative URLs."""
    page = Page(
        url="https://example.com/path/page.html",
        content=b"",
        status_code=200,
        headers={},
    )

    # Relative path
    assert page.follow("other.html") == "https://example.com/path/other.html"

    # Absolute path
    assert page.follow("/other") == "https://example.com/other"

    # Full URL
    assert page.follow("https://other.com/page") == "https://other.com/page"


def test_repr():
    """__repr__ shows url, status, and content size."""
    page = Page(
        url="https://example.com",
        content=b"test content",
        status_code=200,
        headers={},
    )

    r = repr(page)
    assert "Page(" in r
    assert "https://example.com" in r
    assert "status=200" in r
    assert "12 bytes" in r
