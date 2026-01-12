"""Logging configuration using beautilog."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from beautilog import logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logger.getLogger(name)


# Compatibility classes (kept for backwards compatibility)
class JSONFormatter(logging.Formatter):
    """Placeholder JSON formatter (beautilog handles this)."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record."""
        return super().format(record)


class ColorFormatter(logging.Formatter):
    """Placeholder color formatter (beautilog handles this)."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record."""
        return super().format(record)


class LogContext:
    """Context manager for adding fields to log records."""

    def __init__(self, **kwargs):
        """Initialize context with fields."""
        self.fields = kwargs
        self.token = None

    def __enter__(self):
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass
