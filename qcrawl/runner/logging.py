from __future__ import annotations

import logging
import sys
from pathlib import Path


def ensure_output_dir(export_path: str | None) -> None:
    """Create parent directory for `export_path` unless exporting to stdout."""
    if not export_path:
        return
    if str(export_path).lower() in {"-", "stdout"}:
        return
    p = Path(export_path)
    # If path looks like a file (has suffix), create parent; otherwise treat as directory.
    target_dir = p.parent if p.suffix else p
    target_dir.mkdir(parents=True, exist_ok=True)


def _normalize_level(level: str | int) -> int:
    """Coerce level name or integer-like value to a logging level int."""
    if isinstance(level, int):
        return int(level)
    if isinstance(level, str):
        lvl = getattr(logging, level.upper(), None)
        if isinstance(lvl, int):
            return lvl
        try:
            return int(level)
        except Exception:
            return logging.INFO
    return logging.INFO


def setup_logging(level: str | int = "INFO", log_file: str | None = None) -> None:
    """Configure logging for the CLI.

    - Ensures the root logger and the `qcrawl` namespace run at `level`.
    - Replaces existing handlers (uses `force=True` when supported).
    - Adjusts any pre-created `qcrawl.*` loggers to the chosen level.
    """
    lvl = _normalize_level(level)

    # Build handler
    handler: logging.Handler
    if log_file:
        handler = logging.FileHandler(log_file, encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stdout)

    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    # Try to use basicConfig with force=True (Python 3.8+). Fallback to manual replacement.
    try:
        logging.basicConfig(level=lvl, handlers=[handler], force=True)
    except TypeError:
        # Older Python without `force` -- replace root handlers manually
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        root.addHandler(handler)
        root.setLevel(lvl)
    else:
        # basicConfig succeeded; ensure root level explicitly set
        logging.getLogger().setLevel(lvl)

    # Ensure the qcrawl namespace and any existing qcrawl.* loggers honor the chosen level.
    logging.getLogger("qcrawl").setLevel(lvl)

    # Best-effort: update already-created qcrawl.* loggers that may have explicit levels set.
    try:
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if isinstance(name, str) and name.startswith("qcrawl"):
                try:
                    logging.getLogger(name).setLevel(lvl)
                except Exception:
                    # Do not fail overall if a logger cannot be adjusted.
                    continue
    except Exception:
        # Swallow unexpected errors (non-critical for logging setup)
        pass

    # Keep asyncio logger consistent with chosen level if present
    try:
        if "asyncio" in logging.Logger.manager.loggerDict:
            logging.getLogger("asyncio").setLevel(lvl)
    except Exception:
        pass
