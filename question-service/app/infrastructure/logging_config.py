"""Centralized logging configuration for the question service.

This module provides structured logging setup with support for console,
file, and JSON-formatted logging for monitoring systems.
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.config import settings


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to console output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Colored log string
        """
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for subsequent formatters
        record.levelname = levelname

        return formatted


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    json_format: bool = False,
    enable_file_logging: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """Configure logging for the question service.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (uses settings if not provided)
        json_format: Whether to use JSON format for logs
        enable_file_logging: Whether to enable file logging
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep

    Raises:
        ValueError: If log_level is invalid
    """
    # Determine log level
    if log_level is None:
        log_level = settings.log_level

    # Validate log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    console_formatter: logging.Formatter
    if json_format:
        # Use JSON formatter for console
        console_formatter = JSONFormatter()
    else:
        # Use colored formatter for console
        console_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(module)s:%(funcName)s:%(lineno)d - %(message)s"
        )
        console_formatter = ColoredFormatter(console_format)

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (if enabled)
    if enable_file_logging:
        # Determine log file path
        if log_file is None:
            log_file = settings.log_file

        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(numeric_level)

        # Always use JSON format for file logs (better for parsing)
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"File logging enabled: {log_file}")

    root_logger.info(
        f"Logging configured: level={log_level}, "
        f"file_logging={enable_file_logging}, "
        f"json_format={json_format}"
    )


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding extra context to log records.

    Example:
        with LogContext(request_id="123", user_id="456"):
            logger.info("Processing request")
    """

    def __init__(self, **kwargs: Any):
        """Initialize log context with extra fields.

        Args:
            **kwargs: Extra fields to add to log records
        """
        self.extra = kwargs
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self) -> "LogContext":
        """Enter context and modify log record factory."""

        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = self.old_factory(*args, **kwargs)
            record.extra = self.extra
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context and restore original log record factory."""
        logging.setLogRecordFactory(self.old_factory)
