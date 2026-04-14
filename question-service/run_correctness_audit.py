#!/usr/bin/env python3
"""Standalone CLI for answer correctness auditing.

Runs the adversarial blind-solve verification audit independently of question
generation.  Can be scheduled on its own cadence (e.g. weekly full sweep)
without triggering the generation pipeline.

Exit Codes:
    0 - Success
    1 - Configuration / runtime error
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app import QuestionDatabase, QuestionJudge  # noqa: E402
from app.config.config import settings  # noqa: E402
from gioe_libs.structured_logging import setup_logging  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent))
from gioe_libs.observability import observability  # noqa: E402

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run answer correctness audit on the active question pool.",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="Cap the number of questions audited per run.",
    )
    parser.add_argument(
        "--audit-window-hours",
        type=float,
        default=None,
        help="Skip questions audited within this many hours (incremental mode). "
        "Questions never audited are always included.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable DEBUG-level logging."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    observability.init(
        config_path="config/observability.yaml",
        service_name="aiq-question-service",
        environment=settings.env,
    )

    setup_logging(log_level="DEBUG" if args.verbose else settings.log_level)

    if not any(
        [
            settings.openai_api_key,
            settings.anthropic_api_key,
            settings.google_api_key,
            settings.xai_api_key,
        ]
    ):
        logger.error(
            "No LLM API keys configured. "
            "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, or XAI_API_KEY."
        )
        return 1

    # Judge config
    from app.config.judge_config import JudgeConfigLoader  # noqa: PLC0415

    judge_loader = JudgeConfigLoader(settings.judge_config_path)
    judge_loader.load()
    logger.info("Judge config loaded from %s", settings.judge_config_path)

    # Judge
    judge = QuestionJudge(
        judge_config=judge_loader,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        xai_api_key=settings.xai_api_key,
    )
    logger.info("Judge initialized")

    # Database
    try:
        db = QuestionDatabase(
            database_url=settings.database_url,
            openai_api_key=settings.openai_api_key,
            google_api_key=settings.google_api_key,
        )
        logger.info("Database connected")
    except Exception as e:
        logger.error("Database connection failed: %s", e)
        return 1

    # Run audit
    try:
        from app.data.answer_correctness_auditor import (  # noqa: PLC0415
            run_answer_correctness_audit,
        )

        results = run_answer_correctness_audit(
            db.SessionLocal,
            judge,
            judge.judge_config,
            max_questions=args.max_questions,
            audit_window_hours=args.audit_window_hours,
        )

        logger.info(
            "Audit complete: scanned=%d verified=%d failed=%d deactivated=%d",
            results.get("scanned", 0),
            results.get("verified_correct", 0),
            results.get("failed", 0),
            results.get("deactivated", 0),
        )
        return 0
    except Exception as e:
        logger.error("Correctness audit failed: %s", e, exc_info=True)
        return 1
    finally:
        try:
            db.close()
        except Exception:
            pass
        try:
            observability.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
