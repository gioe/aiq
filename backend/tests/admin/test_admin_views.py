"""
Unit tests for admin view formatting helpers and extracted constants.

Covers boundary values for _check_difficulty_mismatch and _format_quality_status
to guard against constant drift between views.py and question_analytics.py.
"""

import pytest
from unittest.mock import MagicMock

from app.models.models import DifficultyLevel
from app.admin.views import (
    QuestionAdmin,
    MIN_RESPONSES_FOR_QUALITY_ANALYSIS,
    RELIABLE_RESPONSE_COUNT,
    ACCEPTABLE_DISCRIMINATION,
    EASY_TOO_HARD_THRESHOLD,
    MEDIUM_TOO_HARD_THRESHOLD,
    MEDIUM_TOO_EASY_THRESHOLD,
    HARD_TOO_EASY_THRESHOLD,
)


class TestConstantValues:
    """Verify imported constants match their canonical source values."""

    def test_min_responses_for_quality_analysis_equals_canonical(self):
        from app.core.psychometrics.question_analytics import (
            MIN_RESPONSES_FOR_SUFFICIENT_DATA,
        )

        assert MIN_RESPONSES_FOR_QUALITY_ANALYSIS == MIN_RESPONSES_FOR_SUFFICIENT_DATA

    def test_reliable_response_count_equals_canonical(self):
        from app.core.psychometrics.question_analytics import (
            MIN_RESPONSES_FOR_CALIBRATION,
        )

        assert RELIABLE_RESPONSE_COUNT == MIN_RESPONSES_FOR_CALIBRATION

    def test_acceptable_discrimination_equals_canonical(self):
        from app.core.psychometrics.question_analytics import (
            POOR_DISCRIMINATION_THRESHOLD,
        )

        assert ACCEPTABLE_DISCRIMINATION == POOR_DISCRIMINATION_THRESHOLD


class TestCheckDifficultyMismatch:
    """Boundary tests for _check_difficulty_mismatch."""

    @pytest.mark.parametrize(
        "assigned,p_value,expected_fragment",
        [
            # Easy: flag when p_value < EASY_TOO_HARD_THRESHOLD (0.5)
            (DifficultyLevel.EASY, EASY_TOO_HARD_THRESHOLD - 0.01, "Too hard"),
            (
                DifficultyLevel.EASY,
                EASY_TOO_HARD_THRESHOLD,
                "",
            ),  # at threshold — no mismatch
            (DifficultyLevel.EASY, 0.9, ""),  # clearly easy — no mismatch
            # Medium: flag when p_value < MEDIUM_TOO_HARD_THRESHOLD (0.3)
            (DifficultyLevel.MEDIUM, MEDIUM_TOO_HARD_THRESHOLD - 0.01, "Too hard"),
            (
                DifficultyLevel.MEDIUM,
                MEDIUM_TOO_HARD_THRESHOLD,
                "",
            ),  # at threshold — no mismatch
            # Medium: flag when p_value > MEDIUM_TOO_EASY_THRESHOLD (0.8)
            (DifficultyLevel.MEDIUM, MEDIUM_TOO_EASY_THRESHOLD + 0.01, "Too easy"),
            (
                DifficultyLevel.MEDIUM,
                MEDIUM_TOO_EASY_THRESHOLD,
                "",
            ),  # at threshold — no mismatch
            (DifficultyLevel.MEDIUM, 0.5, ""),  # clearly medium — no mismatch
            # Hard: flag when p_value > HARD_TOO_EASY_THRESHOLD (0.6)
            (DifficultyLevel.HARD, HARD_TOO_EASY_THRESHOLD + 0.01, "Too easy"),
            (
                DifficultyLevel.HARD,
                HARD_TOO_EASY_THRESHOLD,
                "",
            ),  # at threshold — no mismatch
            (DifficultyLevel.HARD, 0.1, ""),  # clearly hard — no mismatch
        ],
    )
    def test_difficulty_mismatch_boundaries(self, assigned, p_value, expected_fragment):
        result = QuestionAdmin._check_difficulty_mismatch(assigned, p_value)
        assert expected_fragment in result


class TestFormatQualityStatus:
    """Boundary tests for _format_quality_status pending/non-pending logic."""

    @pytest.mark.parametrize(
        "response_count,expect_pending",
        [
            (None, True),
            (0, True),
            (MIN_RESPONSES_FOR_QUALITY_ANALYSIS - 1, True),
            (MIN_RESPONSES_FOR_QUALITY_ANALYSIS, False),
            (MIN_RESPONSES_FOR_QUALITY_ANALYSIS + 1, False),
            (RELIABLE_RESPONSE_COUNT, False),
        ],
    )
    def test_pending_threshold(self, response_count, expect_pending):
        model = MagicMock()
        model.response_count = response_count
        model.empirical_difficulty = None
        model.discrimination = None
        result = str(QuestionAdmin._format_quality_status(model))
        assert ("Pending" in result) == expect_pending

    def test_low_discrimination_flagged(self):
        model = MagicMock()
        model.response_count = MIN_RESPONSES_FOR_QUALITY_ANALYSIS
        model.empirical_difficulty = None
        model.discrimination = ACCEPTABLE_DISCRIMINATION - 0.01
        result = str(QuestionAdmin._format_quality_status(model))
        assert "Review Needed" in result

    def test_acceptable_discrimination_not_flagged(self):
        model = MagicMock()
        model.response_count = MIN_RESPONSES_FOR_QUALITY_ANALYSIS
        model.empirical_difficulty = None
        model.discrimination = ACCEPTABLE_DISCRIMINATION
        result = str(QuestionAdmin._format_quality_status(model))
        assert "Good" in result
