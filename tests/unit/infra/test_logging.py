"""Unit tests for structured logging module."""

import json
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from chartelier.infra.logging import StructuredLogger, get_logger, redact_query


class TestStructuredLogger:
    """Tests for StructuredLogger class."""

    def test_log_methods_exist(self) -> None:
        """Test that all standard log methods are available."""
        mock_logger = MagicMock(spec=logging.Logger)
        logger = StructuredLogger(mock_logger)

        # Test each log level method
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")

        # Verify mock was called for each level
        assert mock_logger.log.call_count == 5

    def test_extra_fields_passed(self) -> None:
        """Test that extra fields are passed to the underlying logger."""
        mock_logger = MagicMock(spec=logging.Logger)
        logger = StructuredLogger(mock_logger)

        logger.info(
            "test message",
            correlation_id="test-123",
            phase="validation",
            rows=100,
            cols=5,
        )

        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args
        assert call_args[0] == (logging.INFO, "test message")
        assert "extra" in call_args[1]
        extra = call_args[1]["extra"]
        assert extra["correlation_id"] == "test-123"
        assert extra["phase"] == "validation"
        assert extra["rows"] == 100
        assert extra["cols"] == 5


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_structured_logger(self) -> None:
        """Test that get_logger returns a StructuredLogger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, StructuredLogger)

    @patch.dict(os.environ, {"CHARTELIER_LOG_LEVEL": "DEBUG"})
    def test_log_level_from_env(self) -> None:
        """Test that log level is set from environment variable."""
        # Clear any existing handlers
        test_logger = logging.getLogger("test.env.logger")
        test_logger.handlers.clear()

        get_logger("test.env.logger")
        underlying = logging.getLogger("test.env.logger")
        assert underlying.level == logging.DEBUG

    @patch.dict(os.environ, {}, clear=True)
    def test_default_log_level(self) -> None:
        """Test that default log level is INFO when env var not set."""
        # Clear any existing handlers
        test_logger = logging.getLogger("test.default.logger")
        test_logger.handlers.clear()

        get_logger("test.default.logger")
        underlying = logging.getLogger("test.default.logger")
        assert underlying.level == logging.INFO

    def test_logger_reuse(self) -> None:
        """Test that calling get_logger twice returns configured logger."""
        get_logger("test.reuse")
        get_logger("test.reuse")

        # Both should use the same underlying logger
        underlying = logging.getLogger("test.reuse")
        assert len(underlying.handlers) == 1


class TestStructuredFormatter:
    """Tests for StructuredFormatter output format."""

    def test_json_format_output(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test that logs are output in JSON format."""
        # Clear existing handlers
        test_logger = logging.getLogger("test.json.format")
        test_logger.handlers.clear()

        logger = get_logger("test.json.format")
        logger.info("test message", correlation_id="abc-123", rows=50)

        # Capture stdout
        captured = capfd.readouterr()

        # Parse as JSON
        log_entry = json.loads(captured.out.strip())

        # Verify structure
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "test message"
        assert log_entry["logger"] == "test.json.format"
        assert log_entry["correlation_id"] == "abc-123"
        assert log_entry["rows"] == 50
        assert "ts" in log_entry  # Timestamp should be present

    def test_timestamp_format(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test that timestamp is in ISO format with timezone."""
        # Clear existing handlers
        test_logger = logging.getLogger("test.timestamp")
        test_logger.handlers.clear()

        logger = get_logger("test.timestamp")
        logger.info("timestamp test")

        captured = capfd.readouterr()
        log_entry = json.loads(captured.out.strip())

        # Verify timestamp format (ISO 8601 with timezone)
        ts = log_entry["ts"]
        assert "T" in ts  # Date-time separator
        assert ts.endswith(("Z", "+00:00")) or "+" in ts  # Has timezone


class TestRedactQuery:
    """Tests for redact_query function."""

    def test_short_strings_not_redacted(self) -> None:
        """Test that short strings are not redacted."""
        query = "SELECT * FROM table WHERE id = 123"
        result = redact_query(query)
        assert result == query

    def test_long_non_numeric_strings_redacted(self) -> None:
        """Test that long non-numeric strings are redacted."""
        query = "SELECT verylongsecretpasswordstring FROM table"
        result = redact_query(query)
        assert "verylongsecretpasswordstring" not in result
        assert "[REDACTED_" in result

    def test_numeric_strings_not_redacted(self) -> None:
        """Test that long numeric strings are not redacted."""
        query = "SELECT * FROM table WHERE id = 12345678901234567890"
        result = redact_query(query)
        assert "12345678901234567890" in result

    def test_mixed_content_partial_redaction(self) -> None:
        """Test that only long non-numeric parts are redacted."""
        query = "apikey=extremelylongsecretapikey123 AND id=456"
        result = redact_query(query, threshold=16)
        assert "extremelylongsecretapikey123" not in result
        assert "[REDACTED_" in result
        assert "456" in result  # Short numeric not redacted

    def test_custom_threshold(self) -> None:
        """Test that custom threshold works correctly."""
        query = "shortkey longerkeyvalue"
        result = redact_query(query, threshold=10)
        assert "shortkey" in result  # Below threshold
        assert "longerkeyvalue" not in result  # Above threshold
        assert "[REDACTED_" in result

    def test_consistent_hash(self) -> None:
        """Test that same string produces same hash."""
        query = "SELECT supersecretpasswordvalue FROM table"
        result1 = redact_query(query)
        result2 = redact_query(query)
        assert result1 == result2  # Should be deterministic

    def test_preserves_structure(self) -> None:
        """Test that query structure is preserved."""
        query = "SELECT col1, verylongsecretcolumnname, col3 FROM table"
        result = redact_query(query)
        parts = result.split()
        assert parts[0] == "SELECT"
        assert parts[1] == "col1,"
        assert "[REDACTED_" in parts[2]
        assert parts[3] == "col3"
        assert parts[4] == "FROM"
        assert parts[5] == "table"
