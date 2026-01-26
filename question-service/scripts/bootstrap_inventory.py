#!/usr/bin/env python3
"""Bootstrap inventory script for generating initial question inventory.

This script orchestrates question generation across all question types,
integrating with the existing question-service architecture.

Features:
- Provider-agnostic design using BaseLLMProvider abstraction
- Retry logic with exponential backoff
- Per-type error isolation (one type failing doesn't stop others)
- JSONL event logging for monitoring integration
- Graceful degradation on provider failures
- Parallel type generation with asyncio and semaphore-based rate limiting

Usage:
    python scripts/bootstrap_inventory.py [OPTIONS]

Options:
    --count N           Total questions per type (distributed across difficulties)
                        Default: 150 (50 per difficulty level)
    --types TYPE,...    Comma-separated list of types to generate (default: all)
    --dry-run           Generate without database insertion
    --no-async          Disable async generation
    --no-batch          Disable batch API generation
    --max-retries N     Maximum retries per type (default: 3)
    --parallel          Enable parallel generation across types
    --max-parallel N    Maximum concurrent types (default: 2)
    --quiet             Suppress terminal progress output
    --help              Show this help message

Exit codes:
    0 - All types completed successfully
    1 - Some types failed after retries
    2 - Configuration or setup error
"""

import argparse
import asyncio
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, TypedDict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.alerting import AlertManager  # noqa: E402
from app.config import settings  # noqa: E402
from app.error_classifier import (  # noqa: E402
    ClassifiedError,
    ErrorCategory,
    ErrorSeverity,
)
from app.models import DifficultyLevel, QuestionType  # noqa: E402
from app.pipeline import QuestionGenerationPipeline  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.prompts import build_generation_prompt  # noqa: E402
from app.providers.google_provider import GoogleProvider  # noqa: E402

# Exit codes
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_CONFIG_ERROR = 2

# Constants
MAX_ERROR_MESSAGE_LENGTH = 500
# Threshold for critical failure alert - matches bash script
CRITICAL_FAILURE_THRESHOLD = 3
MAX_EVENT_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit before rotation
GENERATION_TIMEOUT_SECONDS = 300  # 5 minutes per type generation
# Maximum questions per type to prevent runaway resource usage
# ~3 API calls per question * 10000 = 30000 API calls max
MAX_QUESTIONS_PER_TYPE = 10000

# Batch API constants
BATCH_PARSE_ERROR_THRESHOLD = 0.25  # Fail if >25% of responses fail to parse
BATCH_TIMEOUT_BUFFER_RATIO = 0.10  # Add 10% buffer to batch timeout
BATCH_TIMEOUT_BUFFER_MIN_SECONDS = 60  # Minimum timeout buffer in seconds

# Sensitive data patterns for sanitization
# These patterns match common API key and credential formats that could leak in error messages
SENSITIVE_PATTERNS = [
    # OpenAI API keys (sk-...)
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "[REDACTED_OPENAI_KEY]"),
    # Anthropic API keys (sk-ant-...)
    (re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    # Google API keys (AIza...)
    (re.compile(r"AIza[a-zA-Z0-9\-_]{30,}"), "[REDACTED_GOOGLE_KEY]"),
    # xAI API keys (xai-...)
    (re.compile(r"xai-[a-zA-Z0-9]{20,}"), "[REDACTED_XAI_KEY]"),
    # Bearer tokens in headers
    (
        re.compile(r"Bearer\s+[a-zA-Z0-9\-_.]+", re.IGNORECASE),
        "Bearer [REDACTED_TOKEN]",
    ),
    # Basic auth in URLs (user:pass@host)
    (re.compile(r"://[^:]+:[^@]+@"), "://[REDACTED_CREDENTIALS]@"),
    # Generic API key patterns in query strings (?key=... or &key=...)
    (
        re.compile(r"[?&](api[_-]?key|apikey|key|token|secret)=[^&\s]+", re.IGNORECASE),
        r"?\1=[REDACTED]",
    ),
    # Authorization headers
    (
        re.compile(r"(Authorization|X-Api-Key|X-API-Key):\s*\S+", re.IGNORECASE),
        r"\1: [REDACTED]",
    ),
]


def _sanitize_error(error: Any) -> str:
    """Sanitize error message by redacting sensitive information.

    This function removes potentially sensitive data from error messages
    before they are logged or displayed. It handles API keys, tokens,
    credentials, and other sensitive patterns that might appear in
    API error responses.

    Args:
        error: Error object or string to sanitize

    Returns:
        Sanitized error string with sensitive data redacted
    """
    error_str = str(error)

    # Apply all sanitization patterns
    for pattern, replacement in SENSITIVE_PATTERNS:
        error_str = pattern.sub(replacement, error_str)

    return error_str


class GenerationResult(TypedDict):
    """Result of generating questions for a single type."""

    questions: List[Any]
    generated: int
    target: int


def _truncate_error(error: Any) -> str:
    """Safely sanitize and truncate error message with ellipsis indicator.

    This function first sanitizes the error to remove sensitive information
    (API keys, tokens, credentials), then truncates if needed.

    Args:
        error: Error object or string to truncate

    Returns:
        Sanitized and truncated error string with indicator if truncated
    """
    # First sanitize to remove sensitive data
    error_str = _sanitize_error(error)

    # Then truncate if needed
    if len(error_str) <= MAX_ERROR_MESSAGE_LENGTH:
        return error_str
    return error_str[: MAX_ERROR_MESSAGE_LENGTH - 3] + "..."


@dataclass
class TypeResult:
    """Result of generating questions for a single type."""

    question_type: str
    success: bool
    attempt_count: int
    generated: int = 0
    inserted: int = 0
    approval_rate: float = 0.0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


@dataclass
class BootstrapConfig:
    """Configuration for the bootstrap process."""

    questions_per_type: int = 150
    types: List[str] = field(default_factory=lambda: [qt.value for qt in QuestionType])
    dry_run: bool = False
    use_async: bool = True
    use_batch: bool = True
    max_retries: int = 3
    retry_base_delay: float = 5.0
    retry_max_delay: float = 60.0
    quiet: bool = False
    parallel: bool = False
    max_parallel: int = 2


class ProgressReporter:
    """Real-time progress reporter for terminal output.

    Provides formatted progress updates during question generation.
    Can be silenced with quiet mode.
    """

    # ANSI color codes for terminal output
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(self, quiet: bool = False):
        """Initialize the progress reporter.

        Args:
            quiet: If True, suppress all terminal output
        """
        self.quiet = quiet

    def _print(self, message: str) -> None:
        """Print message if not in quiet mode.

        Args:
            message: Message to print
        """
        if not self.quiet:
            print(message)

    def _truncate(self, message: str, max_length: int = 200) -> str:
        """Sanitize and truncate message with ellipsis indicator if too long.

        This method sanitizes the message to remove sensitive information
        (API keys, tokens, credentials) before truncating.

        Args:
            message: Message to truncate
            max_length: Maximum length before truncation (default: 200)

        Returns:
            Sanitized and truncated message with ellipsis if truncated
        """
        # Sanitize first to remove sensitive data
        sanitized = _sanitize_error(message)

        if len(sanitized) <= max_length:
            return sanitized
        return sanitized[:max_length] + "..."

    def banner(
        self,
        questions_per_type: int,
        types: List[str],
        max_retries: int,
        use_async: bool,
        use_batch: bool,
        dry_run: bool,
        parallel: bool = False,
        max_parallel: int = 2,
    ) -> None:
        """Print the startup banner with configuration.

        Args:
            questions_per_type: Number of questions per type
            types: List of question types to generate
            max_retries: Maximum retry attempts per type
            use_async: Whether async mode is enabled
            use_batch: Whether batch mode is enabled
            dry_run: Whether running in dry-run mode
            parallel: Whether parallel mode is enabled
            max_parallel: Maximum concurrent type generations
        """
        self._print("")
        self._print("=" * 64)
        self._print("       AIQ Question Inventory Bootstrap Script (Python)")
        self._print("=" * 64)
        self._print("")
        self._print("Configuration:")
        self._print(f"  Questions per type: {questions_per_type}")
        self._print(f"  Questions per difficulty: ~{questions_per_type // 3}")
        self._print(f"  Types: {', '.join(types)}")
        self._print("  Difficulties: easy, medium, hard (auto-distributed)")
        self._print(f"  Total types: {len(types)}")
        self._print(f"  Total strata: {len(types) * 3}")
        self._print(f"  Target total questions: {len(types) * questions_per_type}")
        self._print(f"  Max retries per type: {max_retries}")
        self._print(f"  Async mode: {'enabled' if use_async else 'disabled'}")
        if parallel:
            self._print(
                f"  Parallel mode: enabled (max {max_parallel} concurrent types)"
            )
        else:
            self._print("  Parallel mode: disabled")
        self._print(f"  Dry run: {'yes' if dry_run else 'no'}")
        self._print("")
        self._print("=" * 64)
        self._print("")

    def batch_mode_status(self, enabled: bool, reason: str) -> None:
        """Print batch API mode status.

        Args:
            enabled: Whether batch mode is enabled
            reason: Reason for the status
        """
        status = "ENABLED" if enabled else "DISABLED"
        self._print(f"Batch API mode: {status} ({reason})")
        self._print("")

    def type_start(
        self,
        type_index: int,
        total_types: int,
        question_type: str,
        count: int,
        parallel: bool = False,
    ) -> None:
        """Print type generation start message.

        Args:
            type_index: Current type index (1-based)
            total_types: Total number of types
            question_type: Name of the question type
            count: Number of questions to generate
            parallel: Whether running in parallel mode
        """
        if parallel:
            # In parallel mode, add type prefix for clarity
            self._print(f"[{question_type}] Starting generation ({count} questions)")
        else:
            self._print("")
            self._print(
                f"[{type_index}/{total_types}] Generating {question_type} ({count} questions)"
            )
            self._print("-" * 60)

    def phase_transition(self, phase: str, detail: str = "") -> None:
        """Print phase transition message.

        Args:
            phase: Phase name (e.g., "GENERATION", "VALIDATION", "INSERTION")
            detail: Optional detail about the phase
        """
        detail_str = f" - {detail}" if detail else ""
        self._print(f"  {self.BLUE}[PHASE]{self.RESET} {phase}{detail_str}")

    def progress(self, message: str, question_type: Optional[str] = None) -> None:
        """Print progress message.

        Args:
            message: Progress message
            question_type: Optional type prefix for parallel mode
        """
        if question_type:
            self._print(f"  {self.GREEN}[{question_type}]{self.RESET} {message}")
        else:
            self._print(f"  {self.GREEN}[PROGRESS]{self.RESET} {message}")

    def approval_rate(self, approved: int, total: int) -> None:
        """Print approval rate message.

        Args:
            approved: Number of approved questions
            total: Total questions attempted
        """
        rate = (approved / total * 100) if total > 0 else 0.0
        self._print(
            f"  {self.GREEN}[PROGRESS]{self.RESET} Approved: {approved}/{total} ({rate:.1f}%)"
        )

    def inserted(self, count: int) -> None:
        """Print insertion count message.

        Args:
            count: Number of questions inserted
        """
        self._print(
            f"  {self.GREEN}[PROGRESS]{self.RESET} Inserted {count} questions into database"
        )

    def retry_warning(
        self, attempt: int, max_retries: int, question_type: str, delay: float
    ) -> None:
        """Print retry warning message.

        Args:
            attempt: Current attempt number
            max_retries: Maximum retry attempts
            question_type: Name of the question type
            delay: Delay before retry in seconds
        """
        self._print(
            f"  {self.YELLOW}[RETRY]{self.RESET} Attempt {attempt}/{max_retries} "
            f"for {question_type} (waiting {delay:.1f}s)"
        )

    def type_complete(
        self,
        question_type: str,
        success: bool,
        duration: float,
        generated: int = 0,
        parallel: bool = False,
    ) -> None:
        """Print type completion message.

        Args:
            question_type: Name of the question type
            success: Whether generation succeeded
            duration: Duration in seconds
            generated: Number of questions generated (for success)
            parallel: Whether running in parallel mode
        """
        if not parallel:
            self._print("-" * 60)
        if success:
            self._print(
                f"{self.GREEN}✓{self.RESET} {question_type} completed successfully "
                f"({duration:.1f}s, {generated} questions)"
            )
        else:
            self._print(
                f"{self.RED}✗{self.RESET} {question_type} FAILED ({duration:.1f}s)"
            )

    def type_error(self, error_message: str) -> None:
        """Print type error message.

        Args:
            error_message: Error message to display
        """
        self._print(f"  Error: {self._truncate(error_message)}")

    def summary(
        self,
        successful_types: int,
        failed_types: int,
        total_types: int,
        total_duration: float,
        results: List["TypeResult"],
    ) -> None:
        """Print final summary.

        Args:
            successful_types: Number of successful types
            failed_types: Number of failed types
            total_types: Total number of types
            total_duration: Total duration in seconds
            results: List of TypeResult objects
        """
        total_minutes = int(total_duration) // 60
        total_seconds = int(total_duration) % 60

        self._print("")
        self._print("=" * 64)
        self._print("                     BOOTSTRAP SUMMARY")
        self._print("=" * 64)
        self._print("")
        self._print("Results:")
        self._print(f"  Successful types: {successful_types} / {total_types}")
        self._print(f"  Failed types: {failed_types}")
        self._print(f"  Total duration: {total_minutes}m {total_seconds}s")
        self._print("")
        self._print("Type Details:")

        for result in results:
            if result.success:
                self._print(
                    f"  {self.GREEN}[OK]{self.RESET} {result.question_type} - "
                    f"{result.generated} questions"
                )
            else:
                self._print(f"  {self.RED}[FAILED]{self.RESET} {result.question_type}")
                if result.error_message:
                    self._print(f"    Error: {self._truncate(result.error_message)}")

        self._print("")

    def final_status(self, success: bool) -> None:
        """Print final status message.

        Args:
            success: Whether overall bootstrap succeeded
        """
        if success:
            self._print(f"{self.GREEN}Bootstrap completed successfully!{self.RESET}")
        else:
            self._print(f"{self.YELLOW}Bootstrap completed with failures.{self.RESET}")


class EventLogger:
    """Structured event logger for monitoring integration."""

    def __init__(self, log_dir: Path):
        """Initialize the event logger.

        Args:
            log_dir: Directory to write JSONL event files
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.log_dir / "bootstrap_events.jsonl"

    def _rotate_if_needed(self) -> None:
        """Rotate the event log file if it exceeds the size limit."""
        if (
            self.events_file.exists()
            and self.events_file.stat().st_size > MAX_EVENT_FILE_SIZE_BYTES
        ):
            rotated_file = self.log_dir / f"bootstrap_events_{int(time.time())}.jsonl"
            self.events_file.rename(rotated_file)

    def log_event(
        self,
        event_type: str,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Log a structured event to the JSONL file.

        Args:
            event_type: Type of event (e.g., "script_start", "type_completed")
            status: Status of the event (e.g., "started", "success", "failed")
            **kwargs: Additional fields to include in the event
        """
        # Rotate log file if it exceeds size limit
        self._rotate_if_needed()

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "status": status,
            **kwargs,
        }

        with open(self.events_file, "a") as f:
            f.write(json.dumps(event) + "\n")


class BootstrapAlerter:
    """Handles alerting for critical failures in the bootstrap script.

    This class sends alerts when multiple question types fail during
    bootstrap, matching the behavior of the bash script's
    send_multi_type_failure_alert() function.

    Alerts are sent only when the failure count meets or exceeds
    CRITICAL_FAILURE_THRESHOLD (3 types).
    """

    # Sentinel file path for external monitoring
    FAILURE_FLAG_PATH = "logs/bootstrap_failure.flag"

    def __init__(
        self,
        alert_manager: Optional[AlertManager],
        event_logger: EventLogger,
        logger: logging.Logger,
        log_dir: Path,
    ):
        """Initialize the bootstrap alerter.

        Args:
            alert_manager: AlertManager instance (can be None if alerts disabled)
            event_logger: Event logger for structured logging
            logger: Python logger for console/file logging
            log_dir: Directory for log files
        """
        self.alert_manager = alert_manager
        self.event_logger = event_logger
        self.logger = logger
        self.log_dir = log_dir
        self._alert_sent = False

    def check_and_alert(self, results: List["TypeResult"]) -> bool:
        """Check results and send alert if critical failure threshold is met.

        This method:
        1. Counts failed types
        2. Checks if failure count meets CRITICAL_FAILURE_THRESHOLD
        3. Sends alert via AlertManager if threshold met
        4. Writes sentinel file for external monitoring
        5. Logs the alert event

        Args:
            results: List of TypeResult objects from the bootstrap run

        Returns:
            True if an alert was sent, False otherwise
        """
        # Count failed types
        failed_results = [r for r in results if not r.success]
        failed_count = len(failed_results)

        # Only alert if threshold is met
        if failed_count < CRITICAL_FAILURE_THRESHOLD:
            self.logger.debug(
                f"Failed count ({failed_count}) below threshold "
                f"({CRITICAL_FAILURE_THRESHOLD}), no alert needed"
            )
            return False

        # Avoid duplicate alerts
        if self._alert_sent:
            self.logger.debug("Alert already sent for this run, skipping")
            return False

        # Collect failed type names
        failed_types = [r.question_type for r in failed_results]
        failed_types_str = ",".join(failed_types)

        # Collect first error message for context (sanitized for safety)
        error_details = None
        for result in failed_results:
            if result.error_message:
                # Sanitize and truncate to 200 chars like bash script
                sanitized = _sanitize_error(result.error_message)
                error_details = sanitized[:200]
                break

        self.logger.warning(
            f"Critical failure: {failed_count} types failed "
            f"(threshold: {CRITICAL_FAILURE_THRESHOLD})"
        )
        self.logger.warning(f"Failed types: {failed_types_str}")

        # Log the multi-type failure event
        self.event_logger.log_event(
            "multi_type_failure",
            "critical",
            failed_count=failed_count,
            failed_types=failed_types_str,
            threshold=CRITICAL_FAILURE_THRESHOLD,
        )

        # Write sentinel file for external monitoring
        self._write_failure_flag(failed_count, failed_types, error_details)

        # Send alert via AlertManager
        if self.alert_manager:
            success = self._send_alert(failed_count, failed_types, error_details)
            if success:
                self._alert_sent = True
                self.logger.info("Critical failure alert sent successfully")
            else:
                self.logger.warning("Failed to send critical failure alert")
            return success
        else:
            self.logger.info(
                "AlertManager not configured, skipping alert "
                "(failure logged to JSONL and sentinel file)"
            )
            self._alert_sent = True
            return False

    def _send_alert(
        self,
        failed_count: int,
        failed_types: List[str],
        error_details: Optional[str],
    ) -> bool:
        """Send alert via AlertManager.

        Args:
            failed_count: Number of failed types
            failed_types: List of failed type names
            error_details: First error message for context

        Returns:
            True if alert was sent successfully
        """
        if not self.alert_manager:
            return False

        # Build the classified error
        failed_types_str = ", ".join(failed_types)
        message = (
            f"Bootstrap script critical failure: {failed_count} question types failed "
            f"(threshold: {CRITICAL_FAILURE_THRESHOLD}). Failed types: {failed_types_str}. "
            f"Question generation pipeline may be unable to maintain inventory levels."
        )

        classified_error = ClassifiedError(
            category=ErrorCategory.SCRIPT_FAILURE,
            severity=ErrorSeverity.CRITICAL,
            provider="bootstrap_script",
            original_error="MultiTypeFailure",
            message=message,
            is_retryable=True,  # Script can be re-run
        )

        # Build context with failed type details
        context_lines = [
            f"Failed types ({failed_count}):",
        ]
        for qtype in failed_types:
            context_lines.append(f"  - {qtype}")

        if error_details:
            context_lines.extend(
                [
                    "",
                    f"Sample error: {error_details}",
                ]
            )

        context = "\n".join(context_lines)

        return self.alert_manager.send_alert(classified_error, context)

    def _write_failure_flag(
        self,
        failed_count: int,
        failed_types: List[str],
        error_details: Optional[str],
    ) -> None:
        """Write sentinel file for external monitoring.

        This file can be checked by external monitoring tools to detect
        bootstrap failures without parsing logs.

        Args:
            failed_count: Number of failed types
            failed_types: List of failed type names
            error_details: First error message for context
        """
        try:
            flag_path = self.log_dir / "bootstrap_failure.flag"
            flag_path.parent.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(timezone.utc).isoformat()
            content = {
                "timestamp": timestamp,
                "failed_count": failed_count,
                "failed_types": failed_types,
                "threshold": CRITICAL_FAILURE_THRESHOLD,
                "error_sample": error_details,
            }

            with open(flag_path, "w") as f:
                json.dump(content, f, indent=2)

            self.logger.info(f"Failure flag written to {flag_path}")
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to write failure flag: {e}")


class BootstrapInventory:
    """Orchestrates question generation across all types."""

    def __init__(
        self,
        config: BootstrapConfig,
        event_logger: EventLogger,
        logger: logging.Logger,
        progress_reporter: Optional[ProgressReporter] = None,
        alerter: Optional[BootstrapAlerter] = None,
    ):
        """Initialize the bootstrap process.

        Args:
            config: Bootstrap configuration
            event_logger: Event logger for structured logging
            logger: Python logger for console/file logging
            progress_reporter: Optional progress reporter for terminal output
            alerter: Optional alerter for critical failure notifications
        """
        self.config = config
        self.event_logger = event_logger
        self.logger = logger
        self.progress = progress_reporter or ProgressReporter(quiet=config.quiet)
        self.alerter = alerter
        self.pipeline: Optional[QuestionGenerationPipeline] = None
        self.results: List[TypeResult] = []

    def _initialize_pipeline(self) -> QuestionGenerationPipeline:
        """Initialize the question generation pipeline.

        Returns:
            Initialized pipeline

        Raises:
            ValueError: If no API keys are configured
        """
        self.logger.info("Initializing question generation pipeline...")

        pipeline = QuestionGenerationPipeline(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            xai_api_key=settings.xai_api_key,
        )

        providers = pipeline.generator.get_available_providers()
        self.logger.info(f"Pipeline initialized with providers: {providers}")

        return pipeline

    def _supports_batch_api(self) -> bool:
        """Check if the current provider configuration supports batch API.

        Currently only Google provider supports batch API. This method checks
        if Google is available as a provider.

        Returns:
            True if batch API is supported and enabled, False otherwise
        """
        if not settings.enable_batch_generation:
            return False

        if self.pipeline is None:
            return False

        # Check if Google provider is available
        try:
            available_providers = self.pipeline.generator.get_available_providers()
            # Handle case where mock or unexpected type is returned
            if not isinstance(available_providers, (list, tuple, set)):
                return False
            return "google" in available_providers
        except (AttributeError, TypeError):
            # Handle cases where generator or get_available_providers doesn't exist
            return False

    async def _generate_type_with_batch_api(
        self,
        question_type: QuestionType,
        count: int,
    ) -> GenerationResult:
        """Generate questions using batch API (for Google provider).

        This method:
        1. Gets the Google provider from the pipeline
        2. Builds prompts for all questions across difficulties
        3. Submits prompts as a batch job
        4. Polls for completion
        5. Parses responses back to question records

        Args:
            question_type: Type of questions to generate
            count: Total number of questions to generate (distributed across difficulties)

        Returns:
            GenerationResult with generation results

        Raises:
            ValueError: If Google provider is not available
            TimeoutError: If batch job doesn't complete within timeout
            Exception: If batch job fails
        """
        if self.pipeline is None:
            raise RuntimeError("Pipeline not initialized - cannot generate questions")

        # Get Google provider
        if "google" not in self.pipeline.generator.providers:
            raise ValueError("Google provider not available for batch generation")

        google_provider = self.pipeline.generator.providers["google"]
        if not isinstance(google_provider, GoogleProvider):
            raise ValueError("Google provider is not a GoogleProvider instance")

        # Calculate questions per difficulty (dynamic based on enum size)
        difficulty_levels = list(DifficultyLevel)
        num_difficulties = len(difficulty_levels)
        questions_per_difficulty = count // num_difficulties
        remainder = count % num_difficulties

        # Build all prompts upfront
        prompts: List[str] = []
        # Map prompt index to difficulty for response parsing
        prompt_to_difficulty: dict[int, DifficultyLevel] = {}

        for i, difficulty in enumerate(difficulty_levels):
            # Distribute remainder across first few difficulties
            diff_count = questions_per_difficulty + (1 if i < remainder else 0)
            if diff_count == 0:
                continue

            self.logger.info(
                f"Building {diff_count} prompts for {question_type.value}/{difficulty.value}"
            )

            # Build prompts for this difficulty level
            for _ in range(diff_count):
                prompt = build_generation_prompt(question_type, difficulty, count=1)
                prompt_to_difficulty[len(prompts)] = difficulty
                prompts.append(prompt)

        if not prompts:
            self.logger.warning(f"No prompts built for {question_type.value}")
            return GenerationResult(questions=[], generated=0, target=count)

        # Validate batch size doesn't exceed limit
        batch_size_limit = settings.batch_generation_size
        if len(prompts) > batch_size_limit:
            self.logger.warning(
                f"Prompt count ({len(prompts)}) exceeds batch size limit "
                f"({batch_size_limit}). Processing in chunks."
            )

        self.logger.info(
            f"Submitting batch job with {len(prompts)} prompts for {question_type.value}"
        )

        # Log batch generation start event
        self.event_logger.log_event(
            "batch_generation_start",
            "started",
            type=question_type.value,
            total_prompts=len(prompts),
        )

        # Process prompts in chunks if needed (respecting batch size limit)
        all_questions: List[Any] = []
        total_parse_errors = 0
        total_successful = 0
        total_failed = 0

        chunk_size = settings.batch_generation_size
        for chunk_start in range(0, len(prompts), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(prompts))
            chunk_prompts = prompts[chunk_start:chunk_end]
            chunk_num = (chunk_start // chunk_size) + 1
            total_chunks = (len(prompts) + chunk_size - 1) // chunk_size

            if total_chunks > 1:
                self.logger.info(
                    f"Processing batch chunk {chunk_num}/{total_chunks} "
                    f"({len(chunk_prompts)} prompts)"
                )

            # Submit batch job and wait for completion
            try:
                batch_result = await google_provider.generate_batch_completions_async(
                    prompts=chunk_prompts,
                    display_name=f"bootstrap-{question_type.value}-{int(time.time())}-{chunk_num}",
                    temperature=0.8,
                    max_tokens=1500,
                    poll_interval=30.0,
                    timeout=settings.batch_generation_timeout,
                )

                self.logger.info(
                    f"Batch chunk {chunk_num} completed: "
                    f"{batch_result.successful_requests}/{batch_result.total_requests} successful"
                )
                total_successful += batch_result.successful_requests
                total_failed += batch_result.failed_requests

            except TimeoutError as e:
                self.logger.error(f"Batch job timed out: {e}")
                self.event_logger.log_event(
                    "batch_generation_complete",
                    "failed",
                    type=question_type.value,
                    error=_truncate_error(e),
                )
                raise
            except Exception as e:
                self.logger.error(f"Batch job failed: {e}")
                self.event_logger.log_event(
                    "batch_generation_complete",
                    "failed",
                    type=question_type.value,
                    error=_truncate_error(e),
                )
                raise

            # Parse responses into questions
            # Note: Each batch job submission uses keys "request-0" to "request-N"
            # where N is relative to that chunk. We add chunk_start to get the
            # global prompt index for difficulty mapping.
            for response_dict in batch_result.responses:
                try:
                    # Extract key to get chunk-relative index (format: "request-N")
                    key = response_dict.get("key", "")
                    # Calculate global prompt index: chunk_start + relative index
                    prompt_idx = chunk_start  # Default to chunk start
                    if key and "-" in key:
                        try:
                            relative_idx = int(key.split("-")[-1])
                            prompt_idx = chunk_start + relative_idx
                        except ValueError:
                            pass

                    # Get difficulty from our mapping
                    difficulty = prompt_to_difficulty.get(prompt_idx)

                    # Parse text response as JSON
                    text = response_dict.get("text", "")
                    if not text:
                        total_parse_errors += 1
                        continue

                    # Parse the JSON response
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError as e:
                        total_parse_errors += 1
                        self.logger.warning(f"Invalid JSON in response {key}: {e}")
                        continue

                    # Validate response is a dict (not array or other type)
                    if not isinstance(parsed, dict):
                        total_parse_errors += 1
                        self.logger.warning(
                            f"Response {key} is not a dict: {type(parsed).__name__}"
                        )
                        continue

                    # Extract question data
                    question_data = {
                        "question_text": parsed.get("question_text", ""),
                        "correct_answer": parsed.get("correct_answer", ""),
                        "answer_options": parsed.get("answer_options", []),
                        "explanation": parsed.get("explanation", ""),
                    }

                    # Validate required fields
                    if not all(
                        [
                            question_data["question_text"],
                            question_data["correct_answer"],
                            question_data["answer_options"],
                        ]
                    ):
                        total_parse_errors += 1
                        self.logger.warning(
                            f"Incomplete question data in response {key}"
                        )
                        continue

                    # Create a GeneratedQuestion-like object with difficulty
                    question = {
                        "question_type": question_type,
                        "difficulty": difficulty,
                        "question_text": question_data["question_text"],
                        "correct_answer": question_data["correct_answer"],
                        "answer_options": question_data["answer_options"],
                        "explanation": question_data["explanation"],
                        "source_llm": "google",
                    }
                    all_questions.append(question)

                except Exception as e:
                    total_parse_errors += 1
                    self.logger.warning(
                        f"Failed to process response for key "
                        f"{response_dict.get('key', 'unknown')}: {e}"
                    )

        # Log batch generation completion event
        self.event_logger.log_event(
            "batch_generation_complete",
            "success",
            type=question_type.value,
            total_requests=len(prompts),
            successful_requests=total_successful,
            failed_requests=total_failed,
            parse_errors=total_parse_errors,
            questions_generated=len(all_questions),
        )

        if total_parse_errors > 0:
            self.logger.warning(
                f"Encountered {total_parse_errors} parse errors out of "
                f"{total_successful} responses"
            )

        # Fail if parse error rate exceeds 25% threshold
        # This prevents silently returning partial data when most responses fail
        if total_successful > 0:
            parse_error_rate = total_parse_errors / total_successful
            if parse_error_rate > BATCH_PARSE_ERROR_THRESHOLD:
                raise ValueError(
                    f"Parse error rate {parse_error_rate:.1%} exceeds "
                    f"{BATCH_PARSE_ERROR_THRESHOLD:.0%} threshold. "
                    f"{total_parse_errors} of {total_successful} responses failed to parse."
                )

        return GenerationResult(
            questions=all_questions,
            generated=len(all_questions),
            target=count,
        )

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay before next retry using exponential backoff with jitter.

        Uses exponential backoff with random jitter to prevent thundering herd
        problems when multiple processes retry simultaneously.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds with added jitter
        """
        delay = self.config.retry_base_delay * (2 ** (attempt - 1))
        capped_delay = min(delay, self.config.retry_max_delay)

        # Add jitter: random value between 0 and 25% of delay
        jitter = random.uniform(0, capped_delay * 0.25)
        return capped_delay + jitter

    async def _generate_type_async(
        self,
        question_type: QuestionType,
        count: int,
    ) -> GenerationResult:
        """Generate questions for a single type asynchronously.

        Args:
            question_type: Type of questions to generate
            count: Number of questions to generate

        Returns:
            GenerationResult with generation results
        """
        questions_per_difficulty = count // 3
        remainder = count % 3

        all_questions: List[Any] = []
        total_generated = 0

        for i, difficulty in enumerate(DifficultyLevel):
            # Distribute remainder across first few difficulties
            diff_count = questions_per_difficulty + (1 if i < remainder else 0)
            if diff_count == 0:
                continue

            self.logger.info(
                f"Generating {diff_count} {question_type.value}/{difficulty.value} questions"
            )

            batch = await self.pipeline.generate_questions_async(
                question_type=question_type,
                difficulty=difficulty,
                count=diff_count,
                distribute_providers=True,
            )

            all_questions.extend(batch.questions)
            total_generated += len(batch.questions)

            self.logger.info(
                f"Generated {len(batch.questions)}/{diff_count} "
                f"{question_type.value}/{difficulty.value} questions"
            )

        return GenerationResult(
            questions=all_questions,
            generated=total_generated,
            target=count,
        )

    def _generate_type_sync(
        self,
        question_type: QuestionType,
        count: int,
    ) -> GenerationResult:
        """Generate questions for a single type synchronously.

        Args:
            question_type: Type of questions to generate
            count: Number of questions to generate

        Returns:
            GenerationResult with generation results
        """
        questions_per_difficulty = count // 3
        remainder = count % 3

        all_questions: List[Any] = []
        total_generated = 0

        for i, difficulty in enumerate(DifficultyLevel):
            # Distribute remainder across first few difficulties
            diff_count = questions_per_difficulty + (1 if i < remainder else 0)
            if diff_count == 0:
                continue

            self.logger.info(
                f"Generating {diff_count} {question_type.value}/{difficulty.value} questions"
            )

            batch = self.pipeline.generate_questions(
                question_type=question_type,
                difficulty=difficulty,
                count=diff_count,
                distribute_providers=True,
            )

            all_questions.extend(batch.questions)
            total_generated += len(batch.questions)

            self.logger.info(
                f"Generated {len(batch.questions)}/{diff_count} "
                f"{question_type.value}/{difficulty.value} questions"
            )

        return GenerationResult(
            questions=all_questions,
            generated=total_generated,
            target=count,
        )

    async def _process_type_with_semaphore(
        self,
        question_type: str,
        semaphore: asyncio.Semaphore,
        type_index: int,
    ) -> TypeResult:
        """Process a single question type with semaphore-based rate limiting.

        This wrapper acquires the semaphore before processing to limit
        concurrent type generations.

        Args:
            question_type: Question type to process
            semaphore: Semaphore to limit concurrent operations
            type_index: Index of this type in the list (1-based)

        Returns:
            TypeResult with generation results
        """
        async with semaphore:
            self.progress.type_start(
                type_index,
                len(self.config.types),
                question_type,
                self.config.questions_per_type,
                parallel=True,
            )
            return await self._process_type_with_retries(question_type)

    async def _process_type_with_retries(
        self,
        question_type: str,
    ) -> TypeResult:
        """Process a single question type with retry logic.

        Args:
            question_type: Question type to process

        Returns:
            TypeResult with generation results
        """
        qt = QuestionType(question_type)
        attempt = 0
        last_error: Optional[str] = None
        start_time = time.time()

        while attempt < self.config.max_retries:
            attempt += 1
            attempt_start = time.time()

            self.event_logger.log_event(
                "type_start",
                "started",
                type=question_type,
                attempt=attempt,
                max_retries=self.config.max_retries,
                target_per_type=self.config.questions_per_type,
            )

            if attempt > 1:
                delay = self._calculate_retry_delay(attempt - 1)
                self.logger.info(
                    f"Retry {attempt}/{self.config.max_retries} for {question_type} "
                    f"(waiting {delay:.1f}s)"
                )
                await asyncio.sleep(delay)

            try:
                # Validate pipeline is initialized
                if self.pipeline is None:
                    raise RuntimeError(
                        "Pipeline not initialized - cannot generate questions"
                    )

                # Check if batch API should be used
                use_batch_api = (
                    self.config.use_batch
                    and self.config.use_async
                    and self._supports_batch_api()
                )

                if use_batch_api:
                    # Use batch API for generation (Google only)
                    self.logger.info(f"Using batch API for {question_type} generation")
                    result = await asyncio.wait_for(
                        self._generate_type_with_batch_api(
                            qt, self.config.questions_per_type
                        ),
                        # Use 10% buffer with minimum of 60s
                        timeout=settings.batch_generation_timeout
                        + max(
                            BATCH_TIMEOUT_BUFFER_MIN_SECONDS,
                            int(
                                settings.batch_generation_timeout
                                * BATCH_TIMEOUT_BUFFER_RATIO
                            ),
                        ),
                    )
                elif self.config.use_async:
                    # Add timeout protection for async generation
                    result = await asyncio.wait_for(
                        self._generate_type_async(qt, self.config.questions_per_type),
                        timeout=GENERATION_TIMEOUT_SECONDS,
                    )
                else:
                    result = self._generate_type_sync(
                        qt, self.config.questions_per_type
                    )

                duration = time.time() - start_time
                generated = result["generated"]
                approval_rate = (
                    (generated / result["target"]) * 100 if result["target"] > 0 else 0
                )

                self.event_logger.log_event(
                    "type_end",
                    "success",
                    type=question_type,
                    attempt=attempt,
                    duration_seconds=round(duration, 2),
                    generated=generated,
                    target=result["target"],
                )

                return TypeResult(
                    question_type=question_type,
                    success=True,
                    attempt_count=attempt,
                    generated=generated,
                    approval_rate=approval_rate,
                    duration_seconds=duration,
                )

            except asyncio.TimeoutError:
                last_error = f"Generation timed out after {GENERATION_TIMEOUT_SECONDS}s"
                attempt_duration = time.time() - attempt_start
                if attempt < self.config.max_retries:
                    self.logger.warning(
                        f"Attempt {attempt}/{self.config.max_retries} timed out for "
                        f"{question_type} (will retry)"
                    )
                else:
                    self.logger.error(
                        f"All {self.config.max_retries} attempts failed for "
                        f"{question_type}: {last_error}"
                    )

                status = (
                    "failed" if attempt >= self.config.max_retries else "retry_failed"
                )
                self.event_logger.log_event(
                    "type_end",
                    status,
                    type=question_type,
                    attempt=attempt,
                    duration_seconds=round(attempt_duration, 2),
                    error=last_error,
                )

            except Exception as e:
                # Sanitize error message to prevent leaking sensitive info
                last_error = _sanitize_error(e)
                attempt_duration = time.time() - attempt_start

                if attempt < self.config.max_retries:
                    self.logger.warning(
                        f"Attempt {attempt}/{self.config.max_retries} failed for "
                        f"{question_type}: {last_error} (will retry)"
                    )
                else:
                    self.logger.exception(
                        f"All {self.config.max_retries} attempts failed for "
                        f"{question_type}"
                    )

                status = (
                    "failed" if attempt >= self.config.max_retries else "retry_failed"
                )
                self.event_logger.log_event(
                    "type_end",
                    status,
                    type=question_type,
                    attempt=attempt,
                    duration_seconds=round(attempt_duration, 2),
                    error=_truncate_error(last_error) if last_error else None,
                )

        # All retries exhausted
        duration = time.time() - start_time
        return TypeResult(
            question_type=question_type,
            success=False,
            attempt_count=attempt,
            duration_seconds=duration,
            error_message=last_error,
        )

    async def _process_types_parallel(self) -> List[TypeResult]:
        """Process all types in parallel with semaphore-based rate limiting.

        Creates tasks for all types and uses asyncio.gather with
        return_exceptions=True to handle partial failures gracefully.

        Returns:
            List of TypeResult objects (one per type)
        """
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.config.max_parallel)

        # Create tasks for all types
        tasks = []
        for i, question_type in enumerate(self.config.types, 1):
            task = self._process_type_with_semaphore(question_type, semaphore, i)
            tasks.append(task)

        # Execute all tasks concurrently with exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle exceptions
        processed_results: List[TypeResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Task raised an exception - create a failed TypeResult
                question_type = self.config.types[i]
                # Sanitize error to prevent leaking sensitive info
                sanitized_error = _sanitize_error(result)
                self.logger.error(
                    f"Unexpected error processing {question_type}: {sanitized_error}"
                )
                processed_results.append(
                    TypeResult(
                        question_type=question_type,
                        success=False,
                        attempt_count=0,
                        error_message=f"Unexpected error: {sanitized_error}",
                    )
                )
            else:
                # Task succeeded, add the result
                processed_results.append(result)

        return processed_results

    async def run(self) -> int:
        """Run the bootstrap process.

        Returns:
            Exit code (0 for success, 1 for partial failure, 2 for config error)
        """
        start_time = time.time()

        # Log script start
        self.event_logger.log_event(
            "script_start",
            "started",
            total_types=len(self.config.types),
            target_per_type=self.config.questions_per_type,
            types=",".join(self.config.types),
            async_mode="enabled" if self.config.use_async else "disabled",
            batch_mode="enabled" if self.config.use_batch else "disabled",
            parallel_mode="enabled" if self.config.parallel else "disabled",
            max_parallel=self.config.max_parallel if self.config.parallel else None,
            dry_run="yes" if self.config.dry_run else "no",
        )

        # Print banner via progress reporter
        self.progress.banner(
            questions_per_type=self.config.questions_per_type,
            types=self.config.types,
            max_retries=self.config.max_retries,
            use_async=self.config.use_async,
            use_batch=self.config.use_batch,
            dry_run=self.config.dry_run,
            parallel=self.config.parallel,
            max_parallel=self.config.max_parallel,
        )

        # Initialize pipeline
        try:
            self.pipeline = self._initialize_pipeline()
        except Exception as e:
            self.logger.error(f"Failed to initialize pipeline: {e}")
            self.event_logger.log_event(
                "script_end",
                "failed",
                error=_truncate_error(e),
                exit_code=EXIT_CONFIG_ERROR,
            )
            return EXIT_CONFIG_ERROR

        # Check and log batch API availability
        if self.config.use_batch and self._supports_batch_api():
            self.progress.batch_mode_status(True, "Google provider detected")
        elif self.config.use_batch:
            self.progress.batch_mode_status(False, "Google provider not available")
        else:
            self.progress.batch_mode_status(False, "--no-batch flag")

        # Use try-finally to ensure pipeline cleanup
        try:
            # Process types (parallel or sequential based on config)
            successful_types = 0
            failed_types = 0

            if self.config.parallel:
                # Parallel mode: process all types concurrently
                self.logger.info(
                    f"Processing {len(self.config.types)} types in parallel "
                    f"(max {self.config.max_parallel} concurrent)"
                )
                self.results = await self._process_types_parallel()

                # Print completion messages for each result
                for result in self.results:
                    self.progress.type_complete(
                        result.question_type,
                        result.success,
                        result.duration_seconds,
                        result.generated,
                        parallel=True,
                    )
                    if not result.success and result.error_message:
                        self.progress.type_error(result.error_message)

                # Count successes and failures
                successful_types = sum(1 for r in self.results if r.success)
                failed_types = sum(1 for r in self.results if not r.success)

            else:
                # Sequential mode: process types one at a time
                for i, question_type in enumerate(self.config.types, 1):
                    self.progress.type_start(
                        i,
                        len(self.config.types),
                        question_type,
                        self.config.questions_per_type,
                        parallel=False,
                    )

                    type_start = time.time()
                    result = await self._process_type_with_retries(question_type)
                    self.results.append(result)

                    type_duration = time.time() - type_start

                    self.progress.type_complete(
                        question_type,
                        result.success,
                        type_duration,
                        result.generated,
                        parallel=False,
                    )

                    if result.success:
                        successful_types += 1
                    else:
                        if result.error_message:
                            self.progress.type_error(result.error_message)
                        failed_types += 1

            # Calculate final stats
            total_duration = time.time() - start_time

            # Print summary via progress reporter
            self.progress.summary(
                successful_types=successful_types,
                failed_types=failed_types,
                total_types=len(self.config.types),
                total_duration=total_duration,
                results=self.results,
            )

            # Determine exit code and log script end
            if failed_types > 0:
                exit_code = EXIT_PARTIAL_FAILURE
                status = "failed"
            else:
                exit_code = EXIT_SUCCESS
                status = "success"

            self.progress.final_status(failed_types == 0)

            # Check for critical failures and send alert if needed
            if self.alerter and failed_types > 0:
                self.alerter.check_and_alert(self.results)

            self.event_logger.log_event(
                "script_end",
                status,
                successful_types=successful_types,
                failed_types=failed_types,
                total_duration_seconds=round(total_duration, 2),
                types_processed=",".join(self.config.types),
                exit_code=exit_code,
            )

            return exit_code

        finally:
            # Always cleanup pipeline resources
            if self.pipeline:
                await self.pipeline.cleanup()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Generate initial question inventory across all types.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate full inventory: 150 questions per type
  python scripts/bootstrap_inventory.py

  # Generate only math questions
  python scripts/bootstrap_inventory.py --types math

  # Generate pattern and logic questions
  python scripts/bootstrap_inventory.py --types pattern,logic

  # Generate more questions per type (300 = 100 per difficulty)
  python scripts/bootstrap_inventory.py --count 300

  # Parallel generation with default concurrency (2 types at once)
  python scripts/bootstrap_inventory.py --parallel

  # Parallel generation with higher concurrency (4 types at once)
  python scripts/bootstrap_inventory.py --parallel --max-parallel 4

  # Dry run to test without database writes
  python scripts/bootstrap_inventory.py --dry-run --count 15 --types math

  # Stable mode for troubleshooting (no async)
  python scripts/bootstrap_inventory.py --no-async --count 30 --types verbal
        """,
    )

    parser.add_argument(
        "--count",
        type=int,
        default=150,
        help="Total questions per type (distributed across 3 difficulties). Default: 150",
    )

    parser.add_argument(
        "--types",
        type=str,
        default=None,
        help="Comma-separated list of types to generate (default: all). "
        f"Valid types: {', '.join(qt.value for qt in QuestionType)}",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate without database insertion",
    )

    parser.add_argument(
        "--no-async",
        action="store_true",
        help="Disable async generation (slower but more stable)",
    )

    parser.add_argument(
        "--no-batch",
        action="store_true",
        help="Disable batch API generation (use sequential calls)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries per type (default: 3)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress terminal progress output (JSONL events still logged)",
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel generation across question types",
    )

    parser.add_argument(
        "--max-parallel",
        type=int,
        default=2,
        help="Maximum concurrent type generations when --parallel is enabled (default: 2)",
    )

    return parser.parse_args()


def validate_types(types_str: Optional[str]) -> List[str]:
    """Validate and parse the types argument.

    Args:
        types_str: Comma-separated list of types, or None for all

    Returns:
        List of valid type strings

    Raises:
        ValueError: If an invalid type is specified
    """
    valid_types = {qt.value for qt in QuestionType}

    if types_str is None:
        return list(valid_types)

    types = [t.strip().lower() for t in types_str.split(",")]

    for t in types:
        if t not in valid_types:
            raise ValueError(
                f"Invalid question type: {t}. Valid types: {', '.join(valid_types)}"
            )

    return types


def validate_count(count: int) -> None:
    """Validate the count argument.

    Args:
        count: Number of questions per type

    Raises:
        ValueError: If count is out of valid range
    """
    if count < 1 or count > MAX_QUESTIONS_PER_TYPE:
        raise ValueError(
            f"--count must be between 1 and {MAX_QUESTIONS_PER_TYPE} (got: {count}). "
            f"Maximum prevents excessive API costs and runtime."
        )

    if count < 3:
        print(
            f"Warning: --count {count} is less than 3. "
            "Some difficulty levels will receive 0 questions."
        )


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    args = parse_arguments()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level=log_level)
    logger = logging.getLogger(__name__)

    # Validate arguments
    try:
        validate_count(args.count)
        types = validate_types(args.types)
    except ValueError as e:
        print(f"Error: {e}")
        return EXIT_CONFIG_ERROR

    # Check for API keys
    if not any(
        [
            settings.openai_api_key,
            settings.anthropic_api_key,
            settings.google_api_key,
            settings.xai_api_key,
        ]
    ):
        print("Error: No LLM API key found")
        print()
        print(
            "The question service requires at least one of the following environment variables:"
        )
        print("  - OPENAI_API_KEY")
        print("  - ANTHROPIC_API_KEY")
        print("  - GOOGLE_API_KEY")
        print("  - XAI_API_KEY")
        print()
        print("Set one of these before running this script.")
        return EXIT_CONFIG_ERROR

    # Create configuration
    config = BootstrapConfig(
        questions_per_type=args.count,
        types=types,
        dry_run=args.dry_run,
        use_async=not args.no_async,
        use_batch=not args.no_batch,
        max_retries=args.max_retries,
        quiet=args.quiet,
        parallel=args.parallel,
        max_parallel=args.max_parallel,
    )

    # Create event logger
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / "logs"
    event_logger = EventLogger(log_dir)

    # Create alert manager if configured
    alert_manager: Optional[AlertManager] = None
    if settings.enable_email_alerts:
        # Parse comma-separated email list
        to_emails = (
            [e.strip() for e in settings.alert_to_emails.split(",")]
            if settings.alert_to_emails
            else []
        )
        alert_manager = AlertManager(
            email_enabled=settings.enable_email_alerts,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            from_email=settings.alert_from_email,
            to_emails=to_emails,
            alert_file_path=str(log_dir / "bootstrap_alerts.log"),
        )
        logger.info("AlertManager configured for email alerts")
    else:
        logger.info("AlertManager not configured (email alerts disabled)")

    # Create bootstrap alerter
    alerter = BootstrapAlerter(
        alert_manager=alert_manager,
        event_logger=event_logger,
        logger=logger,
        log_dir=log_dir,
    )

    # Run bootstrap
    bootstrap = BootstrapInventory(config, event_logger, logger, alerter=alerter)
    return await bootstrap.run()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
