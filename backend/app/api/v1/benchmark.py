"""
Public benchmark summary endpoint.

Returns curated model performance data for authenticated users,
without sensitive fields (costs, tokens, session details).
"""

import logging
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_current_user
from app.core.cache import get_cache
from app.models import User, get_db
from app.models.llm_benchmark import LLMTestResult

logger = logging.getLogger(__name__)

router = APIRouter()

# Default minimum completed runs before a model is included in the summary.
_DEFAULT_MIN_RUNS = 3

# Cache TTL in seconds (10 minutes — benchmark data changes infrequently).
_DEFAULT_CACHE_TTL = 600

_CACHE_KEY = "benchmark_summary"

# ---------------------------------------------------------------------------
# Display name mapping
# ---------------------------------------------------------------------------

_MODEL_DISPLAY_NAMES: dict[str, str] = {
    # Anthropic
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-opus-4-1-20250805": "Claude Opus 4.1",
    "claude-opus-4-20250514": "Claude Opus 4",
    "claude-3-7-sonnet-20250219": "Claude 3.7 Sonnet",
    "claude-3-haiku-20240307": "Claude 3 Haiku",
    # OpenAI
    "gpt-5.2": "GPT-5.2",
    "gpt-5.1": "GPT-5.1",
    "gpt-5": "GPT-5",
    "o4-mini": "o4-mini",
    "o3": "o3",
    "o3-mini": "o3-mini",
    "o1": "o1",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini",
    # Google
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    # xAI
    "grok-4": "Grok 4",
}


def _display_name(model_id: str) -> str:
    """Return a human-friendly display name for a model ID."""
    return _MODEL_DISPLAY_NAMES.get(model_id, model_id)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DomainAccuracySummary(BaseModel):
    """Per-domain accuracy for a single model."""

    domain: str = Field(..., description="Question domain (e.g. 'pattern', 'logic').")
    accuracy_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Accuracy percentage in this domain."
    )
    total_questions: int = Field(
        ..., ge=0, description="Number of questions answered in this domain."
    )


class ModelSummary(BaseModel):
    """Public performance summary for a single model."""

    display_name: str = Field(..., description="Human-friendly model name.")
    vendor: str = Field(..., description="LLM vendor (e.g. 'anthropic', 'openai').")
    mean_iq: float = Field(..., description="Mean IQ score across completed runs.")
    accuracy_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall accuracy percentage across all runs.",
    )
    runs: int = Field(..., ge=1, description="Number of completed benchmark runs.")
    domain_accuracy: list[DomainAccuracySummary] = Field(
        default_factory=list,
        description="Per-domain accuracy breakdown.",
    )


class BenchmarkSummaryResponse(BaseModel):
    """Response for GET /v1/benchmark/summary."""

    models: list[ModelSummary] = Field(
        ...,
        description="Per-model performance summaries, sorted by mean IQ descending.",
    )
    min_runs: int = Field(
        ..., description="Minimum completed runs threshold used for this response."
    )
    cache_ttl: int = Field(..., description="Cache TTL in seconds for this response.")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=BenchmarkSummaryResponse)
async def get_benchmark_summary(
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    min_runs: int = Query(
        default=_DEFAULT_MIN_RUNS,
        ge=1,
        description="Minimum completed benchmark runs to include a model.",
    ),
) -> BenchmarkSummaryResponse:
    """Return curated model performance data for authenticated users."""

    cache = get_cache()
    cache_key = f"{_CACHE_KEY}:min_runs={min_runs}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # --- Per-model aggregation from completed results -----------------------
    model_q = (
        select(
            LLMTestResult.vendor,
            LLMTestResult.model_id,
            func.count(LLMTestResult.id).label("sessions_count"),
            func.sum(LLMTestResult.total_questions).label("total_questions"),
            func.sum(LLMTestResult.correct_answers).label("correct_answers"),
        )
        .where(LLMTestResult.iq_score.isnot(None))
        .group_by(LLMTestResult.vendor, LLMTestResult.model_id)
        .having(func.count(LLMTestResult.id) >= min_runs)
    )
    model_rows = (await db.execute(model_q)).all()

    models: list[ModelSummary] = []
    for row in model_rows:
        # All IQ scores for this model (for mean_iq).
        all_iq_q = select(LLMTestResult.iq_score).where(
            LLMTestResult.vendor == row.vendor,
            LLMTestResult.model_id == row.model_id,
            LLMTestResult.iq_score.isnot(None),
        )
        model_iq_scores = [
            float(s)
            for s in (await db.execute(all_iq_q)).scalars().all()
            if s is not None
        ]
        mean_iq = round(statistics.mean(model_iq_scores), 2) if model_iq_scores else 0.0

        # Overall accuracy.
        total_q = int(row.total_questions) if row.total_questions else 0
        correct = int(row.correct_answers) if row.correct_answers else 0
        accuracy_pct = round(correct / total_q * 100, 2) if total_q > 0 else 0.0

        # Per-model domain scores.
        domain_q = select(LLMTestResult.domain_scores).where(
            LLMTestResult.vendor == row.vendor,
            LLMTestResult.model_id == row.model_id,
            LLMTestResult.domain_scores.isnot(None),
        )
        domain_rows = (await db.execute(domain_q)).scalars().all()

        domain_correct: dict[str, int] = defaultdict(int)
        domain_total: dict[str, int] = defaultdict(int)
        for ds in domain_rows:
            if not isinstance(ds, dict):
                continue
            for domain, stats in ds.items():
                if isinstance(stats, dict):
                    domain_correct[domain] += stats.get("correct", 0)
                    domain_total[domain] += stats.get("total", 0)

        domain_accuracy = sorted(
            [
                DomainAccuracySummary(
                    domain=domain,
                    accuracy_pct=round(
                        domain_correct[domain] / domain_total[domain] * 100, 2
                    ),
                    total_questions=domain_total[domain],
                )
                for domain in domain_total
                if domain_total[domain] > 0
            ],
            key=lambda d: d.domain,
        )

        models.append(
            ModelSummary(
                display_name=_display_name(row.model_id),
                vendor=row.vendor,
                mean_iq=mean_iq,
                accuracy_pct=accuracy_pct,
                runs=row.sessions_count,
                domain_accuracy=domain_accuracy,
            )
        )

    # Sort by mean IQ descending.
    models.sort(key=lambda m: m.mean_iq, reverse=True)

    response = BenchmarkSummaryResponse(
        models=models,
        min_runs=min_runs,
        cache_ttl=_DEFAULT_CACHE_TTL,
    )

    cache.set(cache_key, response, ttl=_DEFAULT_CACHE_TTL)
    return response
