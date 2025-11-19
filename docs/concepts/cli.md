
You can run spiders programmatically within your Python code or via the command-line interface (CLI) provided by qCrawl.
Here let's explore CLI usage.

For quick usage example refer to the [5 minutes overview](../getting-started/overview.md).
For more details on configuration refer to the [Settings documentation](settings.md).

## Configuration precedence
qCrawl has the following precedence order for applying settings:

``` mermaid
flowchart LR
    A(qCrawl defaults) --> B(YML Config file) --> C(Environment variables) --> D(CLI) --> E(Programmatic overrides)
```

## CLI usage

CLI is intended to run spiders with minimal setup. The basic syntax is:

```bash
qcrawl <spider> [options]
```
Where `<spider>` is the spider class path in the format `module:ClassName`. It is the only required argument.


### Spider & Crawl Settings

| Option            | Type        | Default  | Description                                                                                                                 |
|-------------------|-------------|----------|-----------------------------------------------------------------------------------------------------------------------------|
| `spider`          | `str`       | n/a      | Spider path: module:Class, module.Class, or module.                                                                         |
| `--setting`, `-s` | `key=value` | `[]`     | Per-spider settings using `key=value` pairs (repeatable). Values can be JSON arrays/objects when wrapped in `[...]`/`{...}` |

Example

```bash
# --setting used multiple times
qcrawl mymodule:MySpider \
  --setting concurrency=8 \
  --setting concurrency_per_domain=2 \
  --setting delay_per_domain=0.5 \
  --setting max_depth=3
```

For full list of settings refer to the [Settings documentation](settings.md).


### Output & Export

| Option                 | Type                     | Default    | Description                                                                            |
|------------------------|--------------------------|------------|----------------------------------------------------------------------------------------|
| `--export <path>`      | `str`                    | `None`     | Export destination (local path or `-` / `stdout` for stdout)                           |
| `--export-format`      | `ndjson, json, csv, xml` | `ndjson`   | Export format.                                                                         |
| `--export-mode`        | `buffered, stream`       | `buffered` | Export mode for JSON/NDJSON (buffered writes all at once, stream writes item-by-item). |
| `--export-buffer-size` | `int`                    | `500`      | Buffer size (only used when `--export-format=json` and `--export-mode=buffered`).      |


### Configuration File

| Option            | Type  | Default | Description                                                         |
|-------------------|-------|---------|---------------------------------------------------------------------|
| `--settings-file` | `str` | `None`  | Load spider settings from JSON/YAML (merged with `--setting` args). |


### Logging & Debugging

| Option          | Type               | Default | Description                                                           |
|-----------------|--------------------|---------|-----------------------------------------------------------------------|
| `--log-level`   | `str`              | `INFO`  | Logging verbosity (choices: `DEBUG, INFO, WARNING, ERROR, CRITICAL`). |
| `--log-file`    | `str`              | `None`  | Write logs to file.                                                   |


### Help & Version

| Option       | Type | Default | Description                             |
|--------------|------|---------|-----------------------------------------|
| `--version`  | flag | n/a     | Print qCrawl version and exit.          |
| `--help`     | flag | n/a     | Show help grouped by sections and exit. |
