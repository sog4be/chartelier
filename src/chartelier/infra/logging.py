"""Structured logging infrastructure for Chartelier.

This module provides JSON-formatted structured logging capabilities with
common fields for monitoring and debugging. It does NOT handle PII filtering
directly - that responsibility lies with the calling components.
"""

import hashlib
import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

__all__ = ["StructuredLogger", "get_logger", "redact_query"]


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs JSON-structured log entries."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_entry = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add any extra fields from the record
        excluded_fields = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
        }
        log_entry.update({key: value for key, value in record.__dict__.items() if key not in excluded_fields})

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class StructuredLogger:
    """Wrapper around standard logger with structured logging support."""

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize structured logger.

        Args:
            logger: The underlying Python logger instance.
        """
        self._logger = logger

    def _log(
        self,
        level: int,
        msg: str,
        **kwargs: Any,
    ) -> None:
        """Internal log method with extra fields support.

        Args:
            level: Log level.
            msg: Log message.
            **kwargs: Additional fields to include in the log entry.
        """
        extra = dict(kwargs)
        self._logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, msg, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        Configured StructuredLogger instance.
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.propagate = False

        # Set log level from environment variable
        log_level = os.getenv("CHARTELIER_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level, logging.INFO)
        logger.setLevel(level)

    return StructuredLogger(logger)


def redact_query(query: str, threshold: int = 16) -> str:
    """Redact long non-numeric strings in query for privacy.

    This is an optional utility function that components can use to
    redact sensitive information in query strings before logging.

    Args:
        query: The query string to redact.
        threshold: Minimum length of non-numeric strings to redact (default: 16).

    Returns:
        Query string with long non-numeric parts replaced by hashes.
    """

    def replace_long_string(match: re.Match[str]) -> str:
        """Replace long non-numeric strings with hash."""
        text = match.group(0)
        if len(text) >= threshold and not text.replace(".", "").replace("-", "").isdigit():
            hash_value = hashlib.sha256(text.encode()).hexdigest()[:8]
            return f"[REDACTED_{hash_value}]"
        return text

    # Pattern to match continuous non-whitespace sequences
    pattern = r"\S+"
    return re.sub(pattern, replace_long_string, query)
