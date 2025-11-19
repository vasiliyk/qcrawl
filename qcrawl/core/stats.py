import logging
import math
from collections import defaultdict
from datetime import datetime
from threading import RLock

logger = logging.getLogger(__name__)


class StatsCollector:
    """Thread-safe, synchronous statistics collector."""

    def __init__(self) -> None:
        self._stats: dict[str, int | float | str] = defaultdict(int)
        self._lock = RLock()  # Reentrant lock: safe for nested calls
        self._start_time: datetime | None = None
        self._finish_time: datetime | None = None

    def inc_value(self, key: str, count: int = 1) -> None:
        """Increment counter (thread-safe). Coerces non-numeric to 0."""
        with self._lock:
            current = self._stats[key]
            if not isinstance(current, (int, float)):
                current = 0
            self._stats[key] = current + count

    def set_counter(self, key: str, value: int | float) -> None:
        """Set a numeric counter (thread-safe)."""
        if not isinstance(value, (int, float)):
            raise TypeError("set_counter accepts only int or float")
        with self._lock:
            self._stats[key] = value

    def set_meta(self, key: str, value: str) -> None:
        """Set string metadata (thread-safe)."""
        if not isinstance(value, str):
            raise TypeError("set_meta accepts only str")
        with self._lock:
            self._stats[key] = value

    def get_value(
        self, key: str, default: int | float | str | None = None
    ) -> int | float | str | None:
        """Get value (thread-safe)."""
        with self._lock:
            return self._stats.get(key, default)

    def get_stats(self) -> dict[str, int | float | str]:
        """Get all stats (snapshot)."""
        with self._lock:
            return self._stats.copy()

    def open_spider(self, spider) -> None:
        """Called when spider opens."""
        start = datetime.now()
        with self._lock:
            self._start_time = start
            self.set_meta("start_time", self._start_time.isoformat())
            self.set_meta("spider_name", getattr(spider, "name", "unknown"))

    def close_spider(self, spider, reason: str = "finished") -> None:
        """Called when spider closes."""
        finish = datetime.now()
        with self._lock:
            self._finish_time = finish
            self.set_meta("finish_time", self._finish_time.isoformat())
            self.set_meta("finish_reason", reason)

            if self._start_time:
                elapsed = (self._finish_time - self._start_time).total_seconds()
                self.set_counter("elapsed_time_seconds", elapsed)

    def log_stats(self) -> str:
        """Log collected stats in pretty format."""
        stats = self.get_stats()
        lines = []
        for key in sorted(stats):
            value = stats[key]
            if isinstance(value, float):
                value = f"{value:.6g}" if math.isfinite(value) else str(value)
            elif isinstance(value, int):
                value = f"{value:,}"
            else:
                value = str(value)
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)
