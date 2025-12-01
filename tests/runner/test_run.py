"""Tests for qcrawl.runner.run - SpiderRunner programmatic API

Tests focus on the following behavior:
- Settings initialization and filtering
- Async/sync execution modes
- Error handling for event loop conflicts
"""

import argparse
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from qcrawl.core.spider import Spider
from qcrawl.runner.run import SpiderRunner


# Test Helper Spider
class SampleSpider(Spider):
    """Minimal spider for testing."""

    name = "sample"
    start_urls = ["http://example.com"]

    async def parse(self, response):
        yield {"data": "test"}


# Initialization Tests


def test_spider_runner_init_defaults():
    """SpiderRunner initializes with default settings."""
    runner = SpiderRunner()

    assert runner.log_level == "INFO"
    assert runner.log_file is None
    assert runner.runtime_settings is not None


def test_spider_runner_init_custom_log_level():
    """SpiderRunner respects custom log level."""
    runner = SpiderRunner(settings={"log_level": "DEBUG"})

    assert runner.log_level == "DEBUG"


def test_spider_runner_init_custom_log_file(tmp_path):
    """SpiderRunner respects custom log file."""
    log_file = str(tmp_path / "test.log")
    runner = SpiderRunner(settings={"log_file": log_file})

    assert runner.log_file == log_file


def test_spider_runner_filters_runner_only_keys():
    """SpiderRunner filters out runner-only keys from runtime settings."""
    runner = SpiderRunner(
        settings={
            "log_level": "DEBUG",
            "log_file": "/tmp/test.log",
            "export": "output.json",
            "export_format": "json",
            "export_mode": "buffered",
            "export_buffer_size": 100,
            "setting": ["key=value"],
            "CONCURRENCY": 20,  # This should NOT be filtered
        }
    )

    # Runner settings should be available
    assert runner.log_level == "DEBUG"
    assert runner.log_file == "/tmp/test.log"

    # Runtime settings should NOT contain runner-only keys
    # but SHOULD contain crawler settings like CONCURRENCY
    assert runner.runtime_settings.CONCURRENCY == 20


def test_spider_runner_case_insensitive_filtering():
    """SpiderRunner filters keys case-insensitively in SKIP_KEYS check."""
    runner = SpiderRunner(
        settings={
            "log_level": "WARNING",
            "EXPORT": "out.json",  # Uppercase EXPORT should be filtered
            "export_format": "csv",  # Lowercase also filtered
            "TIMEOUT": 60,  # Should NOT be filtered
        }
    )

    # Runner settings with correct lowercase key names
    assert runner.log_level == "WARNING"

    # Non-filtered keys should be in runtime settings
    assert runner.runtime_settings.TIMEOUT == 60


# crawl() Async Method Tests


@pytest.mark.asyncio
async def test_spider_runner_crawl_calls_run_async():
    """SpiderRunner.crawl() calls run_async with correct arguments."""
    runner = SpiderRunner(settings={"export": "output.json", "export_format": "ndjson"})

    with patch("qcrawl.runner.run.run_async", new_callable=AsyncMock) as mock_run:
        await runner.crawl(SampleSpider, custom_arg="test_value")

        # Verify run_async was called
        mock_run.assert_called_once()

        # Extract call arguments
        call_args = mock_run.call_args
        spider_cls, args, spider_settings, runtime_settings = call_args[0]

        # Verify spider class
        assert spider_cls is SampleSpider

        # Verify args namespace
        assert isinstance(args, argparse.Namespace)
        assert args.export == "output.json"
        assert args.export_format == "ndjson"

        # Verify spider kwargs passed through
        assert spider_settings.spider_args == {"custom_arg": "test_value"}

        # Verify runtime settings passed
        assert runtime_settings is runner.runtime_settings


@pytest.mark.asyncio
async def test_spider_runner_crawl_without_export():
    """SpiderRunner.crawl() works without export settings."""
    runner = SpiderRunner()

    with patch("qcrawl.runner.run.run_async", new_callable=AsyncMock) as mock_run:
        await runner.crawl(SampleSpider)

        call_args = mock_run.call_args
        _, args, _, _ = call_args[0]

        assert args.export is None
        assert args.export_format is None


# crawl_sync() Method Tests


def test_spider_runner_crawl_sync_works_without_loop():
    """SpiderRunner.crawl_sync() works when no event loop is running."""
    runner = SpiderRunner()

    with patch("qcrawl.runner.run.run_async", new_callable=AsyncMock):
        # Should complete without error
        runner.crawl_sync(SampleSpider)


def test_spider_runner_crawl_sync_raises_in_running_loop():
    """SpiderRunner.crawl_sync() raises RuntimeError when called from async context."""

    async def test_in_loop():
        runner = SpiderRunner()
        with pytest.raises(RuntimeError, match="Event loop is already running.*crawl.*instead"):
            runner.crawl_sync(SampleSpider)

    # Run the test inside an event loop
    asyncio.run(test_in_loop())


def test_spider_runner_crawl_sync_passes_kwargs():
    """SpiderRunner.crawl_sync() passes spider kwargs correctly."""
    runner = SpiderRunner()

    with patch.object(runner, "crawl", new_callable=AsyncMock) as mock_crawl:
        runner.crawl_sync(SampleSpider, arg1="value1", arg2="value2")

        # Verify crawl was called with correct kwargs
        mock_crawl.assert_called_once_with(SampleSpider, arg1="value1", arg2="value2")


# Settings Loading Tests


def test_spider_runner_loads_settings_file(tmp_path):
    """SpiderRunner loads settings from config file."""
    config_file = tmp_path / "config.toml"
    # TOML format: flat structure, no section header
    config_file.write_text("CONCURRENCY = 15\nTIMEOUT = 45\n")

    runner = SpiderRunner(settings={"settings_file": str(config_file)})

    assert runner.runtime_settings.CONCURRENCY == 15
    assert runner.runtime_settings.TIMEOUT == 45


def test_spider_runner_merges_settings_with_config_file(tmp_path):
    """SpiderRunner merges explicit settings with config file."""
    config_file = tmp_path / "config.toml"
    # TOML format: flat structure, no section header
    config_file.write_text("CONCURRENCY = 15\nTIMEOUT = 30\n")

    runner = SpiderRunner(
        settings={
            "settings_file": str(config_file),
            "TIMEOUT": 60,  # Override config file value
        }
    )

    assert runner.runtime_settings.CONCURRENCY == 15  # From file
    assert runner.runtime_settings.TIMEOUT == 60  # Overridden


# Output Directory Creation Tests


@patch("qcrawl.runner.run.ensure_output_dir")
def test_spider_runner_creates_output_dir(mock_ensure_dir):
    """SpiderRunner ensures output directory exists for export path."""
    SpiderRunner(settings={"export": "/path/to/output.json"})

    mock_ensure_dir.assert_called_once_with("/path/to/output.json")


@patch("qcrawl.runner.run.ensure_output_dir")
def test_spider_runner_skips_output_dir_without_export(mock_ensure_dir):
    """SpiderRunner skips output directory creation when no export."""
    SpiderRunner()

    mock_ensure_dir.assert_called_once_with(None)
