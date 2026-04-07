#!/usr/bin/env python3
"""Thin pipeline orchestrator for question generation.

Coordinates the five generation phases by delegating to dedicated phase modules:
- app.generation.runner  — Phase 1: question generation
- app.evaluation.runner  — Phase 2: judge evaluation
- app.salvage.runner     — Salvage: recovering rejected questions
- app.data.dedup_runner  — Phase 3: deduplication
- app.data.insertion_runner — Phase 4: database insertion

Can be invoked by any scheduler (cron, cloud scheduler, manual).

Exit Codes:
    0 - Success (questions generated and inserted)
    1 - Partial failure (some questions generated, but errors occurred)
    2 - Complete failure (no questions generated)
    3 - Configuration error
    4 - Database connection error
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app import (  # noqa: E402
    QuestionJudge,
    QuestionDatabase,
    QuestionDeduplicator,
    QuestionGenerationPipeline,
)
from gioe_libs.alerting.alerting import AlertManager  # noqa: E402
from app.reporting.alerting_adapter import to_run_summary  # noqa: E402
from app.config.config import settings  # noqa: E402
from app.inventory.inventory_config import (  # noqa: E402
    DEFAULT_HEALTHY_THRESHOLD,
    DEFAULT_TARGET_QUESTIONS_PER_STRATUM,
    DEFAULT_WARNING_THRESHOLD,
)
from app.inventory.runner import run_inventory_analysis  # noqa: E402
from app.infrastructure.circuit_breaker import (  # noqa: E402
    get_circuit_breaker_registry,
)
from app.infrastructure.error_classifier import (  # noqa: E402
    ClassifiedError,
    ErrorCategory,
    ErrorSeverity,
)
from gioe_libs.alerting.alerting import RunSummary  # noqa: E402
from gioe_libs.structured_logging import setup_logging  # noqa: E402
from gioe_libs.cron_runner import CronJob  # noqa: E402
from app.reporting.run_summary import RunSummary as PipelineRunSummary  # noqa: E402
from app.data.models import (  # noqa: E402
    DifficultyLevel,
    QuestionType,
)
from app.reporting.reporter import RunReporter  # noqa: E402
from app.data.insertion_runner import run_insertion_phase  # noqa: E402
from app.data.dedup_runner import run_dedup_phase  # noqa: E402
from app.generation.runner import GenerationStats, run_generation_phase  # noqa: E402
from app.evaluation.runner import run_judge_phase  # noqa: E402
from app.salvage.runner import run_salvage_phase  # noqa: E402

# Add repo root to path for libs.observability import
sys.path.insert(0, str(Path(__file__).parent.parent))
from gioe_libs.observability import observability  # noqa: E402

# Exit codes
EXIT_SUCCESS = 0
EXIT_COMPLETE_FAILURE = 2
EXIT_PARTIAL_FAILURE = 3  # Matches reporter.py EXIT_CODE_PARTIAL_FAILURE
EXIT_DATABASE_ERROR = 4
EXIT_BILLING_ERROR = 5  # Critical billing/quota issue
EXIT_AUTH_ERROR = 6  # Authentication failure


class InsertionError(RuntimeError):
    """Raised when database insertion fails after a successful generation run.

    Carries a typed run_summary so callers (e.g. gioe_libs CronJob) can
    report partial metrics without resorting to duck-typing.
    """

    def __init__(self, message: str, run_summary: RunSummary) -> None:
        """Initialize with a message and the run summary captured at failure time."""
        super().__init__(message)
        self.run_summary: RunSummary = run_summary


class _RunIdFilter(logging.Filter):
    """Injects run_id into every log record's extra dict for JSON output."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        existing = getattr(record, "extra", None) or {}
        record.extra = {**existing, "run_id": self._run_id}
        return True


def log_success_run(
    stats: GenerationStats,
    inserted_count: int,
    approval_rate: float,
    run_id: Optional[str] = None,
) -> None:
    """Log successful run to a separate success log for monitoring.

    This creates a JSONL file with one entry per successful run,
    making it easy to track historical success metrics. Also logs to stdout
    for Railway visibility.

    Args:
        stats: Run statistics dictionary
        inserted_count: Number of questions inserted
        approval_rate: Approval rate percentage
    """
    success_file = Path("./logs/success_runs.jsonl")
    success_file.parent.mkdir(parents=True, exist_ok=True)

    success_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "questions_generated": stats.get("questions_generated", 0),
        "questions_inserted": inserted_count,
        "duration_seconds": stats.get("duration_seconds", 0),
        "approval_rate": approval_rate,
        "providers_used": stats.get("providers_used", []),
    }

    # Write to file for filesystem monitoring
    with open(success_file, "a") as f:
        f.write(json.dumps(success_entry) + "\n")

    # IMPORTANT: Also log to stdout for Railway/cloud platform visibility
    print(f"SUCCESS_RUN: {json.dumps(success_entry)}", flush=True)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Run question generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default number of questions (from config)
  python run_generation.py

  # Generate 100 questions
  python run_generation.py --count 100

  # Generate only math and logic questions
  python run_generation.py --types math logic

  # Generate only hard questions
  python run_generation.py --difficulties hard

  # Generate only easy and medium math questions
  python run_generation.py --types math --difficulties easy medium

  # Dry run (generate but don't insert to database)
  python run_generation.py --dry-run

  # Verbose logging
  python run_generation.py --verbose

  # Use async parallel generation for faster execution
  python run_generation.py --async

  # Use async parallel judge evaluation for faster execution
  python run_generation.py --async-judge

  # Use both async generation and async judge evaluation
  python run_generation.py --async --async-judge

  # Auto-balance generation based on inventory gaps
  python run_generation.py --auto-balance

  # Auto-balance with custom target per stratum
  python run_generation.py --auto-balance --target-per-stratum 100

  # Test fallback provider configuration
  python run_generation.py --provider-tier fallback
        """,
    )

    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help=f"Number of questions to generate (default: {settings.questions_per_run})",
    )

    parser.add_argument(
        "--types",
        nargs="+",
        choices=[qt.value for qt in QuestionType],
        default=None,
        help="Question types to generate (default: all types)",
    )

    parser.add_argument(
        "--difficulties",
        nargs="+",
        choices=[dl.value for dl in DifficultyLevel],
        default=None,
        help="Difficulty levels to generate (default: all levels)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and evaluate questions but don't insert to database",
    )

    parser.add_argument(
        "--skip-deduplication",
        action="store_true",
        help="Skip deduplication check (use with caution)",
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help=f"Minimum judge score for approval (default: {settings.min_judge_score})",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help=f"Log file path (default: {settings.log_file})",
    )

    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Disable console logging (only log to file)",
    )

    parser.add_argument(
        "--triggered-by",
        type=str,
        default="manual",
        choices=["scheduler", "manual", "webhook"],
        help="Source that triggered this run (default: manual)",
    )

    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use async parallel generation for improved performance",
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Maximum concurrent requests when using async mode (default: 10)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for async API calls (default: 60)",
    )

    parser.add_argument(
        "--async-judge",
        dest="use_async_judge",
        action="store_true",
        help="Use async parallel judge evaluation for improved performance",
    )

    parser.add_argument(
        "--max-concurrent-judge",
        type=int,
        default=10,
        help="Maximum concurrent judge requests when using async mode (default: 10)",
    )

    parser.add_argument(
        "--judge-timeout",
        type=int,
        default=60,
        help="Timeout in seconds for async judge API calls (default: 60)",
    )

    parser.add_argument(
        "--auto-balance",
        action="store_true",
        help="Automatically balance generation based on inventory gaps. "
        "Prioritizes strata with fewer questions to maintain even coverage.",
    )

    parser.add_argument(
        "--target-per-stratum",
        type=int,
        default=DEFAULT_TARGET_QUESTIONS_PER_STRATUM,
        help="Target number of questions per stratum when using --auto-balance "
        f"(default: {DEFAULT_TARGET_QUESTIONS_PER_STRATUM})",
    )

    parser.add_argument(
        "--healthy-threshold",
        type=int,
        default=DEFAULT_HEALTHY_THRESHOLD,
        help=f"Minimum count for healthy inventory status "
        f"(default: {DEFAULT_HEALTHY_THRESHOLD})",
    )

    parser.add_argument(
        "--warning-threshold",
        type=int,
        default=DEFAULT_WARNING_THRESHOLD,
        help=f"Minimum count for warning inventory status "
        f"(default: {DEFAULT_WARNING_THRESHOLD})",
    )

    parser.add_argument(
        "--alerting-config",
        type=str,
        default="./config/alerting.yaml",
        help="Path to alerting configuration file (default: ./config/alerting.yaml)",
    )

    parser.add_argument(
        "--skip-inventory-alerts",
        action="store_true",
        help="Skip inventory alerting even when using --auto-balance",
    )

    parser.add_argument(
        "--provider-tier",
        type=str,
        choices=["primary", "fallback", "balanced"],
        default="primary",
        help="Provider tier to use for question generation. "
        "'primary' uses the primary provider from generators.yaml (default). "
        "'fallback' forces use of fallback provider to test fallback configuration. "
        "'balanced' alternates between primary and fallback providers per question "
        "to distribute load and reduce rate-limit pressure.",
    )

    return parser.parse_args()


def create_run_reporter(
    logger: Optional[logging.Logger] = None,
) -> Optional[RunReporter]:
    """Create a RunReporter instance if reporting is enabled and configured.

    Args:
        logger: Logger instance for output

    Returns:
        RunReporter instance if enabled and configured, None otherwise
    """
    if not settings.enable_run_reporting:
        if logger:
            logger.info("Run reporting is disabled")
        return None

    if not settings.backend_api_url:
        if logger:
            logger.warning(
                "Run reporting enabled but BACKEND_API_URL not configured - skipping"
            )
        return None

    if not settings.backend_service_key:
        if logger:
            logger.warning(
                "Run reporting enabled but BACKEND_SERVICE_KEY not configured - skipping"
            )
        return None

    reporter = RunReporter(
        backend_url=settings.backend_api_url,
        service_key=settings.backend_service_key,
    )
    if logger:
        logger.info(f"Run reporter initialized (backend: {settings.backend_api_url})")
    return reporter


def send_phase_alert(
    alert_manager: AlertManager,
    category: ErrorCategory,
    severity: ErrorSeverity,
    provider: str,
    original_error: str,
    message: str,
    context: str,
    is_retryable: bool = True,
) -> None:
    """Construct a ClassifiedError and send it via alert_manager."""
    error = ClassifiedError(
        category=category,
        severity=severity,
        provider=provider,
        original_error=original_error,
        message=message,
        is_retryable=is_retryable,
    )
    alert_manager.send_alert(error, context=context)


def _build_run_stats(
    stats: GenerationStats,
    inserted_count: int,
    approval_rate: float,
    summary: dict,
) -> dict:
    """Build the run statistics dictionary for reporting."""
    requested = stats.get("target_questions", 0)
    generated = stats.get("questions_generated", 0)
    loss = requested - generated
    return {
        "questions_generated": generated,
        "questions_inserted": inserted_count,
        "approval_rate": approval_rate,
        "duration_seconds": stats.get("duration_seconds", 0),
        "by_type": summary.get("database", {}).get("inserted_by_type", {}),
        "by_difficulty": summary.get("generation", {}).get("by_difficulty", {}),
        "questions_requested": requested,
        "generation_loss": loss,
        "generation_loss_pct": (
            round(loss / requested * 100, 1) if requested > 0 else 0.0
        ),
        "questions_rejected": summary.get("evaluation", {}).get("rejected", 0),
        "duplicates_found": summary.get("deduplication", {}).get("duplicates_found", 0),
    }


def _init_components(
    args: argparse.Namespace,
    alert_manager: AlertManager,
    run_id: str,
    logger: logging.Logger,
) -> tuple[
    QuestionGenerationPipeline,
    QuestionJudge,
    Optional[QuestionDatabase],
    Optional[QuestionDeduplicator],
]:
    """Initialize all pipeline components.

    Returns (pipeline, judge, db, deduplicator). Raises RuntimeError on
    configuration or database errors and sends appropriate alerts.
    """
    if not any(
        [
            settings.openai_api_key,
            settings.anthropic_api_key,
            settings.google_api_key,
            settings.xai_api_key,
        ]
    ):
        logger.error("No LLM API keys configured!")
        logger.error(
            "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, or XAI_API_KEY"
        )
        send_phase_alert(
            alert_manager=alert_manager,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.CRITICAL,
            provider="system",
            original_error="ConfigurationError",
            message="No LLM API keys configured. Question generation cannot run.",
            context=(
                f"[run_id={run_id}] Question generation script failed to start due to missing API keys. "
                "Check environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY"
            ),
            is_retryable=False,
        )
        raise RuntimeError("No LLM API keys configured")

    pipeline = QuestionGenerationPipeline(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        xai_api_key=settings.xai_api_key,
    )
    logger.info("✓ Pipeline initialized")

    from app.config.judge_config import JudgeConfigLoader  # noqa: PLC0415

    judge_loader = JudgeConfigLoader(settings.judge_config_path)
    judge_loader.load()
    logger.info(f"✓ Judge config loaded from {settings.judge_config_path}")

    from app.config.generator_config import initialize_generator_config  # noqa: PLC0415

    try:
        initialize_generator_config(settings.generator_config_path)
        logger.info(f"✓ Generator config loaded from {settings.generator_config_path}")
    except FileNotFoundError:
        logger.warning(
            f"Generator config not found at {settings.generator_config_path}. "
            "Using round-robin distribution instead of specialist routing."
        )

    judge = QuestionJudge(
        judge_config=judge_loader,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        xai_api_key=settings.xai_api_key,
        max_concurrent_evaluations=args.max_concurrent_judge,
        async_timeout_seconds=args.judge_timeout,
    )
    logger.info("✓ Judge initialized")

    db = None
    deduplicator = None

    if not args.dry_run:
        try:
            db = QuestionDatabase(
                database_url=settings.database_url,
                openai_api_key=settings.openai_api_key,
                google_api_key=settings.google_api_key,
            )
            logger.info("✓ Database connected")

            if not settings.openai_api_key:
                logger.error("OpenAI API key required for deduplication")
                raise RuntimeError("OpenAI API key required for deduplication")

            deduplicator = QuestionDeduplicator(
                openai_api_key=settings.openai_api_key,
                similarity_threshold=settings.dedup_similarity_threshold,
                embedding_model=settings.dedup_embedding_model,
                redis_url=settings.redis_url,
                embedding_cache_ttl=settings.embedding_cache_ttl,
                google_api_key=settings.google_api_key,
            )
            cache_type = "Redis" if deduplicator.using_redis_cache else "in-memory"
            logger.info(f"✓ Deduplicator initialized (cache: {cache_type})")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            observability.capture_error(
                e, context={"phase": "init", "step": "database_connection"}
            )
            send_phase_alert(
                alert_manager=alert_manager,
                category=ErrorCategory.SERVER_ERROR,
                severity=ErrorSeverity.CRITICAL,
                provider="database",
                original_error=type(e).__name__,
                message=f"Database connection failed: {str(e)}",
                context=(
                    f"[run_id={run_id}] Question generation cannot connect to database. "
                    f"Check DATABASE_URL and database availability. Error: {str(e)}"
                ),
                is_retryable=False,
            )
            raise RuntimeError(f"Database connection failed: {str(e)}") from e

    return pipeline, judge, db, deduplicator


def main() -> int:
    """Main entry point for question generation script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_arguments()

    # Initialize observability before any code that could raise exceptions
    observability.init(
        config_path="config/observability.yaml",
        service_name="aiq-question-service",
        environment=settings.env,
    )

    # Build alert manager (needed by CronJob and circuit breaker callback)
    alert_manager = AlertManager(
        alert_file_path=settings.alert_file_path,
        discord_webhook_url=settings.discord_webhook_url,
    )

    # Register circuit breaker callback so Discord alerts fire on CLOSED → OPEN transitions.
    get_circuit_breaker_registry().set_on_open_callback(
        alert_manager.send_circuit_breaker_alert
    )

    # NOTE: _work() captures alert_manager from main() scope. This is intentional
    # for run_once(): one AlertManager is created, registered with the circuit breaker
    # registry, and used throughout the single run. If run_loop() were ever adopted,
    # reconstruct alert_manager (and re-register the callback) inside _work() instead.
    def _work() -> dict:
        """Run the generation pipeline once; called by CronJob.run_once()."""
        log_level = "DEBUG" if args.verbose else settings.log_level
        log_file = args.log_file or settings.log_file
        setup_logging(
            log_level=log_level,
            log_file=log_file,
            enable_file_logging=not args.no_console,
        )

        run_id = (
            f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            f"-{uuid.uuid4().hex[:6]}"
        )
        _run_id_filter = _RunIdFilter(run_id)
        logging.getLogger().addFilter(_run_id_filter)
        logger = logging.getLogger(__name__)

        logger.info("=" * 80)
        logger.info(f"Question Generation Script Starting  run_id={run_id}")
        logger.info(
            f"Observability initialized: service=aiq-question-service, env={settings.env}"
        )
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        logger.info(
            f"Configuration: count={args.count or settings.questions_per_run}, "
            f"types={args.types or 'all'}, difficulties={args.difficulties or 'all'}"
        )
        logger.info(f"Provider tier: {args.provider_tier}")
        logger.info(f"Dry run: {args.dry_run}")
        logger.info("=" * 80)

        inserted_count = 0
        approval_rate = 0.0
        stats: Optional[GenerationStats] = None
        db = None
        run_reporter = None
        summary: dict = {}

        try:
            metrics = PipelineRunSummary()
            metrics.start_run()

            logger.info(
                f"Alert manager initialized (discord={'enabled' if settings.discord_webhook_url else 'disabled'})"
            )

            run_reporter = create_run_reporter(logger)

            question_types = None
            if args.types:
                question_types = [QuestionType(qt) for qt in args.types]
                logger.info(
                    f"Generating only types: {[qt.value for qt in question_types]}"
                )

            difficulty_distribution = None
            if args.difficulties:
                difficulties = [DifficultyLevel(d) for d in args.difficulties]
                weight = 1.0 / len(difficulties)
                difficulty_distribution = {d: weight for d in difficulties}
                logger.info(
                    f"Generating only difficulties: {[d.value for d in difficulties]}"
                )

            logger.info("Initializing pipeline components...")
            pipeline, judge, db, deduplicator = _init_components(
                args, alert_manager, run_id, logger
            )

            # Phase 0: Inventory Analysis
            generation_plan = None
            if args.auto_balance:
                logger.info("\n" + "=" * 80)
                logger.info("PHASE 0: Inventory Analysis (Auto-Balance)")
                logger.info("=" * 80)
                generation_plan = run_inventory_analysis(
                    db=db,
                    healthy_threshold=args.healthy_threshold,
                    warning_threshold=args.warning_threshold,
                    target_per_stratum=args.target_per_stratum,
                    target_count=args.count or settings.questions_per_run,
                    alerting_config_path=args.alerting_config,
                    skip_inventory_alerts=args.skip_inventory_alerts,
                    alert_manager=alert_manager,
                    logger=logger,
                )
                if generation_plan is None:
                    return to_run_summary(
                        {"questions_generated": 0, "reason": "inventory_balanced"}
                    )

            # Phase 1: Question Generation
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 1: Question Generation")
            logger.info("=" * 80)
            generated_questions, stats = run_generation_phase(
                pipeline=pipeline,
                generation_plan=generation_plan,
                question_types=question_types,
                difficulty_distribution=difficulty_distribution,
                use_async=args.use_async,
                max_concurrent=args.max_concurrent,
                timeout=args.timeout,
                provider_tier=args.provider_tier,
                count=args.count,
                metrics=metrics,
                logger=logger,
            )

            if not generated_questions:
                logger.error("No questions generated!")
                send_phase_alert(
                    alert_manager=alert_manager,
                    category=ErrorCategory.UNKNOWN,
                    severity=ErrorSeverity.CRITICAL,
                    provider="pipeline",
                    original_error="GenerationFailure",
                    message="Question generation produced zero questions. All generation attempts failed.",
                    context=(
                        f"[run_id={run_id}] Question generation job completed but produced no questions. "
                        f"Target: {stats['target_questions']}, Generated: 0. "
                        "Check logs for LLM API errors."
                    ),
                    is_retryable=True,
                )
                raise RuntimeError("No questions generated")

            # Phase 2: Judge Evaluation
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 2: Judge Evaluation")
            logger.info("=" * 80)
            min_score = args.min_score or settings.min_judge_score
            logger.info(f"Minimum approval score: {min_score}")

            approved_questions, rejected_questions, approval_rate = run_judge_phase(
                generated_questions=generated_questions,
                judge=judge,
                min_score=min_score,
                use_async_judge=args.use_async_judge,
                metrics=metrics,
                logger=logger,
            )

            # Salvage Phase
            if rejected_questions:
                logger.info("\n" + "-" * 40)
                logger.info("SALVAGE PHASE: Attempting to recover rejected questions")
                logger.info("-" * 40)
                approved_questions, approval_rate = run_salvage_phase(
                    rejected_questions=rejected_questions,
                    approved_questions=approved_questions,
                    generated_questions=generated_questions,
                    pipeline=pipeline,
                    judge=judge,
                    min_score=min_score,
                    logger=logger,
                )

            if not approved_questions:
                logger.warning("No questions passed judge evaluation!")
                send_phase_alert(
                    alert_manager=alert_manager,
                    category=ErrorCategory.INVALID_REQUEST,
                    severity=ErrorSeverity.HIGH,
                    provider="judge",
                    original_error="JudgeRejectionFailure",
                    message=f"All {len(generated_questions)} generated questions were rejected by judge evaluation.",
                    context=(
                        f"[run_id={run_id}] Question generation produced {len(generated_questions)} questions "
                        f"but judge rejected all of them. Minimum score threshold: {min_score}. "
                        "Consider reviewing judge configuration or lowering MIN_JUDGE_SCORE."
                    ),
                    is_retryable=True,
                )
                raise RuntimeError("No questions passed judge evaluation")

            # Phase 3: Deduplication
            unique_questions = approved_questions
            if not args.skip_deduplication and not args.dry_run:
                logger.info("\n" + "=" * 80)
                logger.info("PHASE 3: Deduplication")
                logger.info("=" * 80)
                unique_questions = run_dedup_phase(
                    approved_questions=approved_questions,
                    db=db,
                    deduplicator=deduplicator,
                    metrics=metrics,
                    logger=logger,
                )

            # Phase 4: Database Insertion
            inserted_count = 0
            if not args.dry_run and unique_questions:
                logger.info("\n" + "=" * 80)
                logger.info("PHASE 4: Database Insertion")
                logger.info("=" * 80)
                inserted_count = run_insertion_phase(
                    unique_questions=unique_questions,
                    db=db,
                    metrics=metrics,
                    logger=logger,
                )

            # Final Summary
            metrics.end_run()
            summary = metrics.to_summary_dict()

            logger.info("\n" + "=" * 80)
            logger.info("FINAL SUMMARY")
            logger.info("=" * 80)
            logger.info(
                f"Total duration: {summary['execution']['duration_seconds']:.1f}s"
            )
            logger.info(f"Generated: {stats['questions_generated']}")
            logger.info(f"Approved by judge: {len(approved_questions)}")
            logger.info(f"Unique: {len(unique_questions)}")
            logger.info(f"Inserted to database: {inserted_count}")
            logger.info(f"Approval rate: {approval_rate:.1f}%")

            if args.dry_run:
                logger.info("\n[DRY RUN] No questions were inserted to database")

            _run_stats = _build_run_stats(stats, inserted_count, approval_rate, summary)

            if not args.dry_run:
                if inserted_count == 0:
                    logger.error("No questions were inserted to database!")
                    send_phase_alert(
                        alert_manager=alert_manager,
                        category=ErrorCategory.SERVER_ERROR,
                        severity=ErrorSeverity.CRITICAL,
                        provider="database",
                        original_error="InsertionFailure",
                        message=f"Database insertion failed for all {len(unique_questions)} unique questions.",
                        context=(
                            f"[run_id={run_id}] Question generation completed successfully through judge evaluation, "
                            f"but all {len(unique_questions)} questions failed to insert to database. "
                            "Check database connection and logs."
                        ),
                        is_retryable=True,
                    )
                    raise InsertionError(
                        f"Database insertion failed: 0 of {len(unique_questions)} questions inserted",
                        run_summary=to_run_summary(_run_stats),
                    )
                elif inserted_count < len(unique_questions):
                    logger.warning("Some questions failed to insert")
                    raise InsertionError(
                        f"Partial insertion failure: {inserted_count} of {len(unique_questions)} questions inserted",
                        run_summary=to_run_summary(_run_stats),
                    )
                else:
                    logger.info("✓ All unique questions inserted successfully")

            if inserted_count > 0:
                log_success_run(
                    stats=stats,
                    inserted_count=inserted_count,
                    approval_rate=approval_rate,
                    run_id=run_id,
                )
                logger.info("Success metrics logged to logs/success_runs.jsonl")

            if run_reporter:
                min_score = args.min_score or settings.min_judge_score
                backend_run_id = run_reporter.report_run(
                    summary=summary,
                    exit_code=EXIT_SUCCESS,
                    environment=settings.env,
                    triggered_by=args.triggered_by,
                    prompt_version=settings.prompt_version,
                    judge_config_version=settings.judge_config_version,
                    min_judge_score_threshold=min_score,
                    client_run_id=run_id,
                )
                if backend_run_id:
                    logger.info(f"Run reported to backend API (ID: {backend_run_id})")
                else:
                    logger.warning("Failed to report run to backend API")

            # Post-run answer-leakage audit (always runs; respects args.dry_run for writes)
            if db is not None:
                try:
                    from app.data.answer_leakage_auditor import (
                        run_answer_leakage_audit,
                    )  # noqa: PLC0415

                    run_answer_leakage_audit(db.SessionLocal, dry_run=args.dry_run)
                except Exception as audit_err:
                    logger.warning(
                        "[answer-leakage-audit] Audit skipped due to error: %s",
                        audit_err,
                        exc_info=True,
                    )

            logger.info("=" * 80)
            logger.info("Script completed successfully")
            logger.info("=" * 80)

            run_summary = to_run_summary(
                _run_stats,
                loss_threshold=(
                    None if args.dry_run else settings.generation_loss_threshold_pct
                ),
            )

            logger.info(
                "RUN_COMPLETE run_id=%s exit_code=0 questions_requested=%d questions_generated=%d "
                "generation_loss=%d generation_loss_pct=%.1f questions_inserted=%d "
                "approval_rate=%.1f duration_seconds=%.1f",
                run_id,
                _run_stats["questions_requested"],
                _run_stats["questions_generated"],
                _run_stats["generation_loss"],
                _run_stats["generation_loss_pct"],
                inserted_count,
                approval_rate,
                stats.get("duration_seconds", 0.0),
            )

            if (
                not args.dry_run
                and _run_stats["generation_loss_pct"]
                > settings.generation_loss_threshold_pct
            ):
                logger.warning(
                    "GENERATION_LOSS_ALERT generation_loss_pct=%.1f exceeds threshold=%.1f "
                    "requested=%d generated=%d",
                    _run_stats["generation_loss_pct"],
                    settings.generation_loss_threshold_pct,
                    _run_stats["questions_requested"],
                    _run_stats["questions_generated"],
                )

            return run_summary

        except Exception as exc:
            # Report failed and partial_failure runs to the backend API so every
            # run — successful or not — appears in /v1/admin/generation-runs.
            if run_reporter:
                if isinstance(exc, InsertionError) and inserted_count > 0:
                    failure_exit_code = EXIT_PARTIAL_FAILURE
                else:
                    failure_exit_code = EXIT_COMPLETE_FAILURE
                min_score = args.min_score or settings.min_judge_score
                backend_run_id = run_reporter.report_run(
                    summary=summary,
                    exit_code=failure_exit_code,
                    environment=settings.env,
                    triggered_by=args.triggered_by,
                    prompt_version=settings.prompt_version,
                    judge_config_version=settings.judge_config_version,
                    min_judge_score_threshold=min_score,
                    client_run_id=run_id,
                )
                if backend_run_id:
                    logger.info(
                        f"Failed run reported to backend API (ID: {backend_run_id})"
                    )
                else:
                    logger.warning("Failed to report failed run to backend API")
            raise

        finally:
            # Remove run_id filter so it does not persist across runs
            logging.getLogger().removeFilter(_run_id_filter)
            # Always close the database connection, even if an exception is raised
            if db is not None:
                try:
                    db.close()
                    logger.info("Database connection closed")
                except Exception:
                    pass

    job = CronJob(
        name="question-generation",
        schedule="0 * * * *",
        work_fn=_work,
        observability=observability,
        alert_manager=alert_manager,
        heartbeat_path="./logs/heartbeat.json",
    )

    try:
        return job.run_once()
    finally:
        # Shutdown observability backends
        # Skip flush — metrics export on the periodic cycle to avoid
        # Grafana Cloud free tier rate limits (err-mimir-tenant-max-request-rate)
        try:
            observability.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
