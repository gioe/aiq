"""
Tests for reliability schema validators (RE-FI-010, RE-FI-026, RE-FI-027).

These tests verify that the Pydantic validators enforce logical consistency
between meets_threshold boolean and the corresponding metric values, as well
as mathematical constraints between related fields.

=============================================================================
WHAT THE VALIDATORS PREVENT
=============================================================================

The reliability schema validators guard against three categories of invalid states:

1. INSUFFICIENT DATA CLAIMS SUCCESS (RE-FI-010)
   -------------------------------------------------
   Without validation: An API response could claim "meets_threshold=True" even
   when there's no actual data to support it. This is misleading and dangerous
   for consumers who might act on the assumption that reliability has been verified.

   INVALID - Claims threshold met with no data:
       InternalConsistencyMetrics(
           cronbachs_alpha=None,     # No data!
           meets_threshold=True,     # But claims success? BUG!
           num_sessions=50,
       )
       # Validator raises: "meets_threshold cannot be True when
       #                    cronbachs_alpha is None (insufficient data)"

   VALID - Honestly reports insufficient data:
       InternalConsistencyMetrics(
           cronbachs_alpha=None,
           meets_threshold=False,    # Correctly indicates not met
           num_sessions=50,
       )

2. INCONSISTENT THRESHOLD REPORTING (RE-FI-026)
   -------------------------------------------------
   Without validation: The meets_threshold boolean could contradict the actual
   metric value. A reliability coefficient of 0.85 (excellent) might be reported
   as "fails threshold" or vice versa, causing incorrect dashboard displays
   and potentially leading to misguided item removals or quality decisions.

   INVALID - Good reliability reported as failing:
       InternalConsistencyMetrics(
           cronbachs_alpha=0.85,     # Excellent! >= 0.70 threshold
           meets_threshold=False,    # But says it failed? BUG!
           num_sessions=150,
           num_items=20,
       )
       # Validator raises: "meets_threshold must be True when
       #                    cronbachs_alpha (0.85) >= threshold (0.70)"

   INVALID - Poor reliability reported as passing:
       TestRetestMetrics(
           correlation=0.35,         # Poor! < 0.50 threshold
           meets_threshold=True,     # But says it passed? BUG!
           num_pairs=50,
       )
       # Validator raises: "meets_threshold must be False when
       #                    correlation (0.35) < threshold (0.50)"

   VALID - Threshold status matches the data:
       InternalConsistencyMetrics(
           cronbachs_alpha=0.85,
           meets_threshold=True,     # Correctly reports success
           num_sessions=150,
           num_items=20,
       )

3. MATHEMATICALLY IMPOSSIBLE STATE (RE-FI-027)
   -------------------------------------------------
   Without validation: The Spearman-Brown corrected reliability could exist
   without the raw correlation it's derived from. This violates the fundamental
   formula: r_sb = 2r / (1+r). You cannot have the output without the input.

   INVALID - Derived value without source:
       SplitHalfMetrics(
           raw_correlation=None,     # No input to the formula!
           spearman_brown=0.82,      # But correction exists? BUG!
           meets_threshold=True,
           num_sessions=150,
       )
       # Validator raises: "spearman_brown cannot be present when
       #                    raw_correlation is None. The Spearman-Brown
       #                    correction requires a raw correlation value."

   VALID - Both present (normal calculation):
       SplitHalfMetrics(
           raw_correlation=0.70,     # Input to formula
           spearman_brown=0.82,      # Output: 2*0.70 / (1+0.70) = 0.82
           meets_threshold=True,
           num_sessions=150,
       )

   VALID - Both absent (insufficient data):
       SplitHalfMetrics(
           raw_correlation=None,
           spearman_brown=None,
           meets_threshold=False,
           num_sessions=50,
       )

=============================================================================
THRESHOLD VALUES
=============================================================================

The validators use these threshold constants for bidirectional validation:
- ALPHA_THRESHOLD = 0.70     (Cronbach's alpha minimum for internal consistency)
- TEST_RETEST_THRESHOLD = 0.50  (Test-retest correlation minimum for stability)
- SPLIT_HALF_THRESHOLD = 0.70   (Spearman-Brown minimum for split-half reliability)

Boundary behavior: The thresholds use >= comparison, meaning exactly 0.70
meets the threshold (for alpha and split-half) and exactly 0.50 meets the
threshold (for test-retest).

=============================================================================
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.reliability import (
    InternalConsistencyMetrics,
    TestRetestMetrics,
    SplitHalfMetrics,
    ReliabilityInterpretation,
    ALPHA_THRESHOLD,
    TEST_RETEST_THRESHOLD,
    SPLIT_HALF_THRESHOLD,
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

    def test_invalid_when_raw_correlation_none_but_spearman_brown_present(self):
        """
        Invalid: spearman_brown cannot be present when raw_correlation is None.

        The Spearman-Brown correction formula mathematically requires a raw
        correlation value. If raw_correlation is None (insufficient data),
        spearman_brown must also be None.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=0.75,
                meets_threshold=True,
                num_sessions=100,
            )

        error_messages = str(exc_info.value)
        assert (
            "spearman_brown cannot be present when raw_correlation is None"
            in error_messages
        )
        assert (
            "Spearman-Brown correction requires a raw correlation value"
            in error_messages
        )


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


# =============================================================================
# Bidirectional Validation Tests (RE-FI-026)
# =============================================================================


class TestInternalConsistencyBidirectionalValidation:
    """
    Tests for bidirectional validation of InternalConsistencyMetrics.

    Verifies that meets_threshold must match the actual threshold comparison:
    - cronbachs_alpha >= 0.70 → meets_threshold must be True
    - cronbachs_alpha < 0.70 → meets_threshold must be False
    """

    def test_invalid_when_alpha_meets_threshold_but_meets_threshold_false(self):
        """
        When cronbachs_alpha >= 0.70 (meets threshold), meets_threshold
        cannot be False - it must accurately reflect the threshold status.
        """
        with pytest.raises(ValidationError) as exc_info:
            InternalConsistencyMetrics(
                cronbachs_alpha=0.85,  # Above threshold
                interpretation=ReliabilityInterpretation.GOOD,
                meets_threshold=False,  # Incorrect - should be True
                num_sessions=150,
                num_items=20,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be True" in error_messages
        assert "0.85" in error_messages or "0.850" in error_messages
        assert str(ALPHA_THRESHOLD) in error_messages

    def test_invalid_when_alpha_below_threshold_but_meets_threshold_true(self):
        """
        When cronbachs_alpha < 0.70 (below threshold), meets_threshold
        cannot be True - it must accurately reflect the threshold status.
        """
        with pytest.raises(ValidationError) as exc_info:
            InternalConsistencyMetrics(
                cronbachs_alpha=0.55,  # Below threshold
                interpretation=ReliabilityInterpretation.POOR,
                meets_threshold=True,  # Incorrect - should be False
                num_sessions=150,
                num_items=20,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be False" in error_messages
        assert "0.55" in error_messages or "0.550" in error_messages
        assert str(ALPHA_THRESHOLD) in error_messages

    def test_valid_at_exact_threshold_boundary(self):
        """
        When cronbachs_alpha is exactly at the threshold (0.70),
        meets_threshold should be True (>= comparison).
        """
        metrics = InternalConsistencyMetrics(
            cronbachs_alpha=ALPHA_THRESHOLD,  # Exactly 0.70
            interpretation=ReliabilityInterpretation.ACCEPTABLE,
            meets_threshold=True,
            num_sessions=150,
            num_items=20,
        )
        assert metrics.cronbachs_alpha == ALPHA_THRESHOLD
        assert metrics.meets_threshold is True

    def test_invalid_at_exact_threshold_boundary_with_wrong_flag(self):
        """
        When cronbachs_alpha is exactly at the threshold (0.70),
        meets_threshold=False should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            InternalConsistencyMetrics(
                cronbachs_alpha=ALPHA_THRESHOLD,  # Exactly 0.70
                interpretation=ReliabilityInterpretation.ACCEPTABLE,
                meets_threshold=False,  # Incorrect - boundary is inclusive
                num_sessions=150,
                num_items=20,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be True" in error_messages

    def test_valid_just_below_threshold(self):
        """
        When cronbachs_alpha is just below threshold (0.699),
        meets_threshold should be False.
        """
        metrics = InternalConsistencyMetrics(
            cronbachs_alpha=0.699,  # Just below 0.70
            interpretation=ReliabilityInterpretation.QUESTIONABLE,
            meets_threshold=False,
            num_sessions=150,
            num_items=20,
        )
        assert metrics.cronbachs_alpha == 0.699
        assert metrics.meets_threshold is False


class TestTestRetestBidirectionalValidation:
    """
    Tests for bidirectional validation of TestRetestMetrics.

    Verifies that meets_threshold must match the actual threshold comparison:
    - correlation >= 0.50 → meets_threshold must be True
    - correlation < 0.50 → meets_threshold must be False
    """

    def test_invalid_when_correlation_meets_threshold_but_meets_threshold_false(self):
        """
        When correlation >= 0.50 (meets threshold), meets_threshold
        cannot be False.
        """
        with pytest.raises(ValidationError) as exc_info:
            TestRetestMetrics(
                correlation=0.75,  # Above threshold
                interpretation=ReliabilityInterpretation.GOOD,
                meets_threshold=False,  # Incorrect - should be True
                num_pairs=50,
                mean_interval_days=45.0,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be True" in error_messages
        assert "0.75" in error_messages or "0.750" in error_messages

    def test_invalid_when_correlation_below_threshold_but_meets_threshold_true(self):
        """
        When correlation < 0.50 (below threshold), meets_threshold
        cannot be True.
        """
        with pytest.raises(ValidationError) as exc_info:
            TestRetestMetrics(
                correlation=0.35,  # Below threshold
                interpretation=ReliabilityInterpretation.POOR,
                meets_threshold=True,  # Incorrect - should be False
                num_pairs=50,
                mean_interval_days=45.0,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be False" in error_messages
        assert "0.35" in error_messages or "0.350" in error_messages

    def test_valid_at_exact_threshold_boundary(self):
        """
        When correlation is exactly at the threshold (0.50),
        meets_threshold should be True (>= comparison).
        """
        metrics = TestRetestMetrics(
            correlation=TEST_RETEST_THRESHOLD,  # Exactly 0.50
            interpretation=ReliabilityInterpretation.POOR,
            meets_threshold=True,
            num_pairs=50,
            mean_interval_days=45.0,
        )
        assert metrics.correlation == TEST_RETEST_THRESHOLD
        assert metrics.meets_threshold is True

    def test_invalid_at_exact_threshold_boundary_with_wrong_flag(self):
        """
        When correlation is exactly at the threshold (0.50),
        meets_threshold=False should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            TestRetestMetrics(
                correlation=TEST_RETEST_THRESHOLD,  # Exactly 0.50
                interpretation=ReliabilityInterpretation.POOR,
                meets_threshold=False,  # Incorrect - boundary is inclusive
                num_pairs=50,
                mean_interval_days=45.0,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be True" in error_messages

    def test_valid_just_below_threshold(self):
        """
        When correlation is just below threshold (0.499),
        meets_threshold should be False.
        """
        metrics = TestRetestMetrics(
            correlation=0.499,  # Just below 0.50
            interpretation=ReliabilityInterpretation.UNACCEPTABLE,
            meets_threshold=False,
            num_pairs=50,
            mean_interval_days=45.0,
        )
        assert metrics.correlation == 0.499
        assert metrics.meets_threshold is False

    def test_valid_with_negative_correlation_below_threshold(self):
        """
        Negative correlations are below threshold, so meets_threshold should be False.
        """
        metrics = TestRetestMetrics(
            correlation=-0.25,  # Negative, well below 0.50
            interpretation=ReliabilityInterpretation.UNACCEPTABLE,
            meets_threshold=False,
            num_pairs=50,
        )
        assert metrics.correlation == -0.25
        assert metrics.meets_threshold is False

    def test_invalid_negative_correlation_with_meets_threshold_true(self):
        """
        Negative correlations cannot have meets_threshold=True.
        """
        with pytest.raises(ValidationError) as exc_info:
            TestRetestMetrics(
                correlation=-0.25,  # Negative, well below 0.50
                interpretation=ReliabilityInterpretation.UNACCEPTABLE,
                meets_threshold=True,  # Incorrect
                num_pairs=50,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be False" in error_messages


class TestSplitHalfBidirectionalValidation:
    """
    Tests for bidirectional validation of SplitHalfMetrics.

    Verifies that meets_threshold must match the actual threshold comparison:
    - spearman_brown >= 0.70 → meets_threshold must be True
    - spearman_brown < 0.70 → meets_threshold must be False
    """

    def test_invalid_when_spearman_brown_meets_threshold_but_meets_threshold_false(
        self,
    ):
        """
        When spearman_brown >= 0.70 (meets threshold), meets_threshold
        cannot be False.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=0.70,
                spearman_brown=0.82,  # Above threshold
                meets_threshold=False,  # Incorrect - should be True
                num_sessions=150,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be True" in error_messages
        assert "0.82" in error_messages or "0.820" in error_messages

    def test_invalid_when_spearman_brown_below_threshold_but_meets_threshold_true(self):
        """
        When spearman_brown < 0.70 (below threshold), meets_threshold
        cannot be True.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=0.45,
                spearman_brown=0.62,  # Below threshold
                meets_threshold=True,  # Incorrect - should be False
                num_sessions=150,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be False" in error_messages
        assert "0.62" in error_messages or "0.620" in error_messages

    def test_valid_at_exact_threshold_boundary(self):
        """
        When spearman_brown is exactly at the threshold (0.70),
        meets_threshold should be True (>= comparison).
        """
        metrics = SplitHalfMetrics(
            raw_correlation=0.538,  # Raw correlation that produces SB = 0.70
            spearman_brown=SPLIT_HALF_THRESHOLD,  # Exactly 0.70
            meets_threshold=True,
            num_sessions=150,
        )
        assert metrics.spearman_brown == SPLIT_HALF_THRESHOLD
        assert metrics.meets_threshold is True

    def test_invalid_at_exact_threshold_boundary_with_wrong_flag(self):
        """
        When spearman_brown is exactly at the threshold (0.70),
        meets_threshold=False should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=0.538,
                spearman_brown=SPLIT_HALF_THRESHOLD,  # Exactly 0.70
                meets_threshold=False,  # Incorrect - boundary is inclusive
                num_sessions=150,
            )

        error_messages = str(exc_info.value)
        assert "meets_threshold must be True" in error_messages

    def test_valid_just_below_threshold(self):
        """
        When spearman_brown is just below threshold (0.699),
        meets_threshold should be False.
        """
        metrics = SplitHalfMetrics(
            raw_correlation=0.537,
            spearman_brown=0.699,  # Just below 0.70
            meets_threshold=False,
            num_sessions=150,
        )
        assert metrics.spearman_brown == 0.699
        assert metrics.meets_threshold is False

    def test_invalid_when_raw_correlation_none_but_spearman_brown_present(self):
        """
        Edge case: spearman_brown cannot be present when raw_correlation is None.

        This validates the mathematical constraint that the Spearman-Brown
        correction requires a raw correlation value. Previously this was allowed,
        but RE-FI-027 added validation to enforce this constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=0.85,  # Cannot be present without raw_correlation
                meets_threshold=True,
                num_sessions=100,
            )

        error_messages = str(exc_info.value)
        assert (
            "spearman_brown cannot be present when raw_correlation is None"
            in error_messages
        )

    def test_valid_when_both_correlations_none(self):
        """
        Valid: Both raw_correlation and spearman_brown can be None (insufficient data).
        """
        metrics = SplitHalfMetrics(
            raw_correlation=None,
            spearman_brown=None,
            meets_threshold=False,
            num_sessions=50,
        )
        assert metrics.raw_correlation is None
        assert metrics.spearman_brown is None
        assert metrics.meets_threshold is False


class TestBidirectionalValidationThresholdConstants:
    """
    Tests to verify the threshold constants are correctly imported and used.
    """

    def test_alpha_threshold_is_070(self):
        """Verify ALPHA_THRESHOLD constant is 0.70."""
        assert ALPHA_THRESHOLD == 0.70

    def test_test_retest_threshold_is_050(self):
        """Verify TEST_RETEST_THRESHOLD constant is 0.50."""
        assert TEST_RETEST_THRESHOLD == 0.50

    def test_split_half_threshold_is_070(self):
        """Verify SPLIT_HALF_THRESHOLD constant is 0.70."""
        assert SPLIT_HALF_THRESHOLD == 0.70


# =============================================================================
# Spearman-Brown Requires Raw Correlation Validation Tests (RE-FI-027)
# =============================================================================


class TestSpearmanBrownRequiresRawCorrelation:
    """
    Tests for the validation that spearman_brown cannot be present when
    raw_correlation is None.

    The Spearman-Brown correction formula is:
        r_full = (2 × r_half) / (1 + r_half)

    Mathematically, spearman_brown cannot exist without a raw correlation
    value to apply the correction to.
    """

    def test_invalid_spearman_brown_present_without_raw_correlation(self):
        """
        Invalid: Cannot have spearman_brown when raw_correlation is None.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=0.75,
                meets_threshold=True,
                num_sessions=100,
            )

        error_messages = str(exc_info.value)
        assert (
            "spearman_brown cannot be present when raw_correlation is None"
            in error_messages
        )

    def test_invalid_spearman_brown_below_threshold_without_raw_correlation(self):
        """
        Invalid: Cannot have spearman_brown when raw_correlation is None,
        even when spearman_brown is below threshold.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=0.55,
                meets_threshold=False,
                num_sessions=100,
            )

        error_messages = str(exc_info.value)
        assert (
            "spearman_brown cannot be present when raw_correlation is None"
            in error_messages
        )

    def test_invalid_spearman_brown_zero_without_raw_correlation(self):
        """
        Invalid: Cannot have spearman_brown=0.0 when raw_correlation is None.

        Even though 0.0 might seem like a "null" value, it's still a valid
        calculated correlation, and the constraint should still apply.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=0.0,
                meets_threshold=False,
                num_sessions=100,
            )

        error_messages = str(exc_info.value)
        assert (
            "spearman_brown cannot be present when raw_correlation is None"
            in error_messages
        )

    def test_invalid_spearman_brown_negative_without_raw_correlation(self):
        """
        Invalid: Cannot have negative spearman_brown when raw_correlation is None.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=-0.25,
                meets_threshold=False,
                num_sessions=100,
            )

        error_messages = str(exc_info.value)
        assert (
            "spearman_brown cannot be present when raw_correlation is None"
            in error_messages
        )

    def test_valid_both_correlations_present(self):
        """
        Valid: Both raw_correlation and spearman_brown are present.
        This is the normal case when calculation succeeds.
        """
        metrics = SplitHalfMetrics(
            raw_correlation=0.70,
            spearman_brown=0.82,
            meets_threshold=True,
            num_sessions=150,
        )
        assert metrics.raw_correlation == 0.70
        assert metrics.spearman_brown == 0.82
        assert metrics.meets_threshold is True

    def test_valid_both_correlations_none(self):
        """
        Valid: Both raw_correlation and spearman_brown are None.
        This is the normal case when there's insufficient data.
        """
        metrics = SplitHalfMetrics(
            raw_correlation=None,
            spearman_brown=None,
            meets_threshold=False,
            num_sessions=50,
        )
        assert metrics.raw_correlation is None
        assert metrics.spearman_brown is None
        assert metrics.meets_threshold is False

    def test_valid_raw_correlation_present_spearman_brown_none(self):
        """
        Valid: raw_correlation is present but spearman_brown is None.

        This is a valid edge case - technically the raw correlation could
        be calculated but the Spearman-Brown correction not applied for
        some reason (though unlikely in practice).
        """
        metrics = SplitHalfMetrics(
            raw_correlation=0.65,
            spearman_brown=None,
            meets_threshold=False,
            num_sessions=100,
        )
        assert metrics.raw_correlation == 0.65
        assert metrics.spearman_brown is None
        assert metrics.meets_threshold is False

    def test_error_message_explains_mathematical_constraint(self):
        """
        Verify the error message explains the mathematical reason for the constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=0.80,
                meets_threshold=True,
                num_sessions=100,
            )

        error_messages = str(exc_info.value)
        # Should mention the Spearman-Brown correction
        assert "Spearman-Brown correction" in error_messages
        # Should mention that raw correlation is required
        assert "requires a raw correlation value" in error_messages

    def test_validation_runs_with_both_validators(self):
        """
        Verify both validators run: spearman_brown requires raw_correlation
        AND meets_threshold consistency.

        When raw_correlation is None but spearman_brown is present,
        the spearman_brown validation should fail first.
        """
        with pytest.raises(ValidationError) as exc_info:
            SplitHalfMetrics(
                raw_correlation=None,
                spearman_brown=0.85,  # Present without raw_correlation
                meets_threshold=True,
                num_sessions=100,
            )

        # The spearman_brown requires raw_correlation error should be raised
        error_messages = str(exc_info.value)
        assert (
            "spearman_brown cannot be present when raw_correlation is None"
            in error_messages
        )

    def test_valid_at_threshold_boundary_with_both_correlations(self):
        """
        Valid: Both correlations present and spearman_brown is exactly at threshold.
        """
        # Using raw_correlation that produces spearman_brown = 0.70
        # r_sb = 2r / (1+r) = 0.70 => r = 0.538...
        metrics = SplitHalfMetrics(
            raw_correlation=0.538,
            spearman_brown=0.70,
            meets_threshold=True,
            num_sessions=150,
        )
        assert metrics.raw_correlation == 0.538
        assert metrics.spearman_brown == 0.70
        assert metrics.meets_threshold is True

    def test_valid_with_very_low_correlations(self):
        """
        Valid: Both correlations present but very low (near zero).
        """
        metrics = SplitHalfMetrics(
            raw_correlation=0.05,
            spearman_brown=0.095,  # Approximately 2*0.05 / (1+0.05)
            meets_threshold=False,
            num_sessions=100,
        )
        assert metrics.raw_correlation == 0.05
        assert metrics.spearman_brown == 0.095
        assert metrics.meets_threshold is False
