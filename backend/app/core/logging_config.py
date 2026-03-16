"""Backend logging configuration — thin shim over libs/logging.

JSONFormatter, get_logger, and request_id_context come from libs/logging so
both services share identical structured-log output.  setup_logging() here is
backend-specific: it reads from app.core.config.settings and applies the
backend's named-logger configuration via dictConfig.
"""

import logging
import logging.config
import sys
from typing import Any, Dict

from app.core.config import settings
from libs.logging import JSONFormatter, get_logger, request_id_context  # noqa: F401


def setup_logging() -> None:
    """Configure application-wide logging for the backend."""
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

    # Clamp third-party loggers to WARNING; relax only when the root level is
    # DEBUG so low-level networking traces are surfaced without INFO noise.
    third_party_level = log_level if log_level <= logging.DEBUG else logging.WARNING
    for noisy_logger in (
        "httpcore",
        "httpx",
        "anthropic",
        "openai",
        "opentelemetry",
        "urllib3",
    ):
        logging.getLogger(noisy_logger).setLevel(third_party_level)
