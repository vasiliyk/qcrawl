
qCrawl follows a practical testing philosophy focused on quality over quantity:

- **Test behavior, not implementation** - Avoid testing private methods or internal details
- **Mock at boundaries** - Mock external dependencies only,  not internal qCrawl code
- **Follow pytest best practices** - Use fixtures, parametrization, clear organization, AAA pattern
- **High-value integration tests** - Cover all critical paths with integration tests

## Test Types

### Unit Tests (Fast, Isolated)

Located in: `tests/`

**When to write:**

- Testing argument parsing, validation logic
- Testing pure functions without I/O
- Testing class initialization and configuration

**Example:**
```python
def test_parse_args_basic(monkeypatch):
    """parse_args correctly parses CLI arguments."""
    monkeypatch.setattr(sys, "argv", ["qcrawl", "spider:Spider", "--export", "out.json"])

    args = cli.parse_args()

    assert args.spider == "spider:Spider"
    assert args.export == "out.json"
```

**Characteristics:**

- Fast (< 100ms each)
- No external dependencies
- Can mock internal components for isolation
- Run frequently during development

### Integration Tests (Real Behavior)

Located in: `tests/integration/`

**When to write:**

- Testing end-to-end spider execution
- Testing actual HTTP crawling behavior
- Testing export/storage functionality
- Testing middleware chains

**Example:**
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_spider_crawls_real_http(httpbin_server, args_no_export):
    """Spider successfully crawls and parses real HTTP responses."""
    class TestSpider(Spider):
        name = "test"
        start_urls = [f"{httpbin_server}/json"]

        async def parse(self, response):
            data = response.json()
            yield {"title": data.get("slideshow", {}).get("title")}

    # Run against REAL HTTP server (Docker container)
    await run(TestSpider, args_no_export, spider_settings, runtime_settings)

    # Verify actual behavior (output written to stdout)
```

**Characteristics:**

- Slower (requires Docker containers)
- Tests against real services (HTTP servers, Redis)
- NO mocking of internal qCrawl components
- Run before commits/PRs

## Mocking Strategy: "Mock at Boundaries"

### DO Mock (External Dependencies)

Mock things you **don't control**:

```python
# Mock HTTP client (external dependency)
with patch("qcrawl.core.downloader.aiohttp.ClientSession"):
    ...

# Mock Redis (external service)
with patch("redis.asyncio.Redis"):
    ...

# Mock file system for unit tests
with patch("pathlib.Path.write_text"):
    ...

# Mock sys.argv for CLI tests
monkeypatch.setattr(sys, "argv", ["qcrawl", "spider:Spider"])
```

### DON'T Mock (Internal Components)

**Don't mock** things you **control** and want to test:

```python
# BAD - Don't mock internal qCrawl components
with patch("qcrawl.core.spider.Spider"):  # NO
    ...

with patch("qcrawl.core.crawler.Crawler"):  # NO
    ...

with patch("qcrawl.core.engine.CrawlEngine"):  # NO
    ...

# GOOD - Let internal components run naturally
spider = MySpider()
await crawler.crawl()  # Real execution
```

**Why?** Mocking internal components makes tests brittle and misses integration bugs. Integration tests should test **actual behavior**.

## Using Docker with Testcontainers

For integration tests, use real services via Docker instead of mocking.

### Setup

Install qCrawl with dev dependencies (includes testcontainers, pytest, and other test tools):

```bash
pip install -e ".[dev]"  # For local development
# OR
pip install qcrawl[dev]  # From PyPI
```

This installs all development dependencies including:

- `testcontainers` - Docker containers for testing
- `pytest`, `pytest-asyncio`, `pytest-cov` - Testing framework
- `ruff`, `mypy` - Linting and type checking
- `qcrawl[redis]`, `qcrawl[camoufox]` - Optional qCrawl features

### HTTP Server Fixture

```python
import pytest
from testcontainers.core.container import DockerContainer

@pytest.fixture(scope="module")
def httpbin_server():
    """Start httpbin container for testing."""
    container = DockerContainer("kennethreitz/httpbin:latest")
    container.with_exposed_ports(80)
    container.start()

    host = container.get_container_host_ip()
    port = container.get_exposed_port(80)

    yield f"http://{host}:{port}"

    container.stop()
```

### Using in Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_spider_against_real_http(httpbin_server):
    """Test spider against real HTTP server - NO MOCKING."""
    class JsonSpider(Spider):
        name = "json"
        start_urls = [f"{httpbin_server}/json"]

        async def parse(self, response):
            yield response.json()

    # Runs against REAL HTTP server in Docker
    await run(JsonSpider, args, spider_settings, runtime_settings)
```

**Benefits:**

- Tests actual HTTP behavior (redirects, timeouts, headers)
- Catches real integration bugs
- More confidence than mocked tests

## Best Practices

### 1. Use Pytest Fixtures

```python
# GOOD - Use fixtures
@pytest.fixture
def sample_spider():
    return MySpider()

def test_spider_init(sample_spider):
    assert sample_spider.name == "my_spider"

# BAD - Avoid class-based setup
class TestSpider:  # Don't do this
    def setup_method(self):
        self.spider = MySpider()
```

### 2. Parametrize for Multiple Scenarios

```python
@pytest.mark.parametrize("export_value,expected_output", [
    (None, "stdout"),
    ("-", "stdout"),
    ("file.json", "file"),
])
def test_export_variations(export_value, expected_output):
    args = argparse.Namespace(export=export_value)
    result = determine_output(args)
    assert result == expected_output
```

### 3. Follow AAA Pattern

```python
def test_spider_extracts_data():
    # Arrange
    spider = MySpider()
    response = create_test_response()

    # Act
    items = list(spider.parse(response))

    # Assert
    assert len(items) == 2
    assert items[0]["title"] == "Test"
```

### 4. Use Clear Assertions with Messages

```python
# GOOD - Clear assertion messages
assert len(items) > 0, "Should extract at least one item"
assert "title" in item, "Item should have title field"

# BAD - No context on failure
assert len(items) > 0
assert "title" in item
```

### 5. Test Public API Only

```python
# GOOD - Test public methods
def test_spider_parse():
    spider = MySpider()
    items = spider.parse(response)
    assert items

# BAD - Don't test private methods
def test_spider_internal_helper():
    spider = MySpider()
    result = spider._internal_helper()  # Private method
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Unit Tests Only (Fast)
```bash
pytest -m "not integration"
```

### Run Integration Tests Only
```bash
pytest -m integration
# OR
pytest tests/integration/
```

### Run Specific Test
```bash
pytest tests/test_cli.py::test_parse_args_basic -v
```

### Run with Coverage
```bash
pytest --cov=qcrawl --cov-report=term-missing
```

### Skip Slow Tests
```bash
pytest -m "not integration" --maxfail=1  # Fast feedback
```

## Test Organization

```
tests/
├── core/
│   ├── queues/
│   │   ├── test_factory.py
│   │   └── test_memory_queue.py
│   ├── conftest.py            # Core-specific fixtures
│   ├── test_spider.py
│   ├── test_engine.py
│   └── ...
├── downloaders/
│   ├── test_downloader.py
│   ├── test_camoufox.py
│   └── ...
├── middleware/
│   ├── downloader/
│   │   ├── test_retry.py
│   │   ├── test_cookies.py
│   │   └── ...
│   ├── spider/
│   │   ├── test_depth.py
│   │   ├── test_offsite.py
│   │   └── ...
│   ├── conftest.py            # Middleware fixtures
│   └── test_manager.py
├── pipelines/
│   ├── test_manager.py
│   ├── test_validation.py
│   └── ...
├── runner/
│   ├── test_export.py
│   ├── test_run.py
│   └── ...
├── utils/
│   ├── test_url.py
│   ├── test_fingerprint.py
│   └── ...
├── integration/               # Require Docker
│   ├── test_runner.py
│   ├── test_camoufox.py
│   └── test_redis_queue.py
├── conftest.py                # Shared fixtures
├── test_cli.py
└── ...
```

### Section Comments

Organize tests with clear section comments:

```python
# Initialization Tests

def test_spider_init_valid():
    """Spider initializes with valid parameters."""
    ...

def test_spider_init_invalid():
    """Spider raises error with invalid parameters."""
    ...

# Parsing Tests

def test_parse_html():
    """Spider parses HTML correctly."""
    ...

# Error Handling Tests

def test_parse_handles_missing_elements():
    """Spider gracefully handles missing HTML elements."""
    ...
```
