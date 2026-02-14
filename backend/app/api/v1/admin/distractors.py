"""
Distractor analysis admin endpoints.

Endpoints for analyzing the effectiveness of answer options (distractors)
in multiple-choice questions.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.psychometrics.distractor_analysis import (
    async_analyze_distractor_effectiveness,
    async_get_bulk_distractor_summary,
)
from app.models import Question, get_db
from app.schemas.distractor_analysis import (
    DistractorAnalysisResponse,
    DistractorDiscrimination,
    DistractorOptionAnalysis,
    DistractorStatus,
    DistractorSummary,
    DistractorSummaryResponse,
    NonFunctioningCountBreakdown,
    WorstOffenderQuestion,
)

from ._dependencies import verify_admin_token

router = APIRouter()


@router.get(
    "/questions/{question_id}/distractor-analysis",
    response_model=DistractorAnalysisResponse,
    responses={
        404: {"description": "Question not found"},
        400: {"description": "Question is not a multiple-choice question"},
    },
)
async def get_distractor_analysis(
    question_id: int,
    min_responses: int = Query(
        50,
        ge=1,
        le=1000,
        description="Minimum responses required for analysis",
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get detailed distractor analysis for a single question.

    Analyzes the effectiveness of each answer option (distractor) for a
    multiple-choice question. This helps identify non-functioning distractors
    (rarely selected) and inverted distractors (high scorers prefer them).

    Requires X-Admin-Token header with valid admin token.

    **Status Classifications:**
    - Functioning: Selected by >=5% of respondents (good distractor)
    - Weak: Selected by 2-5% of respondents (marginal)
    - Non-functioning: Selected by <2% of respondents (not attracting anyone)

    **Discrimination Classifications:**
    - Good: Bottom quartile selects more than top (positive index > 0.10)
    - Neutral: Similar selection rates across ability levels (|index| <= 0.10)
    - Inverted: Top quartile selects more than bottom (index < -0.10)
      This is problematic as it suggests high-ability test-takers are attracted
      to the "wrong" answer.

    **Effective Option Count:**
    Calculated using the inverse Simpson index. A value of 4.0 for a 4-option
    question means all options are selected equally. A value of 1.0 means
    essentially only one option is ever selected.

    Args:
        question_id: The unique identifier of the question to analyze
        min_responses: Minimum number of responses required for analysis (default: 50)
        db: Database session
        _: Admin token validation dependency

    Returns:
        DistractorAnalysisResponse with detailed analysis for each option

    Raises:
        HTTPException 404: If the question is not found
        HTTPException 400: If the question is not a multiple-choice question

    Example:
        ```
        curl "https://api.example.com/v1/admin/questions/123/distractor-analysis?min_responses=50" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # First check if question exists
        result = await db.execute(select(Question).where(Question.id == question_id))
        question = result.scalar_one_or_none()

        if question is None:
            raise HTTPException(
                status_code=404,
                detail=f"Question with ID {question_id} not found",
            )

        # Check if question has answer options (is multiple-choice)
        if question.answer_options is None:
            raise HTTPException(
                status_code=400,
                detail=f"Question {question_id} is not a multiple-choice question "
                "(no answer_options available)",
            )

        # Get distractor analysis from core function
        analysis = await async_analyze_distractor_effectiveness(
            db, question_id, min_responses=min_responses
        )

        # Handle insufficient data case
        if analysis.get("insufficient_data"):
            # Return a valid response but with minimal data
            return DistractorAnalysisResponse(
                question_id=question_id,
                question_text=str(question.question_text),
                total_responses=analysis.get("total_responses", 0),
                correct_answer=str(question.correct_answer)
                if question.correct_answer
                else None,
                options=[],
                summary=DistractorSummary(
                    functioning_distractors=0,
                    weak_distractors=0,
                    non_functioning_distractors=0,
                    inverted_distractors=0,
                    effective_option_count=0.0,
                    guessing_probability=0.0,
                ),
                recommendations=[
                    f"Insufficient data for analysis. "
                    f"Have {analysis.get('total_responses', 0)} responses, "
                    f"need at least {analysis.get('min_required', min_responses)}."
                ],
            )

        # Build options analysis list
        options_list = []
        for option_key, option_data in analysis["options"].items():
            options_list.append(
                DistractorOptionAnalysis(
                    option_key=option_key,
                    is_correct=option_data["is_correct"],
                    selection_rate=option_data["selection_rate"],
                    status=DistractorStatus(option_data["status"]),
                    discrimination=DistractorDiscrimination(
                        option_data["discrimination"]
                    ),
                    discrimination_index=option_data["discrimination_index"],
                    top_quartile_rate=option_data["top_quartile_rate"],
                    bottom_quartile_rate=option_data["bottom_quartile_rate"],
                )
            )

        # Sort options by key for consistent ordering
        options_list.sort(key=lambda x: x.option_key)

        # Calculate guessing probability from effective option count
        effective_options = analysis["summary"]["effective_option_count"]
        guessing_prob = (1.0 / effective_options) if effective_options > 0 else 0.0

        summary = DistractorSummary(
            functioning_distractors=analysis["summary"]["functioning_distractors"],
            weak_distractors=analysis["summary"]["weak_distractors"],
            non_functioning_distractors=analysis["summary"][
                "non_functioning_distractors"
            ],
            inverted_distractors=analysis["summary"]["inverted_distractors"],
            effective_option_count=analysis["summary"]["effective_option_count"],
            guessing_probability=round(guessing_prob, 4),
        )

        return DistractorAnalysisResponse(
            question_id=question_id,
            question_text=str(question.question_text),
            total_responses=analysis["total_responses"],
            correct_answer=analysis.get("correct_answer"),
            options=options_list,
            summary=summary,
            recommendations=analysis.get("recommendations", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve distractor analysis: {str(e)}",
        )


@router.get(
    "/questions/distractor-summary",
    response_model=DistractorSummaryResponse,
)
async def get_distractor_summary(
    min_responses: int = Query(
        50,
        ge=1,
        le=1000,
        description="Minimum responses required for analysis",
    ),
    question_type: Optional[str] = Query(
        None,
        description="Filter by question type (pattern, logic, spatial, math, verbal, memory)",
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get aggregate distractor analysis statistics across all questions.

    Provides a summary of distractor effectiveness across all multiple-choice
    questions with sufficient response data. This helps identify systemic
    issues with question quality and prioritize question improvements.

    Requires X-Admin-Token header with valid admin token.

    **Summary Statistics:**
    - Total questions analyzed (meeting minimum response threshold)
    - Questions with non-functioning distractors (selected by <2%)
    - Questions with inverted distractors (high scorers prefer wrong answers)

    **Breakdown by Non-Functioning Count:**
    - How many questions have 0, 1, 2, or 3+ non-functioning distractors

    **Worst Offenders:**
    - Top 10 questions with the most distractor issues, sorted by severity
    - Severity is calculated as: (non_functioning * 2) + inverted

    **By Question Type:**
    - Stats grouped by question type (pattern, logic, spatial, etc.)
    - Helps identify if certain question types have more distractor issues

    Args:
        min_responses: Minimum number of responses required for analysis (default: 50)
        question_type: Optional filter by question type
        db: Database session
        _: Admin token validation dependency

    Returns:
        DistractorSummaryResponse with aggregate statistics

    Example:
        ```
        # Get summary for all questions
        curl "https://api.example.com/v1/admin/questions/distractor-summary" \
          -H "X-Admin-Token: your-admin-token"

        # Filter by question type
        curl "https://api.example.com/v1/admin/questions/distractor-summary?question_type=pattern" \
          -H "X-Admin-Token: your-admin-token"

        # Increase minimum response threshold
        curl "https://api.example.com/v1/admin/questions/distractor-summary?min_responses=100" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Get bulk summary from core function
        summary = await async_get_bulk_distractor_summary(
            db, min_responses=min_responses, question_type=question_type
        )

        # Calculate rates
        total = summary["total_questions_analyzed"]
        non_functioning_rate = (
            round(summary["questions_with_non_functioning_distractors"] / total, 4)
            if total > 0
            else 0.0
        )
        inverted_rate = (
            round(summary["questions_with_inverted_distractors"] / total, 4)
            if total > 0
            else 0.0
        )

        # Convert worst offenders to schema objects
        worst_offenders = [
            WorstOffenderQuestion(
                question_id=q["question_id"],
                question_type=q["question_type"],
                difficulty_level=q["difficulty_level"],
                non_functioning_count=q["non_functioning_count"],
                inverted_count=q["inverted_count"],
                total_responses=q["total_responses"],
                effective_option_count=q["effective_option_count"],
            )
            for q in summary["worst_offenders"]
        ]

        # Build breakdown model
        by_nf_count = NonFunctioningCountBreakdown(
            zero=summary["by_non_functioning_count"]["zero"],
            one=summary["by_non_functioning_count"]["one"],
            two=summary["by_non_functioning_count"]["two"],
            three_or_more=summary["by_non_functioning_count"]["three_or_more"],
        )

        return DistractorSummaryResponse(
            total_questions_analyzed=summary["total_questions_analyzed"],
            questions_with_non_functioning_distractors=summary[
                "questions_with_non_functioning_distractors"
            ],
            questions_with_inverted_distractors=summary[
                "questions_with_inverted_distractors"
            ],
            non_functioning_rate=non_functioning_rate,
            inverted_rate=inverted_rate,
            by_non_functioning_count=by_nf_count,
            worst_offenders=worst_offenders,
            by_question_type=summary["by_question_type"],
            avg_effective_option_count=summary["avg_effective_option_count"],
            questions_below_threshold=summary["questions_below_threshold"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve distractor summary: {str(e)}",
        )
