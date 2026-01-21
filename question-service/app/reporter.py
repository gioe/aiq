"""Run reporter for question generation pipeline.

This module provides functionality to report generation run metrics
to the backend API for persistence and analysis.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from .metrics import MetricsTracker
from .type_mapping import normalize_difficulty_metrics, normalize_type_metrics

logger = logging.getLogger(__name__)

# Exit codes from run_generation.py
EXIT_CODE_PARTIAL_FAILURE = 3

# HTTP status codes
HTTP_STATUS_CREATED = 201


class RunReporter:
    """Reports generation run metrics to the backend API.

    This class handles the transformation of MetricsTracker data into
    the API payload format and manages HTTP communication with the backend.
    Connection failures are handled gracefully (logged, not raised) to
    ensure the generation pipeline continues even if reporting fails.

    Attributes:
        backend_url: Base URL for the backend API
        service_key: API key for service-to-service authentication
        timeout: HTTP request timeout in seconds
    """

    def __init__(
        self,
        backend_url: str,
        service_key: str,
        timeout: float = 30.0,
    ):
        """Initialize RunReporter.

        Args:
            backend_url: Base URL for the backend API (e.g., "https://api.example.com")
            service_key: API key for X-Service-Key header authentication
            timeout: HTTP request timeout in seconds (default: 30.0)
        """
        self.backend_url = backend_url.rstrip("/")
        self.service_key = service_key
        self.timeout = timeout
        logger.debug(f"RunReporter initialized with backend_url: {self.backend_url}")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Dictionary of HTTP headers including authentication
        """
        return {
            "Content-Type": "application/json",
            "X-Service-Key": self.service_key,
        }

    def _transform_metrics_to_payload(
        self,
        summary: Dict[str, Any],
        exit_code: int,
        environment: Optional[str] = None,
        triggered_by: Optional[str] = None,
        prompt_version: Optional[str] = None,
        arbiter_config_version: Optional[str] = None,
        min_arbiter_score_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Transform MetricsTracker summary to API payload format.

        Args:
            summary: Output from MetricsTracker.get_summary()
            exit_code: Exit code from the generation run (0-6)
            environment: Environment name (production, staging, development)
            triggered_by: Trigger source (scheduler, manual, webhook)
            prompt_version: Version of prompts used
            arbiter_config_version: Version of arbiter config used
            min_arbiter_score_threshold: Minimum arbiter score for approval

        Returns:
            Dictionary matching QuestionGenerationRunCreate schema
        """
        execution = summary.get("execution", {})
        generation = summary.get("generation", {})
        evaluation = summary.get("evaluation", {})
        deduplication = summary.get("deduplication", {})
        database = summary.get("database", {})
        api = summary.get("api", {})
        error_classification = summary.get("error_classification", {})
        overall = summary.get("overall", {})

        # Determine status based on exit code
        status = self._determine_status(exit_code, overall)

        # Build provider metrics from generation and API data
        provider_metrics = self._build_provider_metrics(generation, api)

        # Build error summary
        error_summary = {
            "by_category": error_classification.get("by_category", {}),
            "by_severity": error_classification.get("by_severity", {}),
            "critical_count": error_classification.get("critical_errors", 0),
        }

        payload: Dict[str, Any] = {
            # Execution timing
            "started_at": execution.get("start_time"),
            "completed_at": execution.get("end_time"),
            "duration_seconds": execution.get("duration_seconds"),
            # Status & outcome
            "status": status,
            "exit_code": exit_code,
            # Generation metrics
            "questions_requested": generation.get("requested", 0),
            "questions_generated": generation.get("generated", 0),
            "generation_failures": generation.get("failed", 0),
            "generation_success_rate": generation.get("success_rate"),
            # Evaluation metrics
            "questions_evaluated": evaluation.get("evaluated", 0),
            "questions_approved": evaluation.get("approved", 0),
            "questions_rejected": evaluation.get("rejected", 0),
            "approval_rate": evaluation.get("approval_rate"),
            "avg_arbiter_score": evaluation.get("average_score"),
            "min_arbiter_score": evaluation.get("min_score"),
            "max_arbiter_score": evaluation.get("max_score"),
            # Deduplication metrics
            "duplicates_found": deduplication.get("duplicates_found", 0),
            "exact_duplicates": deduplication.get("exact_duplicates", 0),
            "semantic_duplicates": deduplication.get("semantic_duplicates", 0),
            "duplicate_rate": deduplication.get("duplicate_rate"),
            # Database metrics
            "questions_inserted": database.get("inserted", 0),
            "insertion_failures": database.get("failed", 0),
            # Overall success
            "overall_success_rate": overall.get("overall_success_rate"),
            "total_errors": overall.get("total_errors", 0),
            # API usage
            "total_api_calls": api.get("total_calls", 0),
            # Breakdown by provider
            "provider_metrics": provider_metrics if provider_metrics else None,
            # Breakdown by question type (normalized to canonical backend values)
            "type_metrics": normalize_type_metrics(generation.get("by_type", {}))
            or None,
            # Breakdown by difficulty (normalized to canonical backend values)
            "difficulty_metrics": normalize_difficulty_metrics(
                generation.get("by_difficulty", {})
            )
            or None,
            # Error tracking
            "error_summary": error_summary if any(error_summary.values()) else None,
            # Configuration used
            "prompt_version": prompt_version,
            "arbiter_config_version": arbiter_config_version,
            "min_arbiter_score_threshold": min_arbiter_score_threshold,
            # Environment context
            "environment": environment,
            "triggered_by": triggered_by,
        }

        return payload

    def _determine_status(self, exit_code: int, overall: Dict[str, Any]) -> str:
        """Determine run status based on exit code and metrics.

        Exit codes from run_generation.py:
            0: Success
            1: Configuration error
            2: No questions generated
            3: Partial failure (some questions generated)
            4: Database error
            5: Unknown error
            6: Pipeline error

        Args:
            exit_code: Exit code from the generation run
            overall: Overall metrics from summary

        Returns:
            Status string: "running", "success", "partial_failure", or "failed"
        """
        if exit_code == 0:
            return "success"
        elif exit_code == EXIT_CODE_PARTIAL_FAILURE:
            return "partial_failure"
        elif exit_code in (1, 2, 4, 5, 6):
            return "failed"
        else:
            # Unknown exit code - determine by metrics
            questions_inserted = overall.get("questions_final_output", 0)
            questions_requested = overall.get("questions_requested", 0)

            if questions_inserted == 0:
                return "failed"
            elif questions_inserted < questions_requested:
                return "partial_failure"
            else:
                return "success"

    def _build_provider_metrics(
        self, generation: Dict[str, Any], api: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Build provider metrics dictionary from generation and API data.

        Args:
            generation: Generation metrics from summary
            api: API metrics from summary

        Returns:
            Dictionary mapping provider names to their metrics
        """
        providers_generated = generation.get("by_provider", {})
        providers_api_calls = api.get("by_provider", {})

        # Combine all providers from both sources
        all_providers = set(providers_generated.keys()) | set(
            providers_api_calls.keys()
        )

        if not all_providers:
            return {}

        provider_metrics: Dict[str, Dict[str, Any]] = {}
        for provider in all_providers:
            provider_metrics[provider] = {
                "generated": providers_generated.get(provider, 0),
                "api_calls": providers_api_calls.get(provider, 0),
                "failures": 0,  # Not tracked per-provider currently
            }

        return provider_metrics

    def report_run(
        self,
        metrics_tracker: MetricsTracker,
        exit_code: int,
        environment: Optional[str] = None,
        triggered_by: Optional[str] = None,
        prompt_version: Optional[str] = None,
        arbiter_config_version: Optional[str] = None,
        min_arbiter_score_threshold: Optional[float] = None,
    ) -> Optional[int]:
        """Report a completed generation run to the backend API.

        This method transforms the metrics summary and sends it to the backend.
        Connection failures are logged but not raised to ensure the pipeline
        continues even if reporting fails.

        Args:
            metrics_tracker: MetricsTracker instance with run data
            exit_code: Exit code from the generation run (0-6)
            environment: Environment name (production, staging, development)
            triggered_by: Trigger source (scheduler, manual, webhook)
            prompt_version: Version of prompts used
            arbiter_config_version: Version of arbiter config used
            min_arbiter_score_threshold: Minimum arbiter score for approval

        Returns:
            Created run ID if successful, None if reporting failed
        """
        try:
            # Get summary from metrics tracker
            summary = metrics_tracker.get_summary()

            # Transform to API payload
            payload = self._transform_metrics_to_payload(
                summary=summary,
                exit_code=exit_code,
                environment=environment,
                triggered_by=triggered_by,
                prompt_version=prompt_version,
                arbiter_config_version=arbiter_config_version,
                min_arbiter_score_threshold=min_arbiter_score_threshold,
            )

            # Send to backend
            url = f"{self.backend_url}/v1/admin/generation-runs"
            logger.info(f"Reporting run to {url}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )

                if response.status_code == HTTP_STATUS_CREATED:
                    data = response.json()
                    run_id = data.get("id")
                    logger.info(f"Run reported successfully with ID: {run_id}")
                    return run_id
                else:
                    logger.error(
                        f"Failed to report run: HTTP {response.status_code} - "
                        f"{response.text}"
                    )
                    return None

        except httpx.ConnectError as e:
            logger.error(f"Connection error when reporting run: {e}")
            return None
        except httpx.TimeoutException as e:
            logger.error(f"Timeout when reporting run: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error when reporting run: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when reporting run: {e}")
            return None

    def report_running(
        self,
        started_at: datetime,
        questions_requested: int,
        environment: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> Optional[int]:
        """Report the start of a generation run (optional).

        This method sends a minimal "running" status report to enable
        detection of stuck/crashed jobs.

        Args:
            started_at: When the run started
            questions_requested: Number of questions requested
            environment: Environment name (production, staging, development)
            triggered_by: Trigger source (scheduler, manual, webhook)

        Returns:
            Created run ID if successful, None if reporting failed
        """
        try:
            payload = {
                "started_at": started_at.isoformat(),
                "status": "running",
                "questions_requested": questions_requested,
                "environment": environment,
                "triggered_by": triggered_by,
            }

            url = f"{self.backend_url}/v1/admin/generation-runs"
            logger.info(f"Reporting run start to {url}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )

                if response.status_code == HTTP_STATUS_CREATED:
                    data = response.json()
                    run_id = data.get("id")
                    logger.info(f"Run start reported with ID: {run_id}")
                    return run_id
                else:
                    logger.error(
                        f"Failed to report run start: HTTP {response.status_code} - "
                        f"{response.text}"
                    )
                    return None

        except httpx.ConnectError as e:
            logger.error(f"Connection error when reporting run start: {e}")
            return None
        except httpx.TimeoutException as e:
            logger.error(f"Timeout when reporting run start: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error when reporting run start: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when reporting run start: {e}")
            return None
