"""
Tests for CATSessionManager orchestrator (TASK-864).

Tests cover:
- Session initialization (default and custom prior theta)
- Response processing and theta re-estimation
- EAP ability estimation (correctness and edge cases)
- Stopping rules (min items, max items, SE threshold)
- Content balance checking
- Fisher information calculation
- Finalization and IQ score conversion
- Domain score calculation
"""
import pytest

from app.core.cat.engine import (
    CATSession,
    CATSessionManager,
    ItemResponse,
)


@pytest.fixture
def manager() -> CATSessionManager:
    """Create a CATSessionManager instance."""
    return CATSessionManager()


class TestInitialize:
    """Tests for CATSessionManager.initialize()."""

    def test_default_prior(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        assert session.user_id == 1
        assert session.session_id == 100
        assert session.theta_estimate == pytest.approx(0.0)
        assert session.theta_se == pytest.approx(1.0)
        assert session.administered_items == []
        assert session.responses == []
        assert session.correct_count == 0

    def test_custom_prior(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100, prior_theta=0.5)
        assert session.theta_estimate == pytest.approx(0.5)
        assert session.theta_se == pytest.approx(1.0)

    def test_negative_prior(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100, prior_theta=-1.0)
        assert session.theta_estimate == pytest.approx(-1.0)

    def test_domain_coverage_initialized(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        expected_domains = {"pattern", "logic", "verbal", "spatial", "math", "memory"}
        assert set(session.domain_coverage.keys()) == expected_domains
        for count in session.domain_coverage.values():
            assert count == 0

    def test_started_at_set(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        assert session.started_at is not None


class TestProcessResponse:
    """Tests for CATSessionManager.process_response()."""

    def test_correct_response_updates_session(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        result = manager.process_response(
            session=session,
            question_id=1,
            is_correct=True,
            question_type="pattern",
            irt_difficulty=0.0,
            irt_discrimination=1.0,
        )
        assert result.items_administered == 1
        assert result.correct_count == 1
        assert session.correct_count == 1
        assert session.administered_items == [1]
        assert len(session.responses) == 1
        assert session.domain_coverage["pattern"] == 1

    def test_incorrect_response(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        result = manager.process_response(
            session=session,
            question_id=1,
            is_correct=False,
            question_type="logic",
            irt_difficulty=0.0,
            irt_discrimination=1.0,
        )
        assert result.correct_count == 0
        assert session.correct_count == 0

    def test_multiple_responses_accumulate(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        for i in range(5):
            manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=(i % 2 == 0),
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=1.0,
            )
        assert len(session.administered_items) == 5
        assert session.correct_count == 3  # items 1, 3, 5 correct
        assert session.domain_coverage["pattern"] == 5

    def test_theta_increases_with_correct_answers(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        # Answer all items correctly — theta should increase
        for i in range(3):
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=True,
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=1.0,
            )
        assert result.theta_estimate > 0.0

    def test_theta_decreases_with_incorrect_answers(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        for i in range(3):
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=False,
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=1.0,
            )
        assert result.theta_estimate < 0.0

    def test_se_decreases_with_more_responses(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        initial_se = session.theta_se
        for i in range(5):
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=(i % 2 == 0),
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=1.0,
            )
        # SE should decrease as more data is accumulated
        assert result.theta_se < initial_se

    def test_does_not_stop_before_min_items(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        for i in range(manager.MIN_ITEMS - 1):
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=True,
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=1.5,
            )
        assert result.should_stop is False
        assert result.stop_reason is None

    def test_rejects_zero_discrimination(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        with pytest.raises(ValueError, match="irt_discrimination must be positive"):
            manager.process_response(
                session=session,
                question_id=1,
                is_correct=True,
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=0.0,
            )

    def test_rejects_negative_discrimination(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        with pytest.raises(ValueError, match="irt_discrimination must be positive"):
            manager.process_response(
                session=session,
                question_id=1,
                is_correct=True,
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=-0.5,
            )


class TestEstimateThetaEAP:
    """Tests for CATSessionManager.estimate_theta_eap()."""

    def test_no_responses_returns_prior(self, manager: CATSessionManager):
        theta, se = manager.estimate_theta_eap([], prior_mean=0.0, prior_sd=1.0)
        assert theta == pytest.approx(0.0)
        assert se == pytest.approx(1.0)

    def test_no_responses_custom_prior(self, manager: CATSessionManager):
        theta, se = manager.estimate_theta_eap([], prior_mean=0.5, prior_sd=0.8)
        assert theta == pytest.approx(0.5)
        assert se == pytest.approx(0.8)

    def test_all_correct_increases_theta(self, manager: CATSessionManager):
        responses = [
            ItemResponse(
                question_id=i,
                is_correct=True,
                irt_difficulty=0.0,
                irt_discrimination=1.0,
                question_type="pattern",
            )
            for i in range(5)
        ]
        theta, se = manager.estimate_theta_eap(responses)
        assert theta > 0.0

    def test_all_incorrect_decreases_theta(self, manager: CATSessionManager):
        responses = [
            ItemResponse(
                question_id=i,
                is_correct=False,
                irt_difficulty=0.0,
                irt_discrimination=1.0,
                question_type="pattern",
            )
            for i in range(5)
        ]
        theta, se = manager.estimate_theta_eap(responses)
        assert theta < 0.0

    def test_mixed_responses_near_zero(self, manager: CATSessionManager):
        """50/50 responses on average-difficulty items should give theta near 0."""
        responses = [
            ItemResponse(
                question_id=i,
                is_correct=(i % 2 == 0),
                irt_difficulty=0.0,
                irt_discrimination=1.0,
                question_type="pattern",
            )
            for i in range(10)
        ]
        theta, se = manager.estimate_theta_eap(responses)
        assert abs(theta) < 0.5  # Should be near zero

    def test_se_decreases_with_more_items(self, manager: CATSessionManager):
        """SE should decrease as we add more response data."""
        responses_3 = [
            ItemResponse(
                question_id=i,
                is_correct=True,
                irt_difficulty=0.0,
                irt_discrimination=1.0,
                question_type="pattern",
            )
            for i in range(3)
        ]
        responses_10 = [
            ItemResponse(
                question_id=i,
                is_correct=True,
                irt_difficulty=0.0,
                irt_discrimination=1.0,
                question_type="pattern",
            )
            for i in range(10)
        ]
        _, se_3 = manager.estimate_theta_eap(responses_3)
        _, se_10 = manager.estimate_theta_eap(responses_10)
        assert se_10 < se_3

    def test_high_discrimination_reduces_se_faster(self, manager: CATSessionManager):
        """Items with higher discrimination should reduce SE faster."""
        responses_low_a = [
            ItemResponse(
                question_id=i,
                is_correct=True,
                irt_difficulty=0.0,
                irt_discrimination=0.5,
                question_type="pattern",
            )
            for i in range(5)
        ]
        responses_high_a = [
            ItemResponse(
                question_id=i,
                is_correct=True,
                irt_difficulty=0.0,
                irt_discrimination=2.0,
                question_type="pattern",
            )
            for i in range(5)
        ]
        _, se_low = manager.estimate_theta_eap(responses_low_a)
        _, se_high = manager.estimate_theta_eap(responses_high_a)
        assert se_high < se_low

    def test_theta_bounded(self, manager: CATSessionManager):
        """Theta should remain within quadrature range even with extreme responses."""
        responses = [
            ItemResponse(
                question_id=i,
                is_correct=True,
                irt_difficulty=-3.0,  # Very easy items
                irt_discrimination=2.0,
                question_type="pattern",
            )
            for i in range(15)
        ]
        theta, se = manager.estimate_theta_eap(responses)
        assert -4.0 <= theta <= 4.0
        assert se > 0.0


class TestShouldStop:
    """Tests for CATSessionManager.should_stop()."""

    @staticmethod
    def _set_content_balanced(session: CATSession, min_per_domain: int = 2):
        """Set all domains to meet minimum content balance."""
        for domain in session.domain_coverage:
            session.domain_coverage[domain] = min_per_domain

    def test_below_min_items_no_stop(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.administered_items = list(range(manager.MIN_ITEMS - 1))
        session.theta_se = 0.10  # Even with very low SE
        should_stop, reason = manager.should_stop(session)
        assert should_stop is False
        assert reason is None

    def test_at_max_items_stops(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.administered_items = list(range(manager.MAX_ITEMS))
        session.theta_se = 0.50  # Even with high SE
        should_stop, reason = manager.should_stop(session)
        assert should_stop is True
        assert reason == "max_items"

    def test_se_below_threshold_stops_when_balanced(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.administered_items = list(range(manager.MIN_ITEMS))
        session.theta_se = 0.25  # Below 0.30 threshold
        self._set_content_balanced(session)
        should_stop, reason = manager.should_stop(session)
        assert should_stop is True
        assert reason == "se_threshold"

    def test_se_below_threshold_no_stop_when_unbalanced(
        self, manager: CATSessionManager
    ):
        """SE is below threshold but content balance is not met — keep going."""
        session = manager.initialize(user_id=1, session_id=100)
        session.administered_items = list(range(manager.MIN_ITEMS))
        session.theta_se = 0.25  # Below threshold
        # Only pattern domain has items
        session.domain_coverage["pattern"] = manager.MIN_ITEMS
        should_stop, reason = manager.should_stop(session)
        assert should_stop is False
        assert reason is None

    def test_se_above_threshold_no_stop(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.administered_items = list(range(manager.MIN_ITEMS))
        session.theta_se = 0.35  # Above 0.30 threshold
        self._set_content_balanced(session)
        should_stop, reason = manager.should_stop(session)
        assert should_stop is False
        assert reason is None

    def test_exactly_at_se_threshold_no_stop(self, manager: CATSessionManager):
        """SE exactly at threshold should NOT stop (requires strictly below)."""
        session = manager.initialize(user_id=1, session_id=100)
        session.administered_items = list(range(manager.MIN_ITEMS))
        session.theta_se = manager.SE_THRESHOLD
        self._set_content_balanced(session)
        should_stop, reason = manager.should_stop(session)
        assert should_stop is False
        assert reason is None

    def test_max_items_takes_priority_over_balance(self, manager: CATSessionManager):
        """Max items should stop even if content balance is not met."""
        session = manager.initialize(user_id=1, session_id=100)
        session.administered_items = list(range(manager.MAX_ITEMS))
        session.theta_se = 0.50
        # Content balance NOT met
        should_stop, reason = manager.should_stop(session)
        assert should_stop is True
        assert reason == "max_items"


class TestCheckContentBalance:
    """Tests for CATSessionManager._check_content_balance()."""

    def test_all_domains_met(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        for domain in session.domain_coverage:
            session.domain_coverage[domain] = manager.MIN_ITEMS_PER_DOMAIN
        assert manager._check_content_balance(session) is True

    def test_one_domain_missing(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        for domain in session.domain_coverage:
            session.domain_coverage[domain] = manager.MIN_ITEMS_PER_DOMAIN
        session.domain_coverage["memory"] = 0
        assert manager._check_content_balance(session) is False

    def test_empty_session(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        assert manager._check_content_balance(session) is False


class TestFisherInformation:
    """Tests for CATSessionManager.calculate_fisher_information()."""

    def test_max_information_at_difficulty(self, manager: CATSessionManager):
        """Fisher information should be maximized when theta = b."""
        info_at_b = manager.calculate_fisher_information(
            theta=0.5, irt_difficulty=0.5, irt_discrimination=1.0
        )
        info_away = manager.calculate_fisher_information(
            theta=2.0, irt_difficulty=0.5, irt_discrimination=1.0
        )
        assert info_at_b > info_away

    def test_higher_discrimination_more_information(self, manager: CATSessionManager):
        """Higher discrimination items provide more information."""
        info_low = manager.calculate_fisher_information(
            theta=0.0, irt_difficulty=0.0, irt_discrimination=0.5
        )
        info_high = manager.calculate_fisher_information(
            theta=0.0, irt_difficulty=0.0, irt_discrimination=2.0
        )
        assert info_high > info_low

    def test_information_at_match_equals_a_squared_over_4(
        self, manager: CATSessionManager
    ):
        """When theta = b, I(θ) = a²/4 (since P=0.5, so P(1-P)=0.25)."""
        a = 1.5
        info = manager.calculate_fisher_information(
            theta=0.0, irt_difficulty=0.0, irt_discrimination=a
        )
        expected = (a**2) * 0.25
        assert info == pytest.approx(expected)

    def test_information_non_negative(self, manager: CATSessionManager):
        """Fisher information should always be non-negative."""
        for theta in [-3.0, -1.0, 0.0, 1.0, 3.0]:
            for b in [-2.0, 0.0, 2.0]:
                for a in [0.5, 1.0, 2.0]:
                    info = manager.calculate_fisher_information(theta, b, a)
                    assert info >= 0.0

    def test_extreme_theta_values(self, manager: CATSessionManager):
        """Fisher information should be small for extreme theta values."""
        info = manager.calculate_fisher_information(
            theta=10.0, irt_difficulty=0.0, irt_discrimination=1.0
        )
        assert info < 0.01  # Very little information far from difficulty


class TestFinalize:
    """Tests for CATSessionManager.finalize()."""

    def test_zero_theta_gives_iq_100(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.theta_estimate = 0.0
        session.theta_se = 0.25
        result = manager.finalize(session, stop_reason="se_threshold")
        assert result.iq_score == 100

    def test_positive_theta_gives_above_100(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.theta_estimate = 1.0  # +1 SD
        session.theta_se = 0.25
        result = manager.finalize(session, stop_reason="se_threshold")
        assert result.iq_score == 115

    def test_negative_theta_gives_below_100(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.theta_estimate = -1.0  # -1 SD
        session.theta_se = 0.25
        result = manager.finalize(session, stop_reason="se_threshold")
        assert result.iq_score == 85

    def test_iq_clamped_upper(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.theta_estimate = 5.0  # Very high
        session.theta_se = 0.25
        result = manager.finalize(session, stop_reason="max_items")
        assert result.iq_score == 160

    def test_iq_clamped_lower(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.theta_estimate = -5.0  # Very low
        session.theta_se = 0.25
        result = manager.finalize(session, stop_reason="max_items")
        assert result.iq_score == 40

    def test_domain_scores_calculated(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        # Simulate some responses
        session.responses = [
            ItemResponse(1, True, 0.0, 1.0, "pattern"),
            ItemResponse(2, False, 0.0, 1.0, "pattern"),
            ItemResponse(3, True, 0.0, 1.0, "logic"),
        ]
        session.domain_coverage["pattern"] = 2
        session.domain_coverage["logic"] = 1
        session.administered_items = [1, 2, 3]
        session.correct_count = 2

        result = manager.finalize(session, stop_reason="se_threshold")
        assert result.domain_scores["pattern"]["items_administered"] == 2
        assert result.domain_scores["pattern"]["correct_count"] == 1
        assert result.domain_scores["pattern"]["accuracy"] == pytest.approx(0.5)
        assert result.domain_scores["logic"]["items_administered"] == 1
        assert result.domain_scores["logic"]["correct_count"] == 1
        assert result.domain_scores["logic"]["accuracy"] == pytest.approx(1.0)
        # Domains with no items
        assert result.domain_scores["memory"]["items_administered"] == 0
        assert result.domain_scores["memory"]["accuracy"] == pytest.approx(0.0)

    def test_result_contains_stop_reason(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        result = manager.finalize(session, stop_reason="max_items")
        assert result.stop_reason == "max_items"

    def test_result_contains_all_fields(self, manager: CATSessionManager):
        session = manager.initialize(user_id=1, session_id=100)
        session.theta_estimate = 0.5
        session.theta_se = 0.28
        session.correct_count = 7
        session.administered_items = list(range(10))
        result = manager.finalize(session, stop_reason="se_threshold")
        assert result.theta_estimate == pytest.approx(0.5)
        assert result.theta_se == pytest.approx(0.28)
        assert result.correct_count == 7
        assert result.items_administered == 10


class TestEndToEnd:
    """End-to-end tests simulating a full CAT session."""

    def test_full_session_all_correct(self, manager: CATSessionManager):
        """Simulate a test where user answers all items correctly."""
        session = manager.initialize(user_id=1, session_id=100)
        domains = ["pattern", "logic", "verbal", "spatial", "math", "memory"]
        stop_result = None

        for i in range(manager.MAX_ITEMS):
            domain = domains[i % len(domains)]
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=True,
                question_type=domain,
                irt_difficulty=0.0,
                irt_discrimination=1.0,
            )
            if result.should_stop:
                stop_result = result
                break

        assert stop_result is not None
        # High-ability user should have positive theta
        assert stop_result.theta_estimate > 0.0
        # Finalize
        final = manager.finalize(
            session, stop_reason=stop_result.stop_reason or "max_items"
        )
        assert final.iq_score > 100

    def test_full_session_all_incorrect(self, manager: CATSessionManager):
        """Simulate a test where user answers all items incorrectly."""
        session = manager.initialize(user_id=1, session_id=100)
        domains = ["pattern", "logic", "verbal", "spatial", "math", "memory"]
        stop_result = None

        for i in range(manager.MAX_ITEMS):
            domain = domains[i % len(domains)]
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=False,
                question_type=domain,
                irt_difficulty=0.0,
                irt_discrimination=1.0,
            )
            if result.should_stop:
                stop_result = result
                break

        assert stop_result is not None
        assert stop_result.theta_estimate < 0.0
        final = manager.finalize(
            session, stop_reason=stop_result.stop_reason or "max_items"
        )
        assert final.iq_score < 100

    def test_max_items_reached(self, manager: CATSessionManager):
        """Test that session stops at MAX_ITEMS even with high SE."""
        session = manager.initialize(user_id=1, session_id=100)

        # Alternate correct/incorrect to keep SE high (inconsistent pattern)
        for i in range(manager.MAX_ITEMS):
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=(i % 2 == 0),
                question_type="pattern",
                irt_difficulty=0.0,
                irt_discrimination=0.3,  # Low discrimination = slow SE reduction
            )

        assert result.should_stop is True
        assert result.stop_reason == "max_items"
        assert result.items_administered == manager.MAX_ITEMS

    def test_se_threshold_reached(self, manager: CATSessionManager):
        """Test that session stops when SE drops below threshold."""
        session = manager.initialize(user_id=1, session_id=100)
        domains = ["pattern", "logic", "verbal", "spatial", "math", "memory"]

        # Use very high discrimination items and consistent responses for fast SE reduction
        # Cycle through all domains to satisfy content balance (MIN_ITEMS_PER_DOMAIN=2)
        for i in range(manager.MAX_ITEMS):
            domain = domains[i % len(domains)]
            result = manager.process_response(
                session=session,
                question_id=i + 1,
                is_correct=True,
                question_type=domain,
                irt_difficulty=session.theta_estimate,  # Match item to ability
                irt_discrimination=3.0,  # Very high discrimination
            )
            if result.should_stop:
                break

        # Should stop before max items due to SE threshold
        assert result.should_stop is True
        assert result.stop_reason == "se_threshold"
        assert result.items_administered < manager.MAX_ITEMS
