"""Logging configuration and formatters."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add custom fields if present
        if hasattr(record, "trace_id"):
            log_obj["trace_id"] = record.trace_id
        if hasattr(record, "span_id"):
            log_obj["span_id"] = record.span_id
        if hasattr(record, "agent_name"):
            log_obj["agent_name"] = record.agent_name

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


class ColorFormatter(logging.Formatter):
    """Colored formatter for console output."""

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class LogContext:
    """Context manager for adding fields to log records."""

    def __init__(self, **kwargs):
        """Initialize context with fields."""
        self.fields = kwargs
        self.token = None

    def __enter__(self):
        """Enter context."""
        # Add fields to logger
        logger = logging.getLogger()
        for handler in logger.handlers:
            if hasattr(handler, "filters"):
                for field_name, field_value in self.fields.items():
                    setattr(handler, field_name, field_value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        logger = logging.getLogger()
        for handler in logger.handlers:
            for field_name in self.fields:
                if hasattr(handler, field_name):
                    delattr(handler, field_name)


def setup_logging(
    json_file: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """Setup logging with console and optional file output.

    Args:
        json_file: Path to JSON log file (optional)
        console_level: Console handler log level
        file_level: File handler log level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler with color
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_formatter = ColorFormatter(
        "%(levelname)s | %(name)s | %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with JSON (if specified)
    if json_file:
        json_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(json_file)
        file_handler.setLevel(file_level)
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
