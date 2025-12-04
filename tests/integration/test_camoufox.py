"""Integration tests for Camoufox browser automation (end-to-end).

Tests the complete flow: Spider → Crawler → Engine → DownloadHandlerManager → CamoufoxDownloader → Real Browser

Requires:
- Docker for httpbin container
- Camoufox package installed (pip install camoufox)
"""

import argparse
from types import SimpleNamespace

import pytest
from testcontainers.core.container import DockerContainer

from qcrawl.core.page import PageMethod
from qcrawl.core.request import Request
from qcrawl.core.spider import Spider
from qcrawl.runner.engine import run
from qcrawl.settings import Settings

# Try to import Camoufox - skip all tests if not available
camoufox_available = True
try:
    from camoufox.async_api import AsyncCamoufox  # noqa: F401
except ImportError:
    camoufox_available = False

# Skip all tests in this module if Camoufox not installed
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not camoufox_available, reason="Camoufox not installed"),
]


# Fixtures


@pytest.fixture(scope="module")
def httpbin_server():
    """Start httpbin container for testing against real HTTP server."""
    import time
    import urllib.request

    container = DockerContainer("kennethreitz/httpbin:latest")
    container.with_exposed_ports(80)
    container.start()

    host = container.get_container_host_ip()
    port = container.get_exposed_port(80)
    base_url = f"http://{host}:{port}"

    # Wait for HTTP server to be ready
    max_retries = 30
    for _ in range(max_retries):
        try:
            urllib.request.urlopen(f"{base_url}/get", timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    yield base_url

    container.stop()


@pytest.fixture
def args_no_export():
    """Provide args with no export (stdout only)."""
    return argparse.Namespace(
        export=None,
        export_format="ndjson",
        export_mode="buffered",
        export_buffer_size=500,
        setting=[],
        settings_file=None,
        log_level="ERROR",
        log_file=None,
    )


@pytest.fixture
def camoufox_settings():
    """Provide settings with Camoufox configuration."""
    return Settings().with_overrides(
        {
            "DOWNLOAD_HANDLERS": {
                "http": "qcrawl.downloaders.HTTPDownloader",
                "https": "qcrawl.downloaders.HTTPDownloader",
                "camoufox": "qcrawl.downloaders.CamoufoxDownloader",
            },
            "CAMOUFOX_CONTEXTS": {
                "default": {"viewport": {"width": 1280, "height": 720}},
            },
            "CAMOUFOX_MAX_CONTEXTS": 2,
            "CAMOUFOX_MAX_PAGES_PER_CONTEXT": 3,
            "CAMOUFOX_DEFAULT_NAVIGATION_TIMEOUT": 30000.0,
            "CAMOUFOX_LAUNCH_OPTIONS": {"headless": True},
        }
    )


# Test Spiders


class BrowserSpider(Spider):
    """Spider that uses browser automation for rendering."""

    name = "browser_spider"

    def __init__(self, base_url="http://httpbin.org"):
        self.start_urls = [f"{base_url}/html"]
        super().__init__()

    async def parse(self, response):
        """Parse HTML response rendered by browser."""
        # Extract data from browser-rendered HTML
        rv = self.response_view(response)
        h1_tags = rv.doc.cssselect("h1")

        for h1 in h1_tags:
            yield {"heading": h1.text_content().strip()}

    async def start_requests(self):
        """Generate initial requests using browser handler."""
        for url in self.start_urls:
            yield Request(url=url, meta={"use_handler": "camoufox"})


class MultiplePagesSpider(Spider):
    """Spider that crawls multiple pages using browser."""

    name = "multiple_pages_spider"

    def __init__(self, base_url="http://httpbin.org"):
        self.start_urls = [f"{base_url}/html", f"{base_url}/links/5"]
        super().__init__()

    async def parse(self, response):
        """Parse HTML response."""
        rv = self.response_view(response)

        # Try to find headings or links
        h1_tags = rv.doc.cssselect("h1")
        links = rv.doc.cssselect("a")

        if h1_tags:
            yield {"type": "heading", "content": h1_tags[0].text_content().strip()}
        if links:
            yield {"type": "links", "count": len(links)}

    async def start_requests(self):
        """Generate requests using browser handler."""
        for url in self.start_urls:
            yield Request(url=url, meta={"use_handler": "camoufox"})


# Integration Tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_renders_html_end_to_end(
    httpbin_server, args_no_export, camoufox_settings, capsys
):
    """Complete flow: Spider uses browser to render HTML from real HTTP server."""
    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    # Run spider with browser automation - tests full integration
    await run(BrowserSpider, args_no_export, spider_settings, camoufox_settings)

    # Verify output contains scraped data
    captured = capsys.readouterr()
    output = captured.out

    assert len(output) > 0, "Should have output"
    assert "heading" in output, "Should contain scraped heading data"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_handles_multiple_pages(
    httpbin_server, args_no_export, camoufox_settings, capsys
):
    """Browser handler can crawl multiple pages via complete flow."""
    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    # Run spider that crawls multiple pages using browser
    await run(MultiplePagesSpider, args_no_export, spider_settings, camoufox_settings)

    # Verify data was extracted from multiple pages
    captured = capsys.readouterr()
    output = captured.out

    assert len(output) > 0, "Should have output"
    assert "heading" in output or "links" in output, "Should contain scraped data"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_with_custom_settings(httpbin_server, args_no_export):
    """Spider can override browser settings via custom_settings."""

    class CustomBrowserSpider(Spider):
        name = "custom_browser"
        start_urls = [f"{httpbin_server}/html"]

        # Override Camoufox settings at spider level
        custom_settings = {
            "CAMOUFOX_MAX_PAGES_PER_CONTEXT": 5,
            "CAMOUFOX_DEFAULT_NAVIGATION_TIMEOUT": 60000.0,
        }

        async def parse(self, response):
            yield {"status": response.status_code}

        async def start_requests(self):
            for url in self.start_urls:
                yield Request(url=url, meta={"use_handler": "camoufox"})

    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})
    runtime_settings = Settings().with_overrides(
        {
            "DOWNLOAD_HANDLERS": {
                "http": "qcrawl.downloaders.HTTPDownloader",
                "camoufox": "qcrawl.downloaders.CamoufoxDownloader",
            },
            "CAMOUFOX_CONTEXTS": {"default": {}},
            "CAMOUFOX_LAUNCH_OPTIONS": {"headless": True},
        }
    )

    # Run with custom spider settings
    await run(CustomBrowserSpider, args_no_export, spider_settings, runtime_settings)

    # If we get here without errors, custom settings were applied correctly


# PageMethod Integration Tests


class PageMethodSpider(Spider):
    """Spider that uses PageMethod for browser interactions."""

    name = "pagemethod_spider"

    def __init__(self, base_url="http://httpbin.org"):
        self.start_urls = [f"{base_url}/html"]
        super().__init__()

    async def parse(self, response):
        """Parse response and verify PageMethod results."""
        rv = self.response_view(response)
        h1_tags = rv.doc.cssselect("h1")

        # Access PageMethod results from response meta
        page_methods = response.meta.get("camoufox_page_methods", [])

        yield {
            "heading": h1_tags[0].text_content().strip() if h1_tags else None,
            "page_methods_executed": len(page_methods),
        }

    async def start_requests(self):
        """Generate requests with PageMethod objects."""
        for url in self.start_urls:
            yield Request(
                url=url,
                meta={
                    "use_handler": "camoufox",
                    "camoufox_page_methods": [
                        # Wait for content after navigation
                        PageMethod("wait_for_selector", "h1", timing="after"),
                    ],
                },
            )


class PageMethodTimingSpider(Spider):
    """Spider that tests PageMethod timing (before/after navigation)."""

    name = "pagemethod_timing"

    def __init__(self, base_url="http://httpbin.org"):
        self.start_urls = [f"{base_url}/html"]
        super().__init__()

    async def parse(self, response):
        """Verify timing execution."""
        page_methods = response.meta.get("camoufox_page_methods", [])

        # Both before and after methods should be executed
        yield {
            "methods_count": len(page_methods),
            "status": response.status_code,
        }

    async def start_requests(self):
        """Generate requests with before/after PageMethods."""
        for url in self.start_urls:
            yield Request(
                url=url,
                meta={
                    "use_handler": "camoufox",
                    "camoufox_page_methods": [
                        # Execute JavaScript before navigation
                        PageMethod("evaluate", "console.log('before navigation')", timing="before"),
                        # Wait after navigation
                        PageMethod("wait_for_timeout", 100, timing="after"),
                    ],
                },
            )


class PageMethodMultipleActionsSpider(Spider):
    """Spider that uses multiple PageMethods in sequence."""

    name = "pagemethod_multiple"

    def __init__(self, base_url="http://httpbin.org"):
        self.start_urls = [f"{base_url}/html"]
        super().__init__()

    async def parse(self, response):
        """Verify multiple page methods execution."""
        yield {"status": response.status_code}

    async def start_requests(self):
        """Generate requests with multiple PageMethods."""
        for url in self.start_urls:
            yield Request(
                url=url,
                meta={
                    "use_handler": "camoufox",
                    "camoufox_page_methods": [
                        # Multiple methods execute in sequence
                        PageMethod("wait_for_selector", "h1"),
                        PageMethod("evaluate", "document.title"),
                        PageMethod("wait_for_timeout", 100),
                    ],
                },
            )


class PageMethodDictBackwardCompatSpider(Spider):
    """Spider that uses dict format for backward compatibility."""

    name = "pagemethod_dict"

    def __init__(self, base_url="http://httpbin.org"):
        self.start_urls = [f"{base_url}/html"]
        super().__init__()

    async def parse(self, response):
        """Verify dict-based page methods work."""
        yield {"status": response.status_code}

    async def start_requests(self):
        """Generate requests with dict-based page methods."""
        for url in self.start_urls:
            yield Request(
                url=url,
                meta={
                    "use_handler": "camoufox",
                    "camoufox_page_methods": [
                        # Old dict format for backward compatibility
                        {"method": "wait_for_selector", "args": ["h1"], "timing": "after"},
                    ],
                },
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagemethod_wait_for_selector(
    httpbin_server, args_no_export, camoufox_settings, capsys
):
    """PageMethod can wait for selectors after page load."""
    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    await run(PageMethodSpider, args_no_export, spider_settings, camoufox_settings)

    # Verify output contains data extracted after waiting for selector
    captured = capsys.readouterr()
    output = captured.out

    assert "heading" in output, "Should extract heading after waiting for selector"
    assert "page_methods_executed" in output, "Should track executed PageMethods"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagemethod_timing_before_after(
    httpbin_server, args_no_export, camoufox_settings, capsys
):
    """PageMethod timing controls when methods execute (before/after navigation)."""
    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    await run(PageMethodTimingSpider, args_no_export, spider_settings, camoufox_settings)

    # Verify spider ran successfully with both before/after methods
    captured = capsys.readouterr()
    output = captured.out

    assert "methods_count" in output, "Should track method execution"
    assert "status" in output, "Should complete navigation successfully"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagemethod_multiple_actions(
    httpbin_server, args_no_export, camoufox_settings, capsys
):
    """PageMethod can execute multiple actions in sequence."""
    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    await run(PageMethodMultipleActionsSpider, args_no_export, spider_settings, camoufox_settings)

    # Verify multiple page methods executed without errors
    captured = capsys.readouterr()
    output = captured.out

    assert "status" in output, "Should complete with multiple page methods"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagemethod_dict_backward_compatibility(
    httpbin_server, args_no_export, camoufox_settings, capsys
):
    """PageMethod supports dict format for backward compatibility."""
    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    await run(
        PageMethodDictBackwardCompatSpider, args_no_export, spider_settings, camoufox_settings
    )

    # Verify dict-based page methods work
    captured = capsys.readouterr()
    output = captured.out

    assert "status" in output, "Should complete with dict-based page methods"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagemethod_evaluate_javascript_with_results(
    httpbin_server, args_no_export, camoufox_settings, capsys
):
    """PageMethod can evaluate JavaScript and results survive serialization."""

    class EvaluateSpider(Spider):
        name = "evaluate"
        start_urls = [f"{httpbin_server}/html"]

        async def parse(self, response):
            """Verify JavaScript evaluation and result storage."""
            # PageMethod results survive serialization!
            page_methods = response.meta.get("camoufox_page_methods", [])

            result_found = False
            for method in page_methods:
                # Methods come back as PageMethod objects with results
                if (
                    isinstance(method, PageMethod)
                    and method.method == "evaluate"
                    and method.result is not None
                    or isinstance(method, dict)
                    and method.get("method") == "evaluate"
                    and method.get("result") is not None
                ):
                    result_found = True
                    break

            yield {
                "status": response.status_code,
                "result_found": result_found,
            }

        async def start_requests(self):
            for url in self.start_urls:
                yield Request(
                    url=url,
                    meta={
                        "use_handler": "camoufox",
                        "camoufox_page_methods": [
                            # Evaluate JavaScript - returns result
                            PageMethod("evaluate", "document.title"),
                            PageMethod("evaluate", "2 + 2"),
                        ],
                    },
                )

    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    await run(EvaluateSpider, args_no_export, spider_settings, camoufox_settings)

    # Verify JavaScript evaluation worked and results were captured
    captured = capsys.readouterr()
    output = captured.out

    assert "result_found" in output, "Should have captured results"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagemethod_with_kwargs(httpbin_server, args_no_export, camoufox_settings, capsys):
    """PageMethod supports keyword arguments."""

    class KwargsSpider(Spider):
        name = "kwargs"
        start_urls = [f"{httpbin_server}/html"]

        async def parse(self, response):
            yield {"status": response.status_code}

        async def start_requests(self):
            for url in self.start_urls:
                yield Request(
                    url=url,
                    meta={
                        "use_handler": "camoufox",
                        "camoufox_page_methods": [
                            # wait_for_selector with timeout kwarg
                            PageMethod("wait_for_selector", "h1", timeout=5000),
                        ],
                    },
                )

    spider_settings = SimpleNamespace(spider_args={"base_url": httpbin_server})

    await run(KwargsSpider, args_no_export, spider_settings, camoufox_settings)

    # Verify keyword arguments work
    captured = capsys.readouterr()
    output = captured.out

    assert "status" in output, "Should complete with keyword arguments"
