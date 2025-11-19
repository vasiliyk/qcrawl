<img src="docs/assets/crawl.svg" alt="qCrawl Logo" style="min-width:75%;" />

[qcrawl](https://www.qcrawl.org) is a fast async web crawling & scraping framework for Python to extract structured data from web-pages.
It is cross-platform and easy to install via `pip`, `conda`, or OS packages.

Follow the [documentation](https://www.qcrawl.org/).


### Libraries comparison

| Attribute           | qCrawl ⭐                                                          | Scrapy                                                           | Playwright                                                             | Colly                                     |
|---------------------|-------------------------------------------------------------------|------------------------------------------------------------------|------------------------------------------------------------------------|-------------------------------------------|
| Language            | Python                                                            | Python                                                           | Node.js, Python, Java                                                  | Go                                        |
| Concurrency model   | Asyncio native with threads for I/O work                          | Evented (Twisted) with non‑blocking I/O                          | Isolated contexts within browser instance + multiple browser instances | Goroutines (lightweight threads)          |
| Queue               | Priority queue with FIFO tiebreak, memory, [disk, redis backends] | Priority queue with FIFO/LIFO tiebreak, memory and disk backends | No built-in crawl queue (user-managed)                                 | FIFO with memory and file backends        |
| Middleware & hooks  | Downloader + Spider middlewares; signal-driven lifecycle hooks    | Downloader + Spider middlewares; signal-driven lifecycle hooks   | Hooks and interception API; not pipeline-centric                       | Middleware-style callbacks                |
| Crawl throttling    | Per-domain concurrency with configurable delay                    | Per-domain concurrency with configurable delay                   | Controlled via browser sessions                                        | Per-host concurrency                      |
| Strengths           | Lightweight, high-throughput, easy to extend                      | Very mature ecosystem and community, easy to extend              | Real browser rendering, JS support, robust for SPA sites               | Extremely high throughput, low memory use |

