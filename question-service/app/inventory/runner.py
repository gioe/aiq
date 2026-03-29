"""Inventory phase runner for the question generation pipeline."""

import logging
from typing import Optional

from app import QuestionDatabase, InventoryAnalyzer
from app.inventory.inventory_analyzer import GenerationPlan
from gioe_libs.alerting.alerting import (
    AlertManager,
    AlertingConfig,
    ResourceMonitor,
    ResourceStatus,
)


def run_inventory_analysis(
    db: Optional[QuestionDatabase],
    healthy_threshold: int,
    warning_threshold: int,
    target_per_stratum: int,
    target_count: int,
    alerting_config_path: str,
    skip_inventory_alerts: bool,
    alert_manager: AlertManager,
    logger: logging.Logger,
) -> Optional[GenerationPlan]:
    """Phase 0: Analyze inventory and compute a balanced generation plan.

    Returns the generation plan, or None if all strata are at target (early exit).
    Raises RuntimeError if auto-balance is requested without a database connection.
    """
    if not db:
        logger.error("Auto-balance requires database connection (cannot use --dry-run)")
        raise RuntimeError("Auto-balance requires database connection")

    analyzer = InventoryAnalyzer(
        database_service=db,
        healthy_threshold=healthy_threshold,
        warning_threshold=warning_threshold,
        target_per_stratum=target_per_stratum,
    )

    analysis = analyzer.analyze_inventory()
    analyzer.log_inventory_summary(analysis)

    generation_plan = analyzer.compute_generation_plan(
        target_total=target_count,
        analysis=analysis,
    )
    logger.info("\n" + generation_plan.to_log_summary())

    if not skip_inventory_alerts:
        logger.info("\nChecking inventory levels for alerting...")
        alerting_config = AlertingConfig.from_yaml(alerting_config_path)
        strata_snapshot = analysis.strata

        def inventory_check_fn() -> list:
            return [
                ResourceStatus(
                    name=f"{s.question_type.value}/{s.difficulty.value}",
                    count=s.current_count,
                )
                for s in strata_snapshot
            ]

        resource_monitor = ResourceMonitor(
            check_fn=inventory_check_fn,
            alert_manager=alert_manager,
            config=alerting_config,
        )
        alert_result = resource_monitor.check_and_alert()

        if alert_result.alerts_sent > 0:
            logger.warning(
                f"Inventory alerts sent: {alert_result.alerts_sent} strata below threshold"
            )
        if alert_result.critical_resources:
            logger.warning(
                f"CRITICAL: {len(alert_result.critical_resources)} strata have "
                f"critically low inventory (< {alerting_config.critical_min})"
            )
        if alert_result.warning_resources:
            logger.info(
                f"WARNING: {len(alert_result.warning_resources)} strata have "
                f"low inventory (< {alerting_config.warning_min})"
            )
    else:
        logger.info("Inventory alerting skipped (--skip-inventory-alerts)")

    if generation_plan.total_questions == 0:
        logger.info("Auto-balance early exit: all strata at or above target")
        logger.info(
            f"  Thresholds: healthy={healthy_threshold}, "
            f"warning={warning_threshold}, "
            f"target_per_stratum={target_per_stratum}"
        )
        logger.info(
            f"  Analyzed {len(analysis.strata)} strata, "
            f"{analysis.total_questions} total active questions"
        )
        logger.info(
            f"  Below target: {len(analysis.strata_below_target)}, "
            f"Critical: {len(analysis.critical_strata)}"
        )
        return None

    return generation_plan
