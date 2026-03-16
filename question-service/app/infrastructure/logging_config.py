"""Backward-compatibility shim — imports from libs.logging.

The canonical implementation now lives in libs/logging/logging_config.py.
"""

from libs.logging.logging_config import (  # noqa: F401
    ColoredFormatter,
    JSONFormatter,
    LogContext,
    get_logger,
    setup_logging,
)
