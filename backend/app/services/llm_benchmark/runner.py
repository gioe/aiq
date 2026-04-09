"""
LLM benchmark test runner.

Orchestrates a full benchmark run: question selection, provider dispatch,
answer scoring, cost tracking, and persistence.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.core.scoring.engine import (
    calculate_iq_score,
    iq_to_percentile,
    calculate_domain_scores,
)
from app.core.scoring.test_composition import async_select_stratified_questions
from app.models.llm_benchmark import (
    LLMTestSession,
    LLMResponse as LLMResponseRecord,
    LLMTestResult,
)
from app.services.llm_benchmark.providers import (
    LLMResponse as ProviderResponse,
    complete_openai,
    complete_anthropic,
    complete_google,
)
from app.services.llm_benchmark.prompts import build_prompt

logger = logging.getLogger(__name__)

# Matches leading option prefixes like "A.", "a.", "A)", "a)", "1.", "1)"
_OPTION_PREFIX_RE = re.compile(r"^[a-zA-Z0-9][.)]\s*")

_PROVIDER_DISPATCH: dict[str, Callable[..., Awaitable[ProviderResponse]]] = {
    "openai": complete_openai,
    "anthropic": complete_anthropic,
    "google": complete_google,
}

# Approximate cost per 1M tokens (USD) for default models.
# Used for cost-cap enforcement only — not billing-grade.
_COST_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    # (input_cost, output_cost) per 1M tokens
    # Prices from question-service/config/models.yaml
    "openai": (5.00, 15.00),  # gpt-5.2
    "anthropic": (3.00, 15.00),  # claude-sonnet-4.5
    "google": (1.25, 10.00),  # gemini-3.1-pro-preview
}


def _estimate_cost(vendor: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from token counts using approximate pricing."""
    rates = _COST_PER_M_TOKENS.get(vendor, (1.0, 3.0))
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000


def _normalize_answer(raw: str) -> str:
    """Strip whitespace, lowercase, and remove leading option prefixes."""
    text = raw.strip().lower()
    text = _OPTION_PREFIX_RE.sub("", text)
    return text.strip()


def _parse_answer_from_response(raw_text: str) -> str:
    """Extract the answer value from a JSON response string.

    Returns an empty string if parsing fails.
    """
    try:
        data = json.loads(raw_text)
        return str(data.get("answer", ""))
    except (json.JSONDecodeError, AttributeError):
        # Some providers may return the answer wrapped in markdown fences
        stripped = re.sub(r"^```\w*\n?", "", raw_text.strip())
        stripped = re.sub(r"\n?```$", "", stripped).strip()
        try:
            data = json.loads(stripped)
            return str(data.get("answer", ""))
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Could not parse JSON from LLM response: %.200s", raw_text)
            return ""


async def run_llm_benchmark(
    db: AsyncSession,
    vendor: str,
    model_id: str,
    *,
    total_questions: int | None = None,
    triggered_by: str = "manual",
) -> int:
    """Run a full LLM benchmark session against a stratified question set.

    Creates an LLMTestSession, iterates through selected questions, calls the
    appropriate LLM provider, scores each answer, persists LLMResponse records,
    and finally writes an LLMTestResult with aggregate scores.

    Args:
        db: Async database session.
        vendor: Provider name — one of "openai", "anthropic", "google".
        model_id: Model identifier passed through to the provider function.
        total_questions: Override for the number of questions to select.
            Defaults to settings.TEST_TOTAL_QUESTIONS.
        triggered_by: Free-form label describing what initiated this run
            (e.g. "manual", "cron", "ci").

    Returns:
        The integer primary key of the created LLMTestSession.

    Raises:
        ValueError: If the vendor is not recognised.
    """
    provider_fn = _PROVIDER_DISPATCH.get(vendor)
    if provider_fn is None:
        raise ValueError(
            f"Unknown vendor {vendor!r}. Must be one of: "
            + ", ".join(_PROVIDER_DISPATCH)
        )

    n_questions = (
        total_questions
        if total_questions is not None
        else settings.TEST_TOTAL_QUESTIONS
    )

    # --- 1. Create session record -----------------------------------------
    session_record = LLMTestSession(
        vendor=vendor,
        model_id=model_id,
        status="in_progress",
        triggered_by=triggered_by,
    )
    db.add(session_record)
    await db.flush()  # obtain session_record.id without committing
    session_id: int = session_record.id
    logger.info(
        "LLM benchmark session %d started: vendor=%s model=%s questions=%d",
        session_id,
        vendor,
        model_id,
        n_questions,
    )

    # --- 2. Select questions -------------------------------------------------
    questions, composition_metadata = await async_select_stratified_questions(
        db,
        user_id=0,
        total_count=n_questions,
        skip_seen_filter=True,
    )
    session_record.composition_metadata = composition_metadata

    questions_dict = {q.id: q for q in questions}

    # --- 3. Iterate questions -------------------------------------------------
    total_prompt_tokens = 0
    total_completion_tokens = 0
    cumulative_cost: float = 0.0
    correct_count = 0
    llm_responses: list[LLMResponseRecord] = []
    final_status = "completed"

    for question in questions:
        # Cost cap check before each call
        if cumulative_cost > settings.LLM_BENCHMARK_COST_CAP_USD:
            logger.warning(
                "Session %d: cost cap $%.4f exceeded after $%.4f. Aborting.",
                session_id,
                settings.LLM_BENCHMARK_COST_CAP_USD,
                cumulative_cost,
            )
            final_status = "cost_cap_exceeded"
            break

        prompt = build_prompt(question)
        t_start = time.monotonic()

        try:
            provider_result: ProviderResponse = await provider_fn(
                prompt, model=model_id
            )
        except Exception:
            logger.exception(
                "Session %d question %d: unhandled provider exception",
                session_id,
                question.id,
            )
            provider_result = ProviderResponse(
                answer="",
                input_tokens=0,
                output_tokens=0,
                model=model_id,
                error="Unhandled provider exception",
            )

        latency_ms = int((time.monotonic() - t_start) * 1000)

        # --- 4. Parse and normalise answer -----------------------------------
        raw_answer = provider_result.answer
        if provider_result.ok:
            extracted = _parse_answer_from_response(raw_answer)
        else:
            extracted = ""
            logger.warning(
                "Session %d question %d: provider error: %s",
                session_id,
                question.id,
                provider_result.error,
            )

        normalized = _normalize_answer(extracted)
        correct_normalized = _normalize_answer(question.correct_answer)
        is_correct = normalized == correct_normalized and normalized != ""

        # --- 5. Cost tracking ------------------------------------------------
        total_prompt_tokens += provider_result.input_tokens
        total_completion_tokens += provider_result.output_tokens
        estimated_cost = _estimate_cost(
            vendor, provider_result.input_tokens, provider_result.output_tokens
        )
        cumulative_cost += estimated_cost

        if is_correct:
            correct_count += 1

        # --- 6. Persist LLMResponse ------------------------------------------
        response_record = LLMResponseRecord(
            session_id=session_id,
            question_id=question.id,
            raw_answer=raw_answer if raw_answer else None,
            normalized_answer=normalized if normalized else None,
            is_correct=is_correct,
            prompt_tokens=provider_result.input_tokens,
            completion_tokens=provider_result.output_tokens,
            cost_usd=estimated_cost,
            latency_ms=latency_ms,
            error=provider_result.error,
        )
        db.add(response_record)
        llm_responses.append(response_record)

    await db.flush()

    # --- 7. Aggregate scores -------------------------------------------------
    answered_count = len(llm_responses)
    score = (
        calculate_iq_score(correct_count, answered_count)
        if answered_count > 0
        else None
    )
    percentile = iq_to_percentile(score.iq_score) if score is not None else None

    domain_scores = calculate_domain_scores(llm_responses, questions_dict)  # type: ignore[arg-type]

    # --- 8. Create LLMTestResult ---------------------------------------------
    result_record = LLMTestResult(
        session_id=session_id,
        vendor=vendor,
        model_id=model_id,
        iq_score=score.iq_score if score is not None else None,
        percentile_rank=percentile,
        total_questions=answered_count,
        correct_answers=correct_count,
        domain_scores=domain_scores,
    )
    db.add(result_record)

    # --- 9. Update session ---------------------------------------------------
    session_record.status = final_status
    session_record.completed_at = utc_now()
    session_record.total_prompt_tokens = total_prompt_tokens
    session_record.total_completion_tokens = total_completion_tokens
    session_record.total_cost_usd = cumulative_cost if cumulative_cost > 0 else None

    await db.commit()

    logger.info(
        "Session %d %s: %d/%d correct, IQ=%s, percentile=%s",
        session_id,
        final_status,
        correct_count,
        answered_count,
        score.iq_score if score else "N/A",
        f"{percentile:.1f}" if percentile is not None else "N/A",
    )

    return session_id
