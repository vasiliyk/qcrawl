<img src="https://www.qcrawl.org/assets/crawl.svg" alt="qCrawl Logo" style="min-width:75%;" />

[![PyPI Version](https://img.shields.io/pypi/v/qcrawl.svg?style=for-the-badge)](https://pypi.org/project/qcrawl)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/qcrawl.svg?style=for-the-badge)](https://pypi.org/project/qcrawl)
[![Codecov](https://img.shields.io/codecov/c/github/crawlcore/qcrawl/main?style=for-the-badge)](https://codecov.io/gh/crawlcore/qcrawl)

[qcrawl](https://www.qcrawl.org) is a fast async web crawling & scraping framework for Python to extract structured data from web-pages.
It is cross-platform and easy to install via `pip` or `conda`.

Follow the [documentation](https://www.qcrawl.org/).


### qCrawl features

1. Async architecture - High-performance concurrent crawling based on asyncio
2. Performance optimized - Queue backend on Redis with direct delivery, messagepack serialization, connection pooling, DNS caching
3. Powerful parsing - CSS/XPath selectors with lxml
4. Middleware system - Customizable request/response processing
5. Flexible export - Multiple output formats including JSON, CSV, XML
6. Flexible queue backends - Memory or Redis-based (+disk) schedulers for different scale requirements
7. Item pipelines - Data transformation, validation, and processing pipeline
8. Pluggable downloaders - HTTP (aiohttp), Camoufox (stealth browser) for JavaScript rendering and anti-bot evasion
