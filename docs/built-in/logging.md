
qCrawl uses Python's standard logging module across components.

Default formatting is `%(asctime)s %(levelname)s %(name)s: %(message)s` (e.g. `2025-11-25 10:30:45,123 INFO qcrawl.core.engine: Starting crawler`).
You can customize logging via CLI flags, runtime settings, environment variables, or code.


## Configuration

### Via CLI (Command Line Interface)

```bash
# --log-level (default INFO) — sets the root logging level.
# --log-file — add a file handler in addition to console.
qcrawl --log-level DEBUG --log-file ./logs/crawl.log myspider
```

### Via toml config file

```toml
LOG_LEVEL = "DEBUG"
LOG_FILE = "./logs/crawl.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"
```

### Via environment variables

```bash
export QCRAWL_LOG_LEVEL=DEBUG
export QCRAWL_LOG_FILE=./logs/crawl.log
export QCRAWL_LOG_FORMAT="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
export QCRAWL_LOG_DATEFORMAT="%Y-%m-%d %H:%M:%S"
qcrawl myspider
```

### Via code

```python
from qcrawl.settings import Settings
from qcrawl.core.crawler import Crawler
from myproject.spiders import MySpider

settings = Settings(
    LOG_LEVEL="DEBUG",
    LOG_FILE="./logs/crawl.log",
    LOG_FORMAT="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    LOG_DATEFORMAT="%Y-%m-%d %H:%M:%S",
)
spider = MySpider()
crawler = Crawler(spider, runtime_settings=settings)
```


## Available Settings

| Setting          | Type        | Default                                             | Description                                            |
|------------------|-------------|-----------------------------------------------------|--------------------------------------------------------|
| `LOG_LEVEL`      | str         | `"INFO"`                                            | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL   |
| `LOG_FILE`       | str \| None | `None`                                              | Path to log file. If None, logs to stdout              |
| `LOG_FORMAT`     | str         | `"%(asctime)s %(levelname)s %(name)s: %(message)s"` | Python logging format string                           |
| `LOG_DATEFORMAT` | str \| None | `None`                                              | Date format for `%(asctime)s` (Python strftime format) |

### Format String Examples

```python
# Default format
"%(asctime)s %(levelname)s %(name)s: %(message)s"
# → 2025-11-25 10:30:45,123 INFO qcrawl.core.engine: Starting crawler

# Compact format with brackets
"%(asctime)s [%(levelname)s] %(name)s: %(message)s"
# → 2025-11-25 10:30:45,123 [INFO] qcrawl.core.engine: Starting crawler

# Minimal format
"[%(levelname)s] %(message)s"
# → [INFO] Starting crawler

# JSON-like format (requires custom formatter or structured logging library)
# For production JSON logging, consider using python-json-logger
```

### Date Format Examples

```python
# Default (None) - uses default Python logging format
None  # → 2025-11-25 10:30:45,123

# Custom date format (strftime)
"%Y-%m-%d %H:%M:%S"  # → 2025-11-25 10:30:45
"%Y/%m/%d %I:%M:%S %p"  # → 2025/11/25 10:30:45 AM
"%b %d %H:%M:%S"  # → Nov 25 10:30:45
```

## Notes

!!! note

    qCrawl logger writes console output to `sys.stdout` when no `LOG_FILE` is provided.
