from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import orjson
import yaml

from qcrawl.core.spider import Spider
from qcrawl.runner import ensure_output_dir, run_async, setup_logging
from qcrawl.settings import Settings as RuntimeSettings
from qcrawl.utils.env import parse_literal


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level, args.log_file)
    ensure_output_dir(args.export)

    settings = SpiderConfig()
    if args.settings_file:
        try:
            settings = SpiderConfig.from_file(args.settings_file)
        except Exception as e:
            logging.error("Failed to load settings file %s: %s", args.settings_file, e)
            raise SystemExit(2) from e
    settings.merge_cli(args)

    runtime_settings = RuntimeSettings.load(
        config_file=args.settings_file, log_level=args.log_level, log_file=args.log_file
    )

    try:
        spider_cls = load_spider_class(args.spider)
    except Exception as e:
        logging.error("Failed to load spider %s: %s", args.spider, e)
        raise SystemExit(2) from e

    try:
        asyncio.run(run_async(spider_cls, args, settings, runtime_settings))
    except KeyboardInterrupt:
        print("\nInterrupted, exiting...")
        raise SystemExit(130) from None


@dataclass
class SpiderConfig:
    spider_args: dict[str, object] = field(default_factory=dict)
    concurrency: int | None = None
    concurrency_per_domain: int | None = None
    delay_per_domain: float | None = None
    max_depth: int | None = None

    @classmethod
    def from_file(cls, path: str) -> SpiderConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Settings file not found: {path}")
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(text) or {}
        else:
            data = orjson.loads(text)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> SpiderConfig:
        spider_args = data.get("spider_args", {})
        if not isinstance(spider_args, dict):
            spider_args = {}

        def to_int(val) -> int | None:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return int(val)
            return None

        def to_float(val) -> float | None:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return float(val)
            return None

        return cls(
            spider_args=spider_args,
            concurrency=to_int(data.get("concurrency")),
            concurrency_per_domain=to_int(data.get("concurrency_per_domain")),
            delay_per_domain=to_float(data.get("delay_per_domain")),
            max_depth=to_int(data.get("max_depth")),
        )

    def merge_cli(self, args: argparse.Namespace) -> None:
        for key, value in getattr(args, "setting", []):
            self.spider_args[key] = value
        for attr in ("concurrency", "concurrency_per_domain", "delay_per_domain", "max_depth"):
            val = getattr(args, attr, None)
            if val is not None:
                setattr(self, attr, val)
                self.spider_args[attr] = val


def _parse_kv(s: str) -> tuple[str, object]:
    if "=" not in s:
        raise argparse.ArgumentTypeError("must be KEY=VALUE")
    key, val = s.split("=", 1)
    key = key.strip()
    raw = val.strip()

    if raw.startswith("{") or raw.startswith("["):
        try:
            return key, orjson.loads(raw)
        except Exception:
            pass
    return key, parse_literal(raw)


class KeyValueListAction(argparse.Action):
    """Argparse action that accepts a single KEY=VALUE string per `-s` invocation.
    Append (key, value) tuples to the destination list. Use multiple `-s` flags
    to provide multiple settings.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, [])
        target: list[tuple[str, object]] = getattr(namespace, self.dest)
        if not isinstance(values, str):
            raise argparse.ArgumentTypeError("Invalid setting value")
        try:
            pair = _parse_kv(values)
        except Exception as e:
            raise argparse.ArgumentError(self, f"Invalid setting {values!r}: {e}") from e
        target.append(pair)


def load_spider_class(path: str) -> type[Spider]:
    if ":" in path:
        mod_name, cls_name = path.split(":", 1)
    elif "." in path:
        mod_name, cls_name = path.rsplit(".", 1)
    else:
        mod_name, cls_name = path, "Spider"

    module: ModuleType = importlib.import_module(mod_name)
    cls = getattr(module, cls_name, None)
    if cls is None:
        raise ImportError(f"Module {mod_name!r} has no attribute {cls_name!r}")
    if not isinstance(cls, type) or not issubclass(cls, Spider):
        raise TypeError(f"{cls_name!r} is not a subclass of Spider")
    return cls


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a qcrawl Spider", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    g_spider = parser.add_argument_group("Spider & Crawl Settings")
    g_spider.add_argument(
        "spider", help="Spider path: module:Class, module.Class, or module (exports Spider)"
    )
    g_spider.add_argument(
        "--setting",
        "-s",
        action=KeyValueListAction,
        default=[],
        help="Set spider setting / constructor arg: KEY=VALUE (use multiple -s to set multiple values)",
    )

    g_output = parser.add_argument_group("Output & Export")
    g_output.add_argument("--export", help="Export destination (Local path or '-'/'stdout')")
    g_output.add_argument(
        "--export-format", default="ndjson", choices=["ndjson", "json", "csv", "xml"]
    )
    g_output.add_argument("--export-mode", default="buffered", choices=["buffered", "stream"])
    g_output.add_argument("--export-buffer-size", type=int, default=500)

    g_config = parser.add_argument_group("Configuration")
    g_config.add_argument(
        "--settings-file",
        help="Load settings from JSON/YAML (applies to runtime Settings and spider config)",
    )

    g_log = parser.add_argument_group("Logging & Debugging")
    g_log.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )
    g_log.add_argument("--log-file", help="Log to file")

    g_help = parser.add_argument_group("Help & Version")
    from qcrawl import __version__

    g_help.add_argument("--version", action="version", version=f"qcrawl {__version__}")

    return parser.parse_args()
