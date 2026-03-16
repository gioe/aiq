"""Backward-compatibility shim — imports from libs.aiq_logging.

The canonical implementation now lives in libs/aiq_logging/logging_config.py.
"""

from libs.aiq_logging.logging_config import (  # noqa: F401
    ColoredFormatter,
    JSONFormatter,
    LogContext,
    get_logger,
    setup_logging,
)
