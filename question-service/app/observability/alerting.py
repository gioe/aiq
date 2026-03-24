"""Alert notification system — shim re-exporting from gioe_libs.alerting.

All implementation lives in libs/alerting/alerting.py so that any service
can import AlertManager without depending on question-service packages.
"""

from gioe_libs.alerting.alerting import (  # noqa: F401
    AlertError,
    AlertManager,
    AlertableError,
    AlertingConfig,
    ErrorCategory,
    ErrorSeverity,
    ResourceMonitor,
    ResourceMonitorResult,
    ResourceStatus,
    RunSummary,
)
from app.infrastructure.llm_error_categories import LLMErrorCategory  # noqa: F401
