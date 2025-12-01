"""Tests for qcrawl.runner.logging - Logging setup and output directory handling

Tests focus on the following behavior:
- Output directory creation for file paths
- Logging configuration with level filtering
- Custom format application
- Logger namespace handling (qcrawl.*)
- Dynamic reconfiguration
- File and stdout handler setup
"""

import logging

from qcrawl.runner.logging import ensure_output_dir, setup_logging

# ensure_output_dir Tests


def test_ensure_output_dir_creates_parent_for_file(tmp_path):
    """ensure_output_dir creates parent directories for file paths."""
    file_path = tmp_path / "data" / "output" / "results.json"

    ensure_output_dir(str(file_path))

    assert file_path.parent.exists()
    assert file_path.parent.is_dir()


def test_ensure_output_dir_creates_directory_path(tmp_path):
    """ensure_output_dir creates directory when path has no file extension."""
    dir_path = tmp_path / "output_directory"

    ensure_output_dir(str(dir_path))

    assert dir_path.exists()
    assert dir_path.is_dir()


def test_ensure_output_dir_ignores_stdout():
    """ensure_output_dir does nothing for stdout indicators."""
    # Should not raise - these are stdout indicators
    ensure_output_dir("-")
    ensure_output_dir("stdout")
    ensure_output_dir("STDOUT")


def test_ensure_output_dir_ignores_none():
    """ensure_output_dir does nothing for None path."""
    ensure_output_dir(None)


# setup_logging Integration Tests


def test_setup_logging_file_handler_writes_messages(tmp_path):
    """setup_logging with file handler actually writes log messages to file."""
    log_file = tmp_path / "test.log"

    setup_logging(level="INFO", log_file=str(log_file))

    # Write messages at different levels
    logger = logging.getLogger("qcrawl.test")
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")

    # Verify file was created and contains expected messages
    assert log_file.exists()
    content = log_file.read_text()

    # INFO level should show INFO and WARNING, but not DEBUG
    assert "Info message" in content
    assert "Warning message" in content
    assert "Debug message" not in content


def test_setup_logging_level_filtering_works(tmp_path):
    """setup_logging level parameter correctly filters messages."""
    log_file = tmp_path / "filtered.log"

    setup_logging(level="WARNING", log_file=str(log_file))

    logger = logging.getLogger("qcrawl.test")
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

    content = log_file.read_text()

    # WARNING level should show WARNING and ERROR, but not DEBUG or INFO
    assert "Warning message" in content
    assert "Error message" in content
    assert "Debug message" not in content
    assert "Info message" not in content


def test_setup_logging_qcrawl_namespace_loggers_work(tmp_path):
    """setup_logging configures qcrawl.* namespace loggers correctly."""
    log_file = tmp_path / "namespace.log"

    setup_logging(level="INFO", log_file=str(log_file))

    # Create loggers in qcrawl namespace
    spider_logger = logging.getLogger("qcrawl.core.spider")
    crawler_logger = logging.getLogger("qcrawl.core.crawler")

    spider_logger.info("Spider log")
    crawler_logger.warning("Crawler log")

    content = log_file.read_text()

    # Both qcrawl.* loggers should write to the log
    assert "Spider log" in content
    assert "Crawler log" in content


def test_setup_logging_custom_format_applies(tmp_path):
    """setup_logging custom format is applied to log output."""
    log_file = tmp_path / "custom_format.log"
    custom_format = "[%(levelname)s] %(message)s"

    setup_logging(level="INFO", log_file=str(log_file), log_format=custom_format)

    logger = logging.getLogger("qcrawl.test")
    logger.warning("Custom format test")

    content = log_file.read_text()

    # Should match custom format pattern
    assert "[WARNING] Custom format test" in content
    # Should NOT have timestamp or logger name (not in custom format)
    lines = content.strip().split("\n")
    # Simple format should result in short lines
    assert all(line.startswith("[") for line in lines if line)


def test_setup_logging_handles_string_level_names(tmp_path):
    """setup_logging accepts string level names (DEBUG, INFO, etc)."""
    log_file = tmp_path / "string_level.log"

    # Test various string level names
    setup_logging(level="DEBUG", log_file=str(log_file))

    logger = logging.getLogger("qcrawl.test")
    logger.debug("Debug level test")

    content = log_file.read_text()
    assert "Debug level test" in content


def test_setup_logging_handles_integer_levels(tmp_path):
    """setup_logging accepts integer log levels."""
    log_file = tmp_path / "int_level.log"

    # 20 = INFO level
    setup_logging(level=20, log_file=str(log_file))

    logger = logging.getLogger("qcrawl.test")
    logger.info("Integer level test")

    content = log_file.read_text()
    assert "Integer level test" in content


def test_setup_logging_can_be_reconfigured(tmp_path):
    """setup_logging can be called multiple times to reconfigure."""
    log_file = tmp_path / "reconfig.log"

    # Start with WARNING
    setup_logging(level="WARNING", log_file=str(log_file))
    logger = logging.getLogger("qcrawl.test")
    logger.info("Should not appear")

    # Reconfigure to DEBUG
    setup_logging(level="DEBUG", log_file=str(log_file))
    logger.debug("Should appear after reconfig")

    content = log_file.read_text()
    assert "Should appear after reconfig" in content
    assert "Should not appear" not in content


def test_setup_logging_updates_existing_qcrawl_loggers(tmp_path):
    """setup_logging updates already-created qcrawl loggers."""
    log_file = tmp_path / "existing_loggers.log"

    # Create logger before setup
    existing_logger = logging.getLogger("qcrawl.pre_existing")

    # Now configure logging
    setup_logging(level="WARNING", log_file=str(log_file))

    # Existing logger should respect new level
    existing_logger.info("Info should not appear")
    existing_logger.error("Error should appear")

    content = log_file.read_text()
    assert "Error should appear" in content
    assert "Info should not appear" not in content


def test_setup_logging_without_file_uses_stdout(capsys):
    """setup_logging without log_file parameter uses stdout handler."""
    setup_logging(level="INFO")

    logger = logging.getLogger("qcrawl.test")
    logger.info("Stdout test message")

    # Flush to ensure output is captured
    logging.getLogger().handlers[0].flush()

    # Message should appear in stdout
    captured = capsys.readouterr()
    assert "Stdout test message" in captured.out
