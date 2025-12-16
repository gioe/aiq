"""
Tests for reliability schema validators (RE-FI-010).

These tests verify that the Pydantic validators enforce logical consistency
between meets_threshold boolean and the corresponding metric values.
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.reliability import (
    InternalConsistencyMetrics,
    TestRetestMetrics,
    SplitHalfMetrics,
    ReliabilityInterpretation,
)


class TestInternalConsistencyMetricsValidator:
    """Tests for InternalConsistencyMetrics.validate_meets_threshold_consistency."""

    def test_valid_when_alpha_present_and_meets_threshold_true(self):
        """Valid when cronbachs_alpha is present and meets_threshold reflects the value."""
        metrics = InternalConsistencyMetrics(
            cronbachs_alpha=0.85,
            interpretation=ReliabilityInterpretation.GOOD,
            meets_threshold=True,
            num_sessions=150,
            num_items=20,
        )
        assert metrics.cronbachs_alpha == 0.85
        assert metrics.meets_threshold is True

    def test_valid_when_alpha_present_and_meets_threshold_false(self):
        """Valid when cronbachs_alpha is below threshold and meets_threshold is False."""
        metrics = InternalConsistencyMetrics(
            cronbachs_alpha=0.55,
            interpretation=ReliabilityInterpretation.POOR,
            meets_threshold=False,
            num_sessions=150,
            num_items=20,
        )
        assert metrics.cronbachs_alpha == 0.55
        assert metrics.meets_threshold is False

    def test_valid_when_alpha_none_and_meets_threshold_false(self):
        """Valid when cronbachs_alpha is None (insufficient data) and meets_threshold is False."""
        metrics = InternalConsistencyMetrics(
            cronbachs_alpha=None,
            interpretation=None,
            meets_threshold=False,
            num_sessions=50,
            num_items=None,
        )
        assert metrics.cronbachs_alpha is None
        assert metrics.meets_threshold is False

    def test_invalid_when_alpha_none_and_meets_threshold_true(self):
        """Invalid when cronbachs_alpha is None but meets_threshold is True."""
        with pytest.raises(ValidationError) as exc_info:
            InternalConsistencyMetrics(
                cronbachs_alpha=None,
                interpretation=None,
                meets_threshold=True,
                num_sessions=50,
                num_items=None,
            )

        # Verify the error message contains the expected text
        error_messages = str(exc_info.value)
        assert (
            "meets_threshold cannot be True when cronbachs_alpha is None"
            in error_messages
        )

    def test_valid_with_all_optional_fields(self):
        """Valid with all optional fields present."""
        now = datetime.now(timezone.utc)
        metrics = InternalConsistencyMetrics(
            cronbachs_alpha=0.78,
            interpretation=ReliabilityInterpretation.GOOD,
            meets_threshold=True,
            num_sessions=200,
            num_items=25,
            last_calculated=now,
            item_total_correlations={1: 0.45, 2: 0.52, 3: 0.38},
        )
        assert metrics.cronbachs_alpha == 0.78
        assert metrics.item_total_correlations == {1: 0.45, 2: 0.52, 3: 0.38}

    def test_valid_at_boundary_alpha_zero(self):
        """Valid when cronbachs_alpha is exactly 0 (a valid calculated value)."""
        metrics = InternalConsistencyMetrics(
            cronbachs_alpha=0.0,
            interpretation=ReliabilityInterpretation.POOR,
            meets_threshold=False,
            num_sessions=100,
            num_items=10,
        )
        assert metrics.cronbachs_alpha == 0.0
        assert metrics.meets_threshold is False


class TestTestRetestMetricsValidator:
    """Tests for TestRetestMetrics.validate_meets_threshold_consistency."""

    def test_valid_when_correlation_present_and_meets_threshold_true(self):
        """Valid when correlation is present and meets_threshold reflects the value."""
        metrics = TestRetestMetrics(
            correlation=0.75,
            interpretation=ReliabilityInterpretation.GOOD,
            meets_threshold=True,
            num_pairs=50,
            mean_interval_days=45.0,
            practice_effect=2.1,
        )
        assert metrics.correlation == 0.75
        assert metrics.meets_threshold is True

    def test_valid_when_correlation_present_and_meets_threshold_false(self):
        """Valid when correlation is below threshold and meets_threshold is False."""
        metrics = TestRetestMetrics(
            correlation=0.35,
            interpretation=ReliabilityInterpretation.POOR,
            meets_threshold=False,
            num_pairs=50,
            mean_interval_days=45.0,
        )
        assert metrics.correlation == 0.35
        assert metrics.meets_threshold is False

    def test_valid_when_correlation_none_and_meets_threshold_false(self):
        """Valid when correlation is None (insufficient data) and meets_threshold is False."""
        metrics = TestRetestMetrics(
            correlation=None,
            interpretation=None,
            meets_threshold=False,
            num_pairs=15,
        )
        assert metrics.correlation is None
        assert metrics.meets_threshold is False

    def test_invalid_when_correlation_none_and_meets_threshold_true(self):
        """Invalid when correlation is None but meets_threshold is True."""
        with pytest.raises(ValidationError) as exc_info:
            TestRetestMetrics(
                correlation=None,
                interpretation=None,
                meets_threshold=True,
                num_pairs=15,
            )

        # Verify the error message contains the expected text
        error_messages = str(exc_info.value)
        assert (
            "meets_threshold cannot be True when correlation is None" in error_messages
        )

    def test_valid_with_all_optional_fields(self):
        """Valid with all optional fields present."""
        now = datetime.now(timezone.utc)
        metrics = TestRetestMetrics(
            correlation=0.65,
            interpretation=ReliabilityInterpretation.ACCEPTABLE,
            meets_threshold=True,
            num_pairs=100,
            mean_interval_days=60.5,
            practice_effect=1.8,
            last_calculated=now,
        )
        assert metrics.correlation == 0.65
        assert metrics.practice_effect == 1.8

    def test_valid_at_boundary_correlation_zero(self):
        """Valid when correlation is exactly 0 (a valid calculated value)."""
        metrics = TestRetestMetrics(
            correlation=0.0,
            interpretation=ReliabilityInterpretation.POOR,
            meets_threshold=False,
            num_pairs=50,
        )
        assert metrics.correlation == 0.0
        assert metrics.meets_threshold is False

    def test_valid_with_negative_correlation(self):
        """Valid when correlation is negative (unusual but valid)."""
        metrics = TestRetestMetrics(
            correlation=-0.25,
            interpretation=ReliabilityInterpretation.POOR,
            meets_threshold=False,
            num_pairs=50,
        )
        assert metrics.correlation == -0.25
        assert metrics.meets_threshold is False


class TestSplitHalfMetricsValidator:
    """Tests for SplitHalfMetrics.validate_meets_threshold_consistency."""

    def test_valid_when_spearman_brown_present_and_meets_threshold_true(self):
        """Valid when spearman_brown is present and meets_threshold reflects the value."""
        metrics = SplitHalfMetrics(
            raw_correlation=0.70,
            spearman_brown=0.82,
            meets_threshold=True,
            num_sessions=150,
        )
        assert metrics.spearman_brown == 0.82
        assert metrics.meets_threshold is True

    def test_valid_when_spearman_brown_present_and_meets_threshold_false(self):
        """Valid when spearman_brown is below threshold and meets_threshold is False."""
        metrics = SplitHalfMetrics(
            raw_correlation=0.45,
            spearman_brown=0.62,
            meets_threshold=False,
            num_sessions=150,
        )
        assert metrics.spearman_brown == 0.62
        assert metrics.meets_threshold is False

    def test_valid_when_spearman_brown_none_and_meets_threshold_false(self):
        """Valid when spearman_brown is None (insufficient data) and meets_threshold is False."""
        metrics = SplitHalfMetrics(
            raw_correlation=None,
            spearman_brown=None,
            meets_threshold=False,
            num_sessions=50,
        )
        assert metrics.spearman_brown is None
        assert metrics.meets_threshold is False

    def test_invalid_when_spearman_brown_none_and_meets_threshold_true(self):
        """Invalid when spearman_brown is None but meets_threshold is True."""
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=None,
                meets_threshold=True,
                num_sessions=50,
            )

        # Verify the error message contains the expected text
        error_messages = str(exc_info.value)
        assert (
            "meets_threshold cannot be True when spearman_brown is None"
            in error_messages
        )

    def test_valid_with_all_optional_fields(self):
        """Valid with all optional fields present."""
        now = datetime.now(timezone.utc)
        metrics = SplitHalfMetrics(
            raw_correlation=0.68,
            spearman_brown=0.81,
            meets_threshold=True,
            num_sessions=200,
            last_calculated=now,
        )
        assert metrics.raw_correlation == 0.68
        assert metrics.spearman_brown == 0.81

    def test_valid_at_boundary_spearman_brown_zero(self):
        """Valid when spearman_brown is exactly 0 (a valid calculated value)."""
        metrics = SplitHalfMetrics(
            raw_correlation=0.0,
            spearman_brown=0.0,
            meets_threshold=False,
            num_sessions=100,
        )
        assert metrics.spearman_brown == 0.0
        assert metrics.meets_threshold is False

    def test_valid_when_raw_correlation_none_but_spearman_brown_present(self):
        """
        Edge case: raw_correlation could be None while spearman_brown is present
        (unlikely but schema allows it). Validator only checks spearman_brown.
        """
        metrics = SplitHalfMetrics(
            raw_correlation=None,
            spearman_brown=0.75,
            meets_threshold=True,
            num_sessions=100,
        )
        assert metrics.raw_correlation is None
        assert metrics.spearman_brown == 0.75
        assert metrics.meets_threshold is True


class TestValidatorErrorMessages:
    """Tests for validator error message quality."""

    def test_internal_consistency_error_message_is_descriptive(self):
        """Verify InternalConsistencyMetrics provides a helpful error message."""
        with pytest.raises(ValidationError) as exc_info:
            InternalConsistencyMetrics(
                cronbachs_alpha=None,
                meets_threshold=True,
                num_sessions=50,
            )

        error_str = str(exc_info.value)
        # Should mention the problem field
        assert "cronbachs_alpha" in error_str
        # Should explain the issue
        assert "insufficient data" in error_str

    def test_test_retest_error_message_is_descriptive(self):
        """Verify TestRetestMetrics provides a helpful error message."""
        with pytest.raises(ValidationError) as exc_info:
            TestRetestMetrics(
                correlation=None,
                meets_threshold=True,
                num_pairs=20,
            )

        error_str = str(exc_info.value)
        # Should mention the problem field
        assert "correlation" in error_str
        # Should explain the issue
        assert "insufficient data" in error_str

    def test_split_half_error_message_is_descriptive(self):
        """Verify SplitHalfMetrics provides a helpful error message."""
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                spearman_brown=None,
                meets_threshold=True,
                num_sessions=50,
            )

        error_str = str(exc_info.value)
        # Should mention the problem field
        assert "spearman_brown" in error_str
        # Should explain the issue
        assert "insufficient data" in error_str


class TestValidatorIntegrationWithBusinessLogic:
    """
    Tests to verify the validators work correctly with the business logic
    that constructs these schemas from calculated reliability metrics.
    """

    def test_insufficient_data_scenario_creates_valid_schema(self):
        """
        When business logic has insufficient data, it should create valid schemas
        with None values and meets_threshold=False.
        """
        # This mimics what get_reliability_report() does when data is insufficient
        internal = InternalConsistencyMetrics(
            cronbachs_alpha=None,
            interpretation=None,
            meets_threshold=False,
            num_sessions=50,
            num_items=None,
            last_calculated=None,
            item_total_correlations=None,
        )

        test_retest = TestRetestMetrics(
            correlation=None,
            interpretation=None,
            meets_threshold=False,
            num_pairs=10,
            mean_interval_days=None,
            practice_effect=None,
            last_calculated=None,
        )

        split_half = SplitHalfMetrics(
            raw_correlation=None,
            spearman_brown=None,
            meets_threshold=False,
            num_sessions=50,
            last_calculated=None,
        )

        assert internal.cronbachs_alpha is None
        assert internal.meets_threshold is False
        assert test_retest.correlation is None
        assert test_retest.meets_threshold is False
        assert split_half.spearman_brown is None
        assert split_half.meets_threshold is False

    def test_sufficient_data_scenario_creates_valid_schema(self):
        """
        When business logic has sufficient data, it should create valid schemas
        with calculated values and appropriate meets_threshold values.
        """
        now = datetime.now(timezone.utc)

        internal = InternalConsistencyMetrics(
            cronbachs_alpha=0.78,
            interpretation=ReliabilityInterpretation.GOOD,
            meets_threshold=True,
            num_sessions=523,
            num_items=20,
            last_calculated=now,
            item_total_correlations={1: 0.45, 2: 0.52, 3: 0.38},
        )

        test_retest = TestRetestMetrics(
            correlation=0.65,
            interpretation=ReliabilityInterpretation.ACCEPTABLE,
            meets_threshold=True,
            num_pairs=89,
            mean_interval_days=45.3,
            practice_effect=2.1,
            last_calculated=now,
        )

        split_half = SplitHalfMetrics(
            raw_correlation=0.71,
            spearman_brown=0.83,
            meets_threshold=True,
            num_sessions=523,
            last_calculated=now,
        )

        assert internal.cronbachs_alpha == 0.78
        assert internal.meets_threshold is True
        assert test_retest.correlation == 0.65
        assert test_retest.meets_threshold is True
        assert split_half.spearman_brown == 0.83
        assert split_half.meets_threshold is True
