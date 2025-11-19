
qCrawl uses Python's standard logging module across components.

Default formatting is `%(asctime)s %(levelname)s %(name)s: %(message)s` (e.g. `[TIME] [LEVEL] logger.name: MESSAGE`).
You can customize logging via CLI flags, runtime settings, environment variables, or code.


## Configuration

### Via CLI (Command Line Interface)

```bash
# --log-level (default INFO) — sets the root logging level.
# --log-file — add a file handler in addition to console.
qcrawl --log-level DEBUG --log-file ./logs/crawl.log myspider
```

### Via yaml config file

```yaml
LOG_LEVEL: DEBUG
LOG_FILE: ./logs/crawl.log
```

### Via code

```python
import logging
from qcrawl.settings import Settings
from qcrawl.core.crawler import Crawler
from myproject.spiders import MySpider

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[logging.StreamHandler(), logging.FileHandler("crawl.log")],
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = Settings.load()  # or Settings(...) to construct
spider = MySpider()
crawler = Crawler(spider, runtime_settings=settings)
```

!!! note

    qCrawl logger writes console output to `sys.stdout` when no `LOG_FILE` is provided.
