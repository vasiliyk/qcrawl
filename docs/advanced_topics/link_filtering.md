
Link filtering determines which URLs your crawler will follow. Effective filtering reduces unnecessary requests, focuses on target content, and respects domain boundaries. Filters can be based on URL patterns, domains, link attributes, or custom logic.

## Filter by URL pattern

Use regular expressions to match specific URL structures:

```python
import re

async def parse(self, response):
    rv = self.response_view(response)

    # Only follow product URLs
    product_pattern = re.compile(r"/products?/[\w-]+")

    for link in rv.doc.cssselect("a"):
        href = link.get("href")
        if href:
            full_url = rv.urljoin(href)
            if product_pattern.search(full_url):
                yield rv.follow(href)
```

**Advanced URL filtering:**

```python
import re

async def parse(self, response):
    rv = self.response_view(response)

    # Define multiple patterns
    allowed_patterns = [
        re.compile(r"/products?/[\w-]+"),
        re.compile(r"/categories/[\w-]+"),
        re.compile(r"/search\?q="),
    ]

    # Exclude patterns
    excluded_patterns = [
        re.compile(r"/login"),
        re.compile(r"/logout"),
        re.compile(r"/admin"),
    ]

    for link in rv.doc.cssselect("a"):
        href = link.get("href")
        if href:
            full_url = rv.urljoin(href)

            # Check excluded first
            if any(pattern.search(full_url) for pattern in excluded_patterns):
                continue

            # Then check allowed
            if any(pattern.search(full_url) for pattern in allowed_patterns):
                yield rv.follow(href)
```


## Filter by domain/subdomain

Restrict crawling to specific domains:

```python
from urllib.parse import urlparse

async def parse(self, response):
    rv = self.response_view(response)

    allowed_domains = {"example.com", "shop.example.com"}

    for link in rv.doc.cssselect("a"):
        href = link.get("href")
        if href:
            full_url = rv.urljoin(href)
            domain = urlparse(full_url).netloc

            if domain in allowed_domains:
                yield rv.follow(href)
```

**Domain filtering with subdomains:**

```python
from urllib.parse import urlparse

async def parse(self, response):
    rv = self.response_view(response)

    base_domain = "example.com"

    for link in rv.doc.cssselect("a"):
        href = link.get("href")
        if href:
            full_url = rv.urljoin(href)
            domain = urlparse(full_url).netloc

            # Allow base domain and all subdomains
            if domain == base_domain or domain.endswith(f".{base_domain}"):
                yield rv.follow(href)
```


## Filter by link text or attributes

Select links based on visible text or HTML attributes:

```python
async def parse(self, response):
    rv = self.response_view(response)

    # Only follow links with specific text or CSS classes
    for link in rv.doc.cssselect("a"):
        link_text = link.text_content().strip().lower()
        css_class = link.get("class", "")

        # Follow category or product links
        if "category" in link_text or "product" in css_class:
            href = link.get("href")
            if href:
                yield rv.follow(href)
```

**Filter by data attributes:**

```python
async def parse(self, response):
    rv = self.response_view(response)

    # Follow links with specific data attributes
    for link in rv.doc.cssselect("a[data-type]"):
        link_type = link.get("data-type")

        if link_type in {"product", "category", "brand"}:
            href = link.get("href")
            if href:
                yield rv.follow(href)
```


## Filter by file extension

Avoid following links to files:

```python
async def parse(self, response):
    rv = self.response_view(response)

    # File extensions to skip
    skip_extensions = {".pdf", ".jpg", ".png", ".zip", ".exe", ".mp4"}

    for link in rv.doc.cssselect("a"):
        href = link.get("href")
        if href:
            full_url = rv.urljoin(href)

            # Check if URL ends with skipped extension
            if not any(full_url.lower().endswith(ext) for ext in skip_extensions):
                yield rv.follow(href)
```


## Filter by URL parameters

Filter based on query parameters:

```python
from urllib.parse import urlparse, parse_qs

async def parse(self, response):
    rv = self.response_view(response)

    for link in rv.doc.cssselect("a"):
        href = link.get("href")
        if href:
            full_url = rv.urljoin(href)
            parsed = urlparse(full_url)
            params = parse_qs(parsed.query)

            # Only follow search results with category parameter
            if "category" in params:
                yield rv.follow(href)
```


## Combining filters

Use multiple filter criteria together:

```python
import re
from urllib.parse import urlparse

class FilteredSpider(Spider):
    name = "filtered"
    start_urls = ["https://example.com"]

    def should_follow(self, url):
        """Centralized filtering logic."""
        parsed = urlparse(url)

        # Domain filter
        if parsed.netloc != "example.com":
            return False

        # URL pattern filter
        if not re.search(r"/(products?|categories)/", parsed.path):
            return False

        # Extension filter
        if parsed.path.lower().endswith((".pdf", ".jpg", ".png")):
            return False

        return True

    async def parse(self, response):
        rv = self.response_view(response)

        for link in rv.doc.cssselect("a"):
            href = link.get("href")
            if href:
                full_url = rv.urljoin(href)
                if self.should_follow(full_url):
                    yield rv.follow(href)
```


## Best practices

- **Filter early**: Avoid scheduling unnecessary requests to reduce queue size
- **Validate URLs before following**: Check patterns, domains, and URL structure
- **Test filters incrementally**: Start with broad filters, then refine based on results
- **Centralize filter logic**: Use helper methods for complex filtering rules
- **Log filtered URLs**: Track what's being excluded for debugging
- **Handle edge cases**: Account for relative URLs, fragments, and malformed links
- **Use allowed_domains**: Consider using built-in domain filtering when available
- **Document filter rules**: Comment why certain patterns are included/excluded

See also: [Crawl Ordering](crawl_ordering.md), [Pagination](pagination.md)