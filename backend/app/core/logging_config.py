"""
Centralized logging configuration with structured logging support.
"""
import json
import logging
import logging.config
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import settings

# Context variable for request ID correlation across async tasks.
# Used by RequestLoggingMiddleware to propagate request_id to all log entries
# within an async request context, enabling log correlation across services.
request_id_context: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for production logging.

    Produces structured log entries with consistent fields for log aggregation.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Use record.created for accurate timing (epoch timestamp when record was created)
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        log_entry: Dict[str, Any] = {
            "timestamp": timestamp.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request_id from context if available
        request_id = request_id_context.get()
        if request_id:
            log_entry["request_id"] = request_id

        # Add extra structured fields from record
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "client_host"):
            log_entry["client_host"] = record.client_host
        if hasattr(record, "user_identifier"):
            log_entry["user_identifier"] = record.user_identifier

        # Add source location for error-level logs
        if record.levelno >= logging.ERROR:
            log_entry["source"] = f"{record.pathname}:{record.lineno}"

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """
    Configure application-wide logging with structured output.

    Configures:
    - Log levels based on environment
    - JSON formatting for production (structured for log aggregators)
    - Human-readable format for development
    - Request ID correlation via context variables
    """
    # Get log level from settings if defined, otherwise default to INFO
    log_level_name = getattr(settings, "LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    is_production = settings.ENV == "production"

    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "()": JSONFormatter,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "json" if is_production else "default",
                "stream": sys.stdout,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
        "loggers": {
            # App loggers
            "app": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            # Quiet down some noisy libraries in development
            "uvicorn.access": {
                "level": logging.WARNING if settings.DEBUG else logging.INFO,
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": logging.WARNING,
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
