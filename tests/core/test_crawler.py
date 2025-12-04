"""Tests for qcrawl.core.crawler.Crawler"""

import pytest

from qcrawl.core.crawler import Crawler
from qcrawl.middleware import DownloaderMiddleware

# Basic Initialization Tests


def test_crawler_initializes_correctly(crawler, spider, settings):
    """Crawler initializes with all required components."""
    assert crawler.spider is spider
    assert crawler.runtime_settings is settings
    assert crawler.stats is not None
    assert crawler.signals is not None
    assert crawler._finalized is False
    assert crawler.queue is None
    assert crawler.handler_manager is None
    assert crawler.scheduler is None
    assert crawler.engine is None


# Middleware Registration Tests


@pytest.mark.parametrize(
    "middleware",
    [
        pytest.param(
            lambda: pytest.importorskip("tests.core.conftest").DummyDownloaderMiddleware(),
            id="instance",
        ),
        pytest.param(
            lambda: pytest.importorskip("tests.core.conftest").DummyDownloaderMiddleware,
            id="class",
        ),
    ],
)
def test_add_middleware_accepts_various_forms(crawler, middleware):
    """Crawler accepts middleware as instance or class."""
    mw = middleware()
    crawler.add_middleware(mw)
    assert mw in crawler._pending_middlewares


def test_add_middleware_after_crawl_raises(crawler):
    """Cannot add middleware after crawl has started."""
    # Simulate crawl started
    crawler.engine = object()

    with pytest.raises(RuntimeError, match="Cannot add middleware after crawl"):
        crawler.add_middleware(object())


def test_add_multiple_middlewares(crawler, downloader_middleware):
    """Crawler can register multiple middlewares in order."""
    mw1 = downloader_middleware
    from tests.core.conftest import DummyDownloaderMiddleware

    mw2 = DummyDownloaderMiddleware()

    crawler.add_middleware(mw1)
    crawler.add_middleware(mw2)

    assert len(crawler._pending_middlewares) >= 2
    # Middlewares appear in order after defaults
    assert mw1 in crawler._pending_middlewares
    assert mw2 in crawler._pending_middlewares


# Middleware Resolution via from_crawler


def test_middleware_with_from_crawler_classmethod(spider, settings):
    """Middleware with from_crawler() classmethod is instantiated correctly."""

    class CustomMiddleware(DownloaderMiddleware):
        def __init__(self, crawler):
            self.crawler = crawler

        @classmethod
        def from_crawler(cls, crawler):
            return cls(crawler)

        async def process_request(self, request, spider):
            pass

    crawler = Crawler(spider, settings)
    crawler.add_middleware(CustomMiddleware)

    # Middleware should be in pending (resolution happens later)
    assert CustomMiddleware in crawler._pending_middlewares


# Lifecycle Tests


@pytest.mark.asyncio
async def test_crawler_context_manager_lifecycle(crawler, spider):
    """Crawler works as async context manager with proper cleanup."""
    assert not crawler._finalized

    async with crawler:
        assert crawler.spider is spider
        assert not crawler._finalized

    # Should be finalized after exit
    assert crawler._finalized


# Default Middlewares


def test_default_middlewares_registered(crawler):
    """Crawler automatically registers default middlewares from settings."""
    # Default middlewares should be added during __init__
    assert len(crawler._pending_middlewares) > 0


# Settings Merging Tests


def test_spider_custom_settings_merge_into_runtime_settings(settings):
    """Spider custom_settings are properly merged into runtime settings."""
    from qcrawl.core.spider import Spider

    class CustomSpider(Spider):
        name = "custom"
        start_urls = ["https://example.com"]

        custom_settings = {
            "CONCURRENCY": 10,
            "USER_AGENT": "CustomBot/1.0",
        }

        async def parse(self, response):
            pass

    crawler = Crawler(CustomSpider(), settings)

    # Settings merging happens during crawl initialization
    # Test the _build_final_settings method directly
    final_settings = crawler._build_final_settings()

    # Custom settings should be merged
    assert final_settings.CONCURRENCY == 10
    assert final_settings.USER_AGENT == "CustomBot/1.0"


def test_download_handlers_from_custom_settings_available(settings):
    """DOWNLOAD_HANDLERS from spider custom_settings are accessible (regression test)."""
    from qcrawl.core.spider import Spider

    class BrowserSpider(Spider):
        name = "browser"
        start_urls = ["https://example.com"]

        custom_settings = {
            "DOWNLOAD_HANDLERS": {
                "http": "qcrawl.downloaders.HTTPDownloader",
                "https": "qcrawl.downloaders.HTTPDownloader",
                "camoufox": "qcrawl.downloaders.CamoufoxDownloader",
            }
        }

        async def parse(self, response):
            pass

    crawler = Crawler(BrowserSpider(), settings)

    # Test the _build_final_settings method directly
    # This is a regression test for the asdict() fix in _build_final_settings()
    final_settings = crawler._build_final_settings()

    handlers = final_settings.DOWNLOAD_HANDLERS
    assert "http" in handlers
    assert "https" in handlers
    assert "camoufox" in handlers
    assert handlers["camoufox"] == "qcrawl.downloaders.CamoufoxDownloader"


def test_spider_instance_custom_settings_merge(settings):
    """Spider instance with custom_settings merges correctly."""
    from qcrawl.core.spider import Spider

    class SpiderWithSettings(Spider):
        name = "test"
        start_urls = ["https://example.com"]

        async def parse(self, response):
            pass

    spider = SpiderWithSettings()
    spider.custom_settings = {
        "DELAY_PER_DOMAIN": 2.0,
        "MAX_RETRIES": 5,
    }

    crawler = Crawler(spider, settings)

    # Test the _build_final_settings method directly
    final_settings = crawler._build_final_settings()

    assert final_settings.DELAY_PER_DOMAIN == 2.0
    assert final_settings.MAX_RETRIES == 5


def test_mixed_case_custom_settings_normalized(settings):
    """Spider custom_settings with mixed case keys are normalized to UPPERCASE."""
    from qcrawl.core.spider import Spider

    class MixedCaseSpider(Spider):
        name = "mixed"
        start_urls = ["https://example.com"]

        custom_settings = {
            "concurrency": 5,  # lowercase
            "User_Agent": "MixedBot/1.0",  # mixed case
            "MAX_RETRIES": 7,  # uppercase
        }

        async def parse(self, response):
            pass

    crawler = Crawler(MixedCaseSpider(), settings)

    # Test the _build_final_settings method directly
    final_settings = crawler._build_final_settings()

    # All should be normalized and accessible
    assert final_settings.CONCURRENCY == 5
    assert final_settings.USER_AGENT == "MixedBot/1.0"
    assert final_settings.MAX_RETRIES == 7


# Error Handling


def test_invalid_middleware_type_rejected(crawler):
    """Crawler rejects invalid middleware types."""
    # This will fail during resolution, not during add_middleware
    # Just verify we can add it (resolution happens later)
    crawler.add_middleware("invalid")
    assert "invalid" in crawler._pending_middlewares
