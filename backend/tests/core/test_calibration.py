"""
Tests for Bayesian 2PL IRT calibration module (TASK-856).

Tests cover:
- calibrate_questions_2pl: Parameter recovery with synthetic data
- calibrate_questions_2pl: Missing data handling
- calibrate_questions_2pl: Input validation and edge cases
- build_priors_from_ctt: CTT-to-IRT prior conversion
- run_calibration_job: Full pipeline with database integration
- validate_calibration: Validation report generation
"""

from datetime import datetime

import numpy as np
import pytest
import pytest_asyncio

from app.core.cat.calibration import (
    FIT_GOOD,
    FIT_INSUFFICIENT,
    CalibrationError,
    build_priors_from_ctt,
    calibrate_questions_2pl,
    run_calibration_job,
    validate_calibration,
)
from app.models.models import (
    DifficultyLevel,
    Question,
    QuestionType,
    Response,
    TestSession,
    TestStatus,
    User,
)


def _generate_2pl_responses(
    n_items: int,
    n_examinees: int,
    true_a: np.ndarray,
    true_b: np.ndarray,
    seed: int = 42,
    missing_rate: float = 0.0,
) -> list[dict]:
    """Generate synthetic 2PL response data with known parameters.

    Args:
        n_items: Number of items.
        n_examinees: Number of examinees.
        true_a: True discrimination parameters (length n_items).
        true_b: True difficulty parameters (length n_items).
        seed: Random seed for reproducibility.
        missing_rate: Fraction of responses to mark as missing (0.0-1.0).

    Returns:
        List of response dicts with user_id, question_id, is_correct.
    """
    rng = np.random.default_rng(seed)
    theta = rng.standard_normal(n_examinees)

    responses = []
    for j in range(n_examinees):
        for i in range(n_items):
            if missing_rate > 0 and rng.random() < missing_rate:
                continue  # Skip this response (missing data)
            p = 1.0 / (1.0 + np.exp(-true_a[i] * (theta[j] - true_b[i])))
            is_correct = bool(rng.random() < p)
            responses.append(
                {
                    "user_id": j + 1,
                    "question_id": i + 1,
                    "is_correct": is_correct,
                }
            )
    return responses


class TestCalibrateQuestions2PL:
    """Tests for the core calibrate_questions_2pl function."""

    def test_parameter_recovery_complete_data(self):
        """Estimated parameters should correlate with true parameters."""
        n_items = 30
        n_examinees = 300
        rng = np.random.default_rng(42)
        true_a = rng.uniform(0.5, 2.5, n_items)
        true_b = rng.normal(0, 1.2, n_items)

        responses = _generate_2pl_responses(
            n_items, n_examinees, true_a, true_b, seed=42
        )

        results = calibrate_questions_2pl(
            responses=responses,
            bootstrap_se=False,
        )

        assert len(results) == n_items

        est_a = np.array([results[i + 1]["discrimination"] for i in range(n_items)])
        est_b = np.array([results[i + 1]["difficulty"] for i in range(n_items)])

        # Difficulty should recover well
        corr_b = np.corrcoef(true_b, est_b)[0, 1]
        assert corr_b > 0.90, f"Difficulty correlation {corr_b:.3f} < 0.90"

        # Discrimination recovery (less precise, especially with moderate N)
        corr_a = np.corrcoef(true_a, est_a)[0, 1]
        assert corr_a > 0.70, f"Discrimination correlation {corr_a:.3f} < 0.70"

        # All items should have information_peak = difficulty
        for qid, params in results.items():
            assert params["information_peak"] == pytest.approx(params["difficulty"])

    def test_parameter_recovery_with_missing_data(self):
        """Calibration should handle sparse response matrices."""
        n_items = 25
        n_examinees = 200
        rng = np.random.default_rng(123)
        true_a = rng.uniform(0.8, 2.0, n_items)
        true_b = rng.normal(0, 1.0, n_items)

        responses = _generate_2pl_responses(
            n_items, n_examinees, true_a, true_b, seed=123, missing_rate=0.3
        )

        results = calibrate_questions_2pl(
            responses=responses,
            bootstrap_se=False,
        )

        est_b = np.array([results[i + 1]["difficulty"] for i in range(n_items)])
        corr_b = np.corrcoef(true_b, est_b)[0, 1]
        assert (
            corr_b > 0.85
        ), f"Difficulty correlation with 30% missing: {corr_b:.3f} < 0.85"

    def test_bootstrap_standard_errors(self):
        """Bootstrap SEs should be positive and reasonable."""
        n_items = 15
        n_examinees = 100
        rng = np.random.default_rng(42)
        true_a = rng.uniform(0.8, 1.8, n_items)
        true_b = rng.normal(0, 1.0, n_items)

        responses = _generate_2pl_responses(
            n_items, n_examinees, true_a, true_b, seed=42
        )

        results = calibrate_questions_2pl(
            responses=responses,
            bootstrap_se=True,
            bootstrap_iterations=100,  # Reduced for test speed
            bootstrap_n_processors=1,
        )

        for qid, params in results.items():
            assert (
                params["se_difficulty"] > 0
            ), f"SE difficulty should be positive for item {qid}"
            assert (
                params["se_discrimination"] > 0
            ), f"SE discrimination should be positive for item {qid}"
            # SEs should be reasonable (not absurdly large)
            assert (
                params["se_difficulty"] < 5.0
            ), f"SE difficulty {params['se_difficulty']:.2f} too large for item {qid}"
            assert params["se_discrimination"] < 5.0, (
                f"SE discrimination {params['se_discrimination']:.2f} too large "
                f"for item {qid}"
            )

    def test_empty_responses_raises_error(self):
        """Empty response list should raise CalibrationError."""
        with pytest.raises(CalibrationError, match="No responses provided"):
            calibrate_questions_2pl(responses=[])

    def test_single_item_raises_error(self):
        """Single item should raise CalibrationError (need >= 2)."""
        responses = [
            {"user_id": 1, "question_id": 1, "is_correct": True},
            {"user_id": 2, "question_id": 1, "is_correct": False},
        ]
        with pytest.raises(CalibrationError, match="At least 2 items"):
            calibrate_questions_2pl(responses=responses)

    def test_few_examinees_raises_error(self):
        """Fewer than 10 examinees should raise CalibrationError."""
        responses = [
            {"user_id": u, "question_id": q, "is_correct": u % 2 == 0}
            for u in range(1, 6)
            for q in range(1, 5)
        ]
        with pytest.raises(CalibrationError, match="At least 10 examinees"):
            calibrate_questions_2pl(responses=responses)

    def test_extremely_sparse_matrix_raises_error(self):
        """Response matrix with >95% missing data should raise CalibrationError."""
        # 100 users, 100 items, but each user only answers 1 item -> 99% sparse
        responses = [
            {"user_id": u, "question_id": (u % 100) + 1, "is_correct": True}
            for u in range(1, 101)
        ]
        with pytest.raises(CalibrationError, match="too sparse"):
            calibrate_questions_2pl(responses=responses, bootstrap_se=False)

    def test_question_ids_filter(self):
        """Only requested question_ids should be calibrated."""
        n_items = 20
        n_examinees = 100
        rng = np.random.default_rng(42)
        true_a = rng.uniform(0.8, 2.0, n_items)
        true_b = rng.normal(0, 1.0, n_items)

        responses = _generate_2pl_responses(
            n_items, n_examinees, true_a, true_b, seed=42
        )

        subset_ids = [1, 5, 10, 15, 20]
        results = calibrate_questions_2pl(
            responses=responses,
            question_ids=subset_ids,
            bootstrap_se=False,
        )

        assert set(results.keys()) == set(subset_ids)

    def test_result_structure(self):
        """Each result should contain all required keys."""
        n_items = 10
        n_examinees = 50
        rng = np.random.default_rng(42)
        true_a = rng.uniform(0.8, 2.0, n_items)
        true_b = rng.normal(0, 1.0, n_items)

        responses = _generate_2pl_responses(
            n_items, n_examinees, true_a, true_b, seed=42
        )

        results = calibrate_questions_2pl(
            responses=responses,
            bootstrap_se=False,
        )

        expected_keys = {
            "difficulty",
            "discrimination",
            "se_difficulty",
            "se_discrimination",
            "information_peak",
        }
        for qid, params in results.items():
            assert (
                set(params.keys()) == expected_keys
            ), f"Item {qid} missing keys: {expected_keys - set(params.keys())}"
            # All values should be finite floats
            for key, value in params.items():
                assert isinstance(
                    value, float
                ), f"Item {qid} {key} should be float, got {type(value)}"
                assert np.isfinite(value), f"Item {qid} {key} is not finite: {value}"


class TestBuildPriorsFromCTT:
    """Tests for the build_priors_from_ctt function."""

    async def test_logit_transformation(self, db_session):
        """Empirical difficulty should transform to logit scale correctly."""
        # Easy item: p=0.80 -> b = -1.386
        q1 = Question(
            question_text="Easy question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=0.80,
            discrimination=0.40,
            is_active=True,
        )
        # Hard item: p=0.20 -> b = 1.386
        q2 = Question(
            question_text="Hard question",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="B",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=0.20,
            discrimination=0.30,
            is_active=True,
        )
        # Medium item: p=0.50 -> b = 0.0
        q3 = Question(
            question_text="Medium question",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="C",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=0.50,
            discrimination=0.50,
            is_active=True,
        )
        db_session.add_all([q1, q2, q3])
        await db_session.commit()

        prior_diffs, prior_discs = await build_priors_from_ctt(
            db_session, [q1.id, q2.id, q3.id]
        )

        # Easy item: negative b (below average difficulty)
        assert prior_diffs[q1.id] == pytest.approx(-1.386, abs=0.01)

        # Hard item: positive b (above average difficulty)
        assert prior_diffs[q2.id] == pytest.approx(1.386, abs=0.01)

        # Medium item: b = 0
        assert prior_diffs[q3.id] == pytest.approx(0.0, abs=0.01)

        # Discrimination priors should equal CTT values directly
        assert prior_discs[q1.id] == pytest.approx(0.40)
        assert prior_discs[q2.id] == pytest.approx(0.30)
        assert prior_discs[q3.id] == pytest.approx(0.50)

    async def test_missing_ctt_metrics(self, db_session):
        """Questions without CTT metrics should be excluded from priors."""
        q = Question(
            question_text="New question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=None,
            discrimination=None,
            is_active=True,
        )
        db_session.add(q)
        await db_session.commit()

        prior_diffs, prior_discs = await build_priors_from_ctt(db_session, [q.id])

        assert q.id not in prior_diffs
        assert q.id not in prior_discs

    async def test_negative_discrimination_excluded(self, db_session):
        """Negative CTT discrimination should not produce a prior."""
        q = Question(
            question_text="Bad discriminator",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=0.50,
            discrimination=-0.10,
            is_active=True,
        )
        db_session.add(q)
        await db_session.commit()

        prior_diffs, prior_discs = await build_priors_from_ctt(db_session, [q.id])

        assert q.id in prior_diffs  # Difficulty prior still valid
        assert q.id not in prior_discs  # Negative discrimination excluded

    async def test_extreme_p_values_clamped(self, db_session):
        """P-values near 0 or 1 should be clamped to avoid log(0)."""
        q_easy = Question(
            question_text="Nearly impossible to fail",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=0.999,
            discrimination=0.20,
            is_active=True,
        )
        q_hard = Question(
            question_text="Nearly impossible to answer",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="B",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=0.001,
            discrimination=0.15,
            is_active=True,
        )
        db_session.add_all([q_easy, q_hard])
        await db_session.commit()

        prior_diffs, _ = await build_priors_from_ctt(db_session, [q_easy.id, q_hard.id])

        # Should produce finite values (clamped)
        assert np.isfinite(prior_diffs[q_easy.id])
        assert np.isfinite(prior_diffs[q_hard.id])
        # Easy item should have negative b, hard positive
        assert prior_diffs[q_easy.id] < 0
        assert prior_diffs[q_hard.id] > 0


class TestRunCalibrationJob:
    """Tests for the full calibration pipeline."""

    @pytest_asyncio.fixture
    async def calibration_data(self, db_session):
        """Set up a realistic calibration scenario with questions, users, and responses."""
        test_password_hash = "hash"  # pragma: allowlist secret

        # Create users
        users = [
            User(email=f"cal_user{i}@test.com", password_hash=test_password_hash)
            for i in range(50)
        ]
        db_session.add_all(users)
        await db_session.flush()

        # Create questions with CTT stats
        questions = []
        rng = np.random.default_rng(42)
        true_a = rng.uniform(0.8, 2.0, 10)
        true_b = rng.normal(0, 1.0, 10)

        for i in range(10):
            q = Question(
                question_text=f"Calibration question {i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                answer_options=["A", "B", "C", "D"],
                empirical_difficulty=float(
                    1.0 / (1.0 + np.exp(true_b[i]))
                ),  # Convert b to p
                discrimination=float(true_a[i] / 2.0),
                response_count=50,
                is_active=True,
            )
            questions.append(q)

        db_session.add_all(questions)
        await db_session.flush()

        # Create test sessions and responses
        theta = rng.standard_normal(50)
        for u_idx, user in enumerate(users):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                is_adaptive=False,
                completed_at=datetime(2026, 1, 15, 12, 0, 0),
            )
            db_session.add(session)
            await db_session.flush()

            for q_idx, question in enumerate(questions):
                p = 1.0 / (
                    1.0 + np.exp(-true_a[q_idx] * (theta[u_idx] - true_b[q_idx]))
                )
                is_correct = bool(rng.random() < p)
                response = Response(
                    test_session_id=session.id,
                    user_id=user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    answered_at=datetime(2026, 1, 15, 12, 0, 0),
                )
                db_session.add(response)

        await db_session.commit()
        return {
            "questions": questions,
            "users": users,
            "true_a": true_a,
            "true_b": true_b,
        }

    async def test_full_pipeline(self, db_session, calibration_data):
        """Full calibration job should update IRT parameters in database."""
        result = await run_calibration_job(
            db=db_session,
            min_responses=10,
            bootstrap_se=False,
        )

        assert result["calibrated"] == 10
        assert result["skipped"] == 0
        assert result["timestamp"]

        # Verify database was updated with plausible values
        for q in calibration_data["questions"]:
            await db_session.refresh(q)
            assert q.irt_difficulty is not None
            assert q.irt_discrimination is not None
            assert q.irt_discrimination > 0, "Discrimination should be positive"
            assert q.irt_calibrated_at is not None
            assert q.irt_calibration_n >= 10
            assert q.irt_information_peak == pytest.approx(q.irt_difficulty)

        # Verify parameter recovery at the pipeline level
        est_b = [q.irt_difficulty for q in calibration_data["questions"]]
        true_b = calibration_data["true_b"]
        corr_b = np.corrcoef(true_b, est_b)[0, 1]
        assert (
            corr_b > 0.80
        ), f"Pipeline difficulty recovery correlation {corr_b:.3f} < 0.80"

    async def test_min_responses_filter(self, db_session, calibration_data):
        """High min_responses should filter out items with fewer responses."""
        result = await run_calibration_job(
            db=db_session,
            min_responses=999,
            bootstrap_se=False,
        )
        assert result["calibrated"] == 0

    async def test_specific_question_ids(self, db_session, calibration_data):
        """Specifying question_ids should limit calibration scope."""
        subset = [
            calibration_data["questions"][0].id,
            calibration_data["questions"][1].id,
        ]
        result = await run_calibration_job(
            db=db_session,
            question_ids=subset,
            min_responses=10,
            bootstrap_se=False,
        )
        assert result["calibrated"] == 2

    async def test_excludes_adaptive_sessions(self, db_session, calibration_data):
        """Responses from adaptive (CAT) sessions should be excluded."""
        # Add an adaptive session with many responses
        user = calibration_data["users"][0]
        adaptive_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=True,
            completed_at=datetime(2026, 1, 20, 12, 0, 0),
        )
        db_session.add(adaptive_session)
        await db_session.flush()

        for q in calibration_data["questions"]:
            resp = Response(
                test_session_id=adaptive_session.id,
                user_id=user.id,
                question_id=q.id,
                user_answer="A",
                is_correct=True,
                answered_at=datetime(2026, 1, 20, 12, 0, 0),
            )
            db_session.add(resp)
        await db_session.commit()

        # Calibration should still work (adaptive responses excluded)
        result = await run_calibration_job(
            db=db_session,
            min_responses=10,
            bootstrap_se=False,
        )
        assert result["calibrated"] == 10


class TestValidateCalibration:
    """Tests for the validate_calibration function."""

    async def test_good_fit(self, db_session):
        """Well-calibrated items should show good fit."""
        # Create items with consistent IRT and empirical difficulty
        for i in range(20):
            p = 0.1 + 0.04 * i  # Range from 0.10 to 0.86
            p_clamped = max(0.01, min(0.99, p))
            irt_b = -np.log(p_clamped / (1 - p_clamped))  # Logit transform
            # Add small noise to make it realistic
            irt_b_noisy = irt_b + np.random.default_rng(i).normal(0, 0.15)

            q = Question(
                question_text=f"Validated question {i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                answer_options=["A", "B", "C", "D"],
                empirical_difficulty=p,
                irt_difficulty=irt_b_noisy,
                irt_discrimination=1.0,
                irt_se_difficulty=0.20,
                irt_se_discrimination=0.15,
                irt_calibrated_at=datetime(2026, 1, 15, 12, 0, 0),
                is_active=True,
            )
            db_session.add(q)
        await db_session.commit()

        result = await validate_calibration(db_session)

        assert result["n_items"] == 20
        assert result["correlation_irt_empirical"] > 0.80
        assert result["interpretation"] == FIT_GOOD
        assert result["mean_se_difficulty"] == pytest.approx(0.20)
        assert result["mean_se_discrimination"] == pytest.approx(0.15)

    async def test_insufficient_items(self, db_session):
        """Fewer than 3 items should return insufficient message."""
        q = Question(
            question_text="Lonely question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options=["A", "B", "C", "D"],
            empirical_difficulty=0.50,
            irt_difficulty=0.0,
            is_active=True,
        )
        db_session.add(q)
        await db_session.commit()

        result = await validate_calibration(db_session)

        assert result["n_items"] == 1
        assert result["interpretation"] == FIT_INSUFFICIENT

    async def test_question_id_filter(self, db_session):
        """Should only validate specified question IDs."""
        questions = []
        for i in range(10):
            p = 0.2 + 0.06 * i
            q = Question(
                question_text=f"Filter question {i}",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                answer_options=["A", "B", "C", "D"],
                empirical_difficulty=p,
                irt_difficulty=-np.log(p / (1 - p)),
                irt_discrimination=1.0,
                irt_calibrated_at=datetime(2026, 1, 15, 12, 0, 0),
                is_active=True,
            )
            questions.append(q)
            db_session.add(q)
        await db_session.commit()

        subset_ids = [questions[0].id, questions[1].id, questions[2].id]
        result = await validate_calibration(db_session, question_ids=subset_ids)

        assert result["n_items"] == 3
