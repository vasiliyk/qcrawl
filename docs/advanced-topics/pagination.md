
Pagination is how websites split content across multiple pages. Different sites use different pagination mechanisms: "next" links, numbered pages, "load more" buttons, or infinite scroll. Understanding the pagination pattern is key to extracting all data.

## Simple next-page pagination

Follow a "next" or "→" link to the next page:

```python
async def parse(self, response):
    rv = self.response_view(response)

    # Extract items from current page
    for item in rv.doc.cssselect(".item"):
        yield self.extract_item(item)

    # Follow "next" link
    next_link = rv.doc.cssselect("a.next")
    if next_link:
        href = next_link[0].get("href")
        if href:
            yield rv.follow(href)
```

**Alternative selectors for "next" links:**

```python
async def parse(self, response):
    rv = self.response_view(response)

    # Extract items
    for item in rv.doc.cssselect(".item"):
        yield self.extract_item(item)

    # Try multiple next-link selectors
    next_selectors = [
        "a.next",
        "a[rel='next']",
        "a:contains('Next')",
        "li.next > a",
        "a.pagination-next",
    ]

    for selector in next_selectors:
        next_links = rv.doc.cssselect(selector)
        if next_links:
            href = next_links[0].get("href")
            if href:
                yield rv.follow(href)
                break
```


## Numbered pagination

Generate page URLs based on page numbers:

```python
from qcrawl.core.request import Request

async def parse(self, response):
    rv = self.response_view(response)

    # Extract items
    for item in rv.doc.cssselect(".item"):
        yield self.extract_item(item)

    # Generate page URLs
    current_page = response.request.meta.get("page", 1)
    max_pages = 10

    if current_page < max_pages:
        next_page = current_page + 1
        next_url = f"https://example.com/items?page={next_page}"
        yield Request(url=next_url, meta={"page": next_page})
```

**Dynamic max_pages detection:**

```python
async def parse(self, response):
    rv = self.response_view(response)

    # Extract items
    for item in rv.doc.cssselect(".item"):
        yield self.extract_item(item)

    # Detect total pages from pagination
    pagination_links = rv.doc.cssselect(".pagination a")
    if pagination_links:
        # Extract page numbers from links
        page_numbers = []
        for link in pagination_links:
            text = link.text_content().strip()
            if text.isdigit():
                page_numbers.append(int(text))

        max_pages = max(page_numbers) if page_numbers else 1
    else:
        max_pages = 1

    current_page = response.request.meta.get("page", 1)

    if current_page < max_pages:
        next_page = current_page + 1
        next_url = f"https://example.com/items?page={next_page}"
        yield Request(url=next_url, meta={"page": next_page})
```


## Load-more / infinite scroll

Handle AJAX-based pagination:

```python
from qcrawl.core.request import Request

async def parse(self, response):
    rv = self.response_view(response)

    # Extract items
    for item in rv.doc.cssselect(".item"):
        yield self.extract_item(item)

    # Check for AJAX endpoint
    page = response.request.meta.get("page", 1)
    max_pages = 20

    if page < max_pages:
        # API endpoint that returns more items
        api_url = f"https://example.com/api/items?offset={page * 20}"
        yield Request(
            url=api_url,
            meta={"page": page + 1}
        )
```

**Handle JSON responses:**

```python
async def parse(self, response):
    # Check if response is JSON
    if response.headers.get("Content-Type", "").startswith("application/json"):
        data = response.json()

        # Extract items from JSON
        for item in data.get("items", []):
            yield {
                "title": item.get("title"),
                "price": item.get("price"),
            }

        # Check for next page
        if data.get("has_more"):
            page = response.request.meta.get("page", 1)
            next_url = f"https://example.com/api/items?offset={page * 20}"
            yield Request(url=next_url, meta={"page": page + 1})
    else:
        # Handle HTML response
        rv = self.response_view(response)
        for item in rv.doc.cssselect(".item"):
            yield self.extract_item(item)
```


## Cursor-based pagination

Handle cursor/token-based pagination (common in APIs):

```python
async def parse(self, response):
    data = response.json()

    # Extract items
    for item in data.get("results", []):
        yield {
            "id": item["id"],
            "name": item["name"],
        }

    # Follow next cursor
    next_cursor = data.get("next_cursor")
    if next_cursor:
        next_url = f"https://api.example.com/items?cursor={next_cursor}"
        yield Request(url=next_url)
```


## Offset-based pagination

Common in REST APIs:

```python
async def parse(self, response):
    data = response.json()

    # Extract items
    items = data.get("items", [])
    for item in items:
        yield item

    # Calculate next offset
    current_offset = response.request.meta.get("offset", 0)
    limit = 20
    total = data.get("total_count")

    if total and current_offset + limit < total:
        next_offset = current_offset + limit
        next_url = f"https://api.example.com/items?offset={next_offset}&limit={limit}"
        yield Request(
            url=next_url,
            meta={"offset": next_offset}
        )
```


## Pagination with state tracking

Track pagination state across requests:

```python
async def parse(self, response):
    rv = self.response_view(response)

    # Extract items
    items_found = 0
    for item in rv.doc.cssselect(".item"):
        yield self.extract_item(item)
        items_found += 1

    # Track cumulative stats
    total_items = response.request.meta.get("total_items", 0) + items_found
    current_page = response.request.meta.get("page", 1)

    # Follow next page
    next_link = rv.doc.cssselect("a.next")
    if next_link and items_found > 0:
        href = next_link[0].get("href")
        if href:
            yield rv.follow(
                href,
                meta={
                    "page": current_page + 1,
                    "total_items": total_items
                }
            )
```


## Handling pagination errors

Gracefully handle pagination edge cases:

```python
async def parse(self, response):
    rv = self.response_view(response)

    # Extract items
    items = rv.doc.cssselect(".item")

    # Check if page has content
    if not items:
        self.logger.warning(f"No items found on page: {response.url}")
        return

    for item in items:
        yield self.extract_item(item)

    # Safety limit to prevent infinite loops
    current_page = response.request.meta.get("page", 1)
    max_pages = 100

    if current_page >= max_pages:
        self.logger.warning(f"Reached max pages limit: {max_pages}")
        return

    # Follow next link with error handling
    next_link = rv.doc.cssselect("a.next")
    if next_link:
        href = next_link[0].get("href")
        if href:
            yield rv.follow(href, meta={"page": current_page + 1})
```


## Best practices

- **Handle pagination limits**: Set reasonable max_pages to prevent infinite loops
- **Track page numbers**: Use meta to pass page state through requests
- **Detect pagination type**: Identify whether site uses links, numbers, or AJAX
- **Validate pagination**: Check for empty pages or duplicate content
- **Log pagination progress**: Track pages processed for debugging
- **Handle edge cases**: Account for single-page results, broken pagination
- **Respect rate limits**: Don't hammer pagination endpoints too quickly
- **Test thoroughly**: Verify pagination works from first to last page
- **Stop on empty pages**: Exit when no more items are found

See also: [Crawl Ordering](crawl_ordering.md), [Link Filtering](link_filtering.md)