"""Tests for qcrawl.core.spider.Spider and ResponseView"""

import pytest

from qcrawl.core.response import Page
from qcrawl.core.spider import ResponseView, Spider


class DummySpider(Spider):
    """Concrete Spider for testing."""

    name = "test_spider"
    start_urls = ["https://example.com"]

    async def parse(self, response):
        yield {"url": response.url}


def test_spider_init_valid():
    """Spider initializes with valid name and start_urls."""
    spider = DummySpider()
    assert spider.name == "test_spider"
    assert spider.start_urls == ["https://example.com"]
    assert spider.engine is None
    assert spider.crawler is None


def test_spider_init_missing_name():
    """Spider raises TypeError if name is missing."""

    class NoNameSpider(Spider):
        start_urls = ["https://example.com"]

        async def parse(self, response):
            yield {}

    with pytest.raises(TypeError, match="must define a non-empty `name: str`"):
        NoNameSpider()


def test_spider_init_missing_start_urls():
    """Spider raises TypeError if start_urls is missing."""

    class NoUrlsSpider(Spider):
        name = "test"

        async def parse(self, response):
            yield {}

    with pytest.raises(TypeError, match="must define a non-empty `start_urls: list"):
        NoUrlsSpider()


@pytest.mark.asyncio
async def test_start_requests():
    """start_requests yields Requests from start_urls."""
    spider = DummySpider()
    requests = []

    async for req in spider.start_requests():
        requests.append(req)

    assert len(requests) == 1
    assert requests[0].url == "https://example.com/"  # Normalized
    assert requests[0].priority == 0
    assert requests[0].meta == {"depth": 0}


@pytest.mark.asyncio
async def test_open_spider():
    """open_spider attaches engine and crawler."""

    class MockEngine:
        crawler = None

    spider = DummySpider()
    engine = MockEngine()

    await spider.open_spider(engine)
    assert spider.engine is engine


@pytest.mark.asyncio
async def test_close_spider():
    """close_spider is a no-op by default."""
    spider = DummySpider()
    await spider.close_spider(None, reason="finished")  # Returns None


def test_response_view():
    """response_view creates ResponseView."""
    spider = DummySpider()
    page = Page(url="https://example.com", content=b"<html></html>", status_code=200, headers={})

    rv = spider.response_view(page)
    assert isinstance(rv, ResponseView)
    assert rv.response is page
    assert rv.spider is spider


def test_spider_follow():
    """Spider.follow creates Request from href."""
    spider = DummySpider()
    page = Page(url="https://example.com/page", content=b"", status_code=200, headers={})

    req = spider.follow(page, "/other", priority=5, meta={"key": "value"})
    assert req.url == "https://example.com/other"
    assert req.priority == 5
    assert req.meta == {"key": "value"}


def test_response_view_init():
    """ResponseView initializes with response and spider."""
    spider = DummySpider()
    page = Page(url="https://example.com", content=b"<html></html>", status_code=200, headers={})

    rv = ResponseView(page, spider)
    assert rv.response is page
    assert rv.spider is spider
    assert rv._doc is None


def test_response_view_doc():
    """ResponseView.doc lazy-loads lxml document."""
    spider = DummySpider()
    page = Page(
        url="https://example.com",
        content=b"<html><body><h1>Title</h1></body></html>",
        status_code=200,
        headers={},
    )

    rv = ResponseView(page, spider)
    assert rv._doc is None  # Not loaded yet

    doc = rv.doc
    assert doc is not None
    assert rv._doc is doc  # Cached

    # Can query the document
    headings = doc.cssselect("h1")
    assert len(headings) == 1
    assert headings[0].text == "Title"


def test_response_view_follow():
    """ResponseView.follow creates Request with resolved URL."""
    spider = DummySpider()
    page = Page(url="https://example.com/page", content=b"", status_code=200, headers={})

    rv = ResponseView(page, spider)

    # Relative URL
    req = rv.follow("other.html", priority=5, meta={"depth": 1})
    assert "other.html" in req.url
    assert req.priority == 5
    assert req.meta == {"depth": 1}

    # Absolute path
    req = rv.follow("/path")
    assert req.url == "https://example.com/path"


def test_response_view_urljoin():
    """ResponseView.urljoin resolves relative URLs."""
    spider = DummySpider()
    page = Page(url="https://example.com/path/page", content=b"", status_code=200, headers={})

    rv = ResponseView(page, spider)

    # Relative URL
    url = rv.urljoin("other.html")
    assert url == "https://example.com/path/other.html"

    # Absolute path
    url = rv.urljoin("/other")
    assert url == "https://example.com/other"

    # Full URL
    url = rv.urljoin("https://other.com/page")
    assert url == "https://other.com/page"
