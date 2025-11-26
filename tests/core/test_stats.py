"""Tests for qcrawl.core.stats.StatsCollector"""

import time
from unittest.mock import Mock

import pytest

from qcrawl.core.stats import StatsCollector


def test_inc_value():
    """StatsCollector inc_value increments counters."""
    stats = StatsCollector()

    stats.inc_value("requests")
    stats.inc_value("requests")
    stats.inc_value("responses", count=5)

    assert stats.get_value("requests") == 2
    assert stats.get_value("responses") == 5


def test_inc_value_coerces_non_numeric():
    """StatsCollector inc_value coerces non-numeric values to 0."""
    stats = StatsCollector()

    stats.set_meta("key", "string_value")
    stats.inc_value("key")  # Should coerce to 0 then increment

    assert stats.get_value("key") == 1


def test_set_counter():
    """StatsCollector set_counter sets numeric values."""
    stats = StatsCollector()

    stats.set_counter("total", 100)
    stats.set_counter("average", 42.5)

    assert stats.get_value("total") == 100
    assert stats.get_value("average") == 42.5


def test_set_counter_rejects_non_numeric():
    """StatsCollector set_counter raises TypeError for non-numeric values."""
    stats = StatsCollector()

    with pytest.raises(TypeError, match="set_counter accepts only int or float"):
        stats.set_counter("key", "string")  # type: ignore[arg-type]


def test_set_meta():
    """StatsCollector set_meta sets string metadata."""
    stats = StatsCollector()

    stats.set_meta("spider_name", "test_spider")
    stats.set_meta("reason", "finished")

    assert stats.get_value("spider_name") == "test_spider"
    assert stats.get_value("reason") == "finished"


def test_set_meta_rejects_non_string():
    """StatsCollector set_meta raises TypeError for non-string values."""
    stats = StatsCollector()

    with pytest.raises(TypeError, match="set_meta accepts only str"):
        stats.set_meta("key", 123)  # type: ignore[arg-type]


def test_get_value_with_default():
    """StatsCollector get_value returns default for missing keys."""
    stats = StatsCollector()

    assert stats.get_value("missing") is None
    assert stats.get_value("missing", default=0) == 0


def test_get_stats():
    """StatsCollector get_stats returns snapshot of all stats."""
    stats = StatsCollector()

    stats.inc_value("requests", 10)
    stats.set_meta("spider", "test")

    snapshot = stats.get_stats()
    assert snapshot["requests"] == 10
    assert snapshot["spider"] == "test"

    # Snapshot is a copy
    stats.inc_value("requests", 5)
    assert snapshot["requests"] == 10  # Unchanged


def test_open_spider():
    """StatsCollector open_spider records start time and spider name."""
    stats = StatsCollector()
    spider = Mock()
    spider.name = "test_spider"

    stats.open_spider(spider)

    assert stats.get_value("start_time") is not None
    assert stats.get_value("spider_name") == "test_spider"
    assert stats._start_time is not None


def test_close_spider():
    """StatsCollector close_spider records finish time and elapsed time."""
    stats = StatsCollector()
    spider = Mock()
    spider.name = "test_spider"

    stats.open_spider(spider)
    time.sleep(0.01)
    stats.close_spider(spider, reason="finished")

    assert stats.get_value("finish_time") is not None
    assert stats.get_value("finish_reason") == "finished"
    elapsed = stats.get_value("elapsed_time_seconds")
    assert isinstance(elapsed, (int, float)) and elapsed > 0


def test_log_stats():
    """StatsCollector log_stats formats stats for logging."""
    stats = StatsCollector()

    stats.inc_value("requests", 1000)
    stats.set_counter("average", 3.14159)
    stats.set_meta("spider", "test")

    log_output = stats.log_stats()

    assert "requests: 1,000" in log_output
    assert "average: 3.14159" in log_output
    assert "spider: test" in log_output
