"""
Tests for CAT readiness evaluation service (TASK-835).

Tests cover:
- No calibrated items → not ready
- 5/6 domains ready → globally not ready
- All 6 domains pass → globally ready
- Items with SE above threshold excluded
- Difficulty band coverage required
- Inactive/flagged/uncalibrated items excluded
"""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cat.readiness import evaluate_cat_readiness
from app.models.models import (
    DifficultyLevel,
    Question,
    QuestionType,
)


def _create_calibrated_question(
    db_session: AsyncSession,
    question_type: QuestionType,
    irt_difficulty: float,
    irt_se_difficulty: float = 0.20,
    irt_se_discrimination: float = 0.15,
    irt_discrimination: float = 1.0,
    is_active: bool = True,
    quality_flag: str = "normal",
) -> Question:
    """Helper to create a well-calibrated question."""
    q = Question(
        question_text=f"Test question ({question_type.value}, b={irt_difficulty})",
        question_type=question_type,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="A",
        answer_options=["A", "B", "C", "D"],
        is_active=is_active,
        quality_flag=quality_flag,
        irt_difficulty=irt_difficulty,
        irt_discrimination=irt_discrimination,
        irt_se_difficulty=irt_se_difficulty,
        irt_se_discrimination=irt_se_discrimination,
        irt_calibrated_at=datetime(2026, 1, 15, 12, 0, 0),
    )
    db_session.add(q)
    return q


def _populate_domain_ready(
    db_session: AsyncSession,
    question_type: QuestionType,
    easy_count: int = 10,
    medium_count: int = 15,
    hard_count: int = 10,
) -> None:
    """Helper to populate a domain with enough calibrated items to pass."""
    # Easy items: b < -1.0
    for i in range(easy_count):
        _create_calibrated_question(
            db_session, question_type, irt_difficulty=-1.5 - i * 0.1
        )
    # Medium items: -1.0 <= b <= 1.0
    for i in range(medium_count):
        _create_calibrated_question(
            db_session, question_type, irt_difficulty=-0.5 + i * 0.1
        )
    # Hard items: b > 1.0
    for i in range(hard_count):
        _create_calibrated_question(
            db_session, question_type, irt_difficulty=1.5 + i * 0.1
        )


class TestCATReadinessNoItems:
    """Tests with no calibrated items."""

    async def test_empty_database_not_ready(self, db_session: AsyncSession):
        """No calibrated items → globally not ready."""
        result = await evaluate_cat_readiness(db_session)

        assert result.is_globally_ready is False
        assert len(result.domains) == 6
        for domain in result.domains:
            assert domain.is_ready is False
            assert domain.total_calibrated == 0
            assert domain.well_calibrated == 0

    async def test_uncalibrated_items_not_counted(self, db_session: AsyncSession):
        """Items without irt_calibrated_at are not counted."""
        # Create questions without IRT calibration
        for q_type in QuestionType:
            for _ in range(50):
                q = Question(
                    question_text="Uncalibrated question",
                    question_type=q_type,
                    difficulty_level=DifficultyLevel.MEDIUM,
                    correct_answer="A",
                    answer_options=["A", "B", "C", "D"],
                    is_active=True,
                    quality_flag="normal",
                    irt_difficulty=0.0,
                    irt_discrimination=1.0,
                    # No irt_calibrated_at, irt_se_difficulty, irt_se_discrimination
                )
                db_session.add(q)
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)
        assert result.is_globally_ready is False
        for domain in result.domains:
            assert domain.total_calibrated == 0
            assert domain.well_calibrated == 0


class TestCATReadinessPartialDomains:
    """Tests with some domains ready."""

    async def test_five_of_six_domains_not_globally_ready(
        self, db_session: AsyncSession
    ):
        """5/6 domains ready → globally not ready."""
        # Make 5 domains ready
        ready_types = list(QuestionType)[:5]
        for q_type in ready_types:
            _populate_domain_ready(db_session, q_type)
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        assert result.is_globally_ready is False
        ready_count = sum(1 for d in result.domains if d.is_ready)
        assert ready_count == 5
        assert "5/6" in result.summary


class TestCATReadinessAllDomains:
    """Tests with all domains ready."""

    async def test_all_six_domains_globally_ready(self, db_session: AsyncSession):
        """All 6 domains pass → globally ready."""
        for q_type in QuestionType:
            _populate_domain_ready(db_session, q_type)
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        assert result.is_globally_ready is True
        assert all(d.is_ready for d in result.domains)
        assert "6/6" in result.summary

    async def test_thresholds_in_result(self, db_session: AsyncSession):
        """Result includes thresholds used for evaluation."""
        result = await evaluate_cat_readiness(db_session)

        assert "min_calibrated_items_per_domain" in result.thresholds
        assert "max_se_difficulty" in result.thresholds
        assert "max_se_discrimination" in result.thresholds
        assert "min_items_per_difficulty_band" in result.thresholds


class TestCATReadinessSEFiltering:
    """Tests for SE-based item filtering."""

    async def test_high_se_difficulty_excluded(self, db_session: AsyncSession):
        """Items with SE(difficulty) above threshold are excluded."""
        q_type = QuestionType.PATTERN

        # Create items with high SE on difficulty (above 0.50 threshold)
        for i in range(40):
            _create_calibrated_question(
                db_session,
                q_type,
                irt_difficulty=-1.5 + i * 0.1,
                irt_se_difficulty=0.60,  # Above threshold
                irt_se_discrimination=0.15,
            )
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        pattern_domain = next(d for d in result.domains if d.domain == "pattern")
        assert pattern_domain.total_calibrated == 40
        assert pattern_domain.well_calibrated == 0
        assert pattern_domain.is_ready is False

    async def test_high_se_discrimination_excluded(self, db_session: AsyncSession):
        """Items with SE(discrimination) above threshold are excluded."""
        q_type = QuestionType.LOGIC

        # Create items with high SE on discrimination (above 0.30 threshold)
        for i in range(40):
            _create_calibrated_question(
                db_session,
                q_type,
                irt_difficulty=-1.5 + i * 0.1,
                irt_se_difficulty=0.20,
                irt_se_discrimination=0.40,  # Above threshold
            )
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        logic_domain = next(d for d in result.domains if d.domain == "logic")
        assert logic_domain.total_calibrated == 40
        assert logic_domain.well_calibrated == 0
        assert logic_domain.is_ready is False

    async def test_items_at_threshold_included(self, db_session: AsyncSession):
        """Items with SE exactly at threshold are included."""
        q_type = QuestionType.MATH
        _populate_domain_ready(db_session, q_type)

        # Add items exactly at SE thresholds
        _create_calibrated_question(
            db_session,
            q_type,
            irt_difficulty=0.0,
            irt_se_difficulty=0.50,  # Exactly at threshold
            irt_se_discrimination=0.30,  # Exactly at threshold
        )
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        math_domain = next(d for d in result.domains if d.domain == "math")
        # 35 from _populate_domain_ready + 1 at threshold = 36
        assert math_domain.well_calibrated == 36


class TestCATReadinessDifficultyBands:
    """Tests for difficulty band coverage requirements."""

    async def test_missing_easy_band_not_ready(self, db_session: AsyncSession):
        """Domain without enough easy items (b < -1.0) is not ready."""
        q_type = QuestionType.SPATIAL

        # Only medium and hard items, no easy
        for i in range(20):
            _create_calibrated_question(
                db_session, q_type, irt_difficulty=0.0 + i * 0.05
            )
        for i in range(15):
            _create_calibrated_question(
                db_session, q_type, irt_difficulty=1.5 + i * 0.1
            )
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        spatial_domain = next(d for d in result.domains if d.domain == "spatial")
        assert spatial_domain.is_ready is False
        assert spatial_domain.easy_count == 0
        assert any("easy" in r.lower() for r in spatial_domain.reasons)

    async def test_missing_hard_band_not_ready(self, db_session: AsyncSession):
        """Domain without enough hard items (b > 1.0) is not ready."""
        q_type = QuestionType.VERBAL

        # Only easy and medium items, no hard
        for i in range(15):
            _create_calibrated_question(
                db_session, q_type, irt_difficulty=-2.0 + i * 0.05
            )
        for i in range(20):
            _create_calibrated_question(
                db_session, q_type, irt_difficulty=-0.8 + i * 0.08
            )
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        verbal_domain = next(d for d in result.domains if d.domain == "verbal")
        assert verbal_domain.is_ready is False
        assert verbal_domain.hard_count == 0
        assert any("hard" in r.lower() for r in verbal_domain.reasons)


class TestCATReadinessItemExclusion:
    """Tests for inactive/flagged item exclusion."""

    async def test_inactive_items_excluded(self, db_session: AsyncSession):
        """Inactive items are not counted toward readiness."""
        q_type = QuestionType.MEMORY

        for i in range(40):
            _create_calibrated_question(
                db_session,
                q_type,
                irt_difficulty=-2.0 + i * 0.1,
                is_active=False,
            )
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        memory_domain = next(d for d in result.domains if d.domain == "memory")
        assert memory_domain.total_calibrated == 0
        assert memory_domain.well_calibrated == 0

    async def test_flagged_items_excluded(self, db_session: AsyncSession):
        """Items with non-normal quality flags are excluded."""
        q_type = QuestionType.PATTERN

        for i in range(20):
            _create_calibrated_question(
                db_session,
                q_type,
                irt_difficulty=-2.0 + i * 0.1,
                quality_flag="under_review",
            )
        for i in range(20):
            _create_calibrated_question(
                db_session,
                q_type,
                irt_difficulty=-2.0 + i * 0.1,
                quality_flag="deactivated",
            )
        await db_session.commit()

        result = await evaluate_cat_readiness(db_session)

        pattern_domain = next(d for d in result.domains if d.domain == "pattern")
        assert pattern_domain.total_calibrated == 0
        assert pattern_domain.well_calibrated == 0
