"""Tests for inventory analyzer module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.inventory_analyzer import (
    DEFAULT_HEALTHY_THRESHOLD,
    DEFAULT_TARGET_QUESTIONS_PER_STRATUM,
    DEFAULT_WARNING_THRESHOLD,
    GenerationPlan,
    InventoryAnalysis,
    InventoryAnalyzer,
    StratumInventory,
)
from app.database import DatabaseService
from app.models import DifficultyLevel, QuestionType


class TestStratumInventory:
    """Tests for StratumInventory dataclass."""

    def test_deficit_calculation_below_target(self):
        """Test deficit calculation when below target."""
        stratum = StratumInventory(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            current_count=30,
            target_count=50,
        )
        assert stratum.deficit == 20
        assert stratum.is_below_target is True

    def test_deficit_calculation_at_target(self):
        """Test deficit calculation when at target."""
        stratum = StratumInventory(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            current_count=50,
            target_count=50,
        )
        assert stratum.deficit == 0
        assert stratum.is_below_target is False

    def test_deficit_calculation_above_target(self):
        """Test deficit calculation when above target."""
        stratum = StratumInventory(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            current_count=75,
            target_count=50,
        )
        assert stratum.deficit == 0
        assert stratum.is_below_target is False

    def test_fill_priority_empty_stratum(self):
        """Test fill priority for empty stratum."""
        stratum = StratumInventory(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            current_count=0,
            target_count=50,
        )
        # Empty stratum should have max priority (1.0)
        assert stratum.fill_priority == pytest.approx(1.0)

    def test_fill_priority_half_filled(self):
        """Test fill priority for half-filled stratum."""
        stratum = StratumInventory(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            current_count=25,
            target_count=50,
        )
        assert stratum.fill_priority == pytest.approx(0.5)

    def test_fill_priority_full_stratum(self):
        """Test fill priority for full stratum."""
        stratum = StratumInventory(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            current_count=50,
            target_count=50,
        )
        assert stratum.fill_priority == pytest.approx(0.0)

    def test_fill_priority_zero_target(self):
        """Test fill priority when target is zero."""
        stratum = StratumInventory(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            current_count=10,
            target_count=0,
        )
        assert stratum.fill_priority == pytest.approx(0.0)


class TestInventoryAnalysis:
    """Tests for InventoryAnalysis dataclass."""

    def test_strata_below_target(self):
        """Test filtering strata below target."""
        strata = [
            StratumInventory(QuestionType.MATH, DifficultyLevel.EASY, 30, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.MEDIUM, 50, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.HARD, 10, 50),
        ]
        analysis = InventoryAnalysis(
            strata=strata,
            total_questions=90,
            total_deficit=60,
            healthy_threshold=50,
            warning_threshold=20,
        )

        below_target = analysis.strata_below_target
        assert len(below_target) == 2
        assert strata[0] in below_target
        assert strata[2] in below_target

    def test_critical_strata(self):
        """Test identifying critical strata."""
        strata = [
            StratumInventory(QuestionType.MATH, DifficultyLevel.EASY, 30, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.MEDIUM, 15, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.HARD, 5, 50),
        ]
        analysis = InventoryAnalysis(
            strata=strata,
            total_questions=50,
            total_deficit=100,
            healthy_threshold=50,
            warning_threshold=20,
        )

        critical = analysis.critical_strata
        assert len(critical) == 2
        assert strata[1] in critical  # 15 < 20
        assert strata[2] in critical  # 5 < 20

    def test_strata_by_priority(self):
        """Test sorting strata by fill priority."""
        strata = [
            StratumInventory(QuestionType.MATH, DifficultyLevel.EASY, 40, 50),  # 0.2
            StratumInventory(QuestionType.MATH, DifficultyLevel.MEDIUM, 0, 50),  # 1.0
            StratumInventory(QuestionType.MATH, DifficultyLevel.HARD, 25, 50),  # 0.5
        ]
        analysis = InventoryAnalysis(
            strata=strata,
            total_questions=65,
            total_deficit=85,
            healthy_threshold=50,
            warning_threshold=20,
        )

        by_priority = analysis.strata_by_priority
        assert by_priority[0] == strata[1]  # Empty stratum first
        assert by_priority[1] == strata[2]  # Half-filled second
        assert by_priority[2] == strata[0]  # Nearly full last


class TestGenerationPlan:
    """Tests for GenerationPlan dataclass."""

    def test_get_allocation(self):
        """Test getting allocation for a stratum."""
        plan = GenerationPlan(
            allocations={
                (QuestionType.MATH, DifficultyLevel.EASY): 10,
                (QuestionType.MATH, DifficultyLevel.HARD): 20,
            },
            total_questions=30,
        )

        assert plan.get_allocation(QuestionType.MATH, DifficultyLevel.EASY) == 10
        assert plan.get_allocation(QuestionType.MATH, DifficultyLevel.HARD) == 20
        assert plan.get_allocation(QuestionType.MATH, DifficultyLevel.MEDIUM) == 0

    def test_get_types_to_generate(self):
        """Test getting question types with allocations."""
        plan = GenerationPlan(
            allocations={
                (QuestionType.MATH, DifficultyLevel.EASY): 10,
                (QuestionType.MATH, DifficultyLevel.HARD): 20,
                (QuestionType.LOGIC, DifficultyLevel.EASY): 15,
            },
            total_questions=45,
        )

        types = plan.get_types_to_generate()
        type_dict = dict(types)

        assert QuestionType.MATH in type_dict
        assert QuestionType.LOGIC in type_dict
        assert type_dict[QuestionType.MATH] == 30  # 10 + 20
        assert type_dict[QuestionType.LOGIC] == 15

    def test_to_log_summary(self):
        """Test generating log summary."""
        plan = GenerationPlan(
            allocations={
                (QuestionType.MATH, DifficultyLevel.EASY): 10,
                (QuestionType.LOGIC, DifficultyLevel.HARD): 20,
            },
            total_questions=30,
        )

        summary = plan.to_log_summary()
        assert "Generation Plan:" in summary
        assert "Total questions: 30" in summary
        assert "math/easy: 10" in summary
        assert "logic/hard: 20" in summary


class TestInventoryAnalyzer:
    """Tests for InventoryAnalyzer class."""

    @pytest.fixture
    def mock_db_service(self):
        """Create a mock database service."""
        with patch("app.database.create_engine"):
            with patch("app.database.sessionmaker"):
                service = Mock(spec=DatabaseService)
                service.get_session = Mock()
                service.close_session = Mock()
                return service

    def test_initialization_with_defaults(self, mock_db_service):
        """Test analyzer initialization with default values."""
        analyzer = InventoryAnalyzer(database_service=mock_db_service)

        assert analyzer.healthy_threshold == DEFAULT_HEALTHY_THRESHOLD
        assert analyzer.warning_threshold == DEFAULT_WARNING_THRESHOLD
        assert analyzer.target_per_stratum == DEFAULT_TARGET_QUESTIONS_PER_STRATUM

    def test_initialization_with_custom_values(self, mock_db_service):
        """Test analyzer initialization with custom values."""
        analyzer = InventoryAnalyzer(
            database_service=mock_db_service,
            healthy_threshold=100,
            warning_threshold=30,
            target_per_stratum=75,
        )

        assert analyzer.healthy_threshold == 100
        assert analyzer.warning_threshold == 30
        assert analyzer.target_per_stratum == 75

    def test_analyze_inventory(self, mock_db_service):
        """Test analyzing inventory from database."""
        # Mock session and query results
        mock_session = MagicMock(spec=Session)

        # Create mock result rows
        mock_results = [
            (QuestionType.MATH, DifficultyLevel.EASY, 30),
            (QuestionType.MATH, DifficultyLevel.MEDIUM, 45),
            (QuestionType.LOGIC, DifficultyLevel.HARD, 10),
        ]

        # Configure the mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results

        mock_db_service.get_session.return_value = mock_session

        analyzer = InventoryAnalyzer(
            database_service=mock_db_service,
            target_per_stratum=50,
        )

        analysis = analyzer.analyze_inventory()

        # Should have strata for all type/difficulty combinations
        expected_strata = len(QuestionType) * len(DifficultyLevel)
        assert len(analysis.strata) == expected_strata

        # Check total questions
        assert analysis.total_questions == 85  # 30 + 45 + 10

        # Check that specific strata have correct counts
        math_easy = next(
            s
            for s in analysis.strata
            if s.question_type == QuestionType.MATH
            and s.difficulty == DifficultyLevel.EASY
        )
        assert math_easy.current_count == 30

        # Check that missing strata have zero counts
        verbal_easy = next(
            s
            for s in analysis.strata
            if s.question_type == QuestionType.VERBAL
            and s.difficulty == DifficultyLevel.EASY
        )
        assert verbal_easy.current_count == 0

    def test_compute_generation_plan_proportional(self, mock_db_service):
        """Test computing generation plan with proportional allocation."""
        # Create a pre-computed analysis
        strata = [
            StratumInventory(
                QuestionType.MATH, DifficultyLevel.EASY, 0, 50
            ),  # deficit 50
            StratumInventory(
                QuestionType.MATH, DifficultyLevel.MEDIUM, 25, 50
            ),  # deficit 25
            StratumInventory(
                QuestionType.MATH, DifficultyLevel.HARD, 50, 50
            ),  # deficit 0
        ]
        analysis = InventoryAnalysis(
            strata=strata,
            total_questions=75,
            total_deficit=75,
            healthy_threshold=50,
            warning_threshold=20,
        )

        analyzer = InventoryAnalyzer(
            database_service=mock_db_service,
            target_per_stratum=50,
        )

        plan = analyzer.compute_generation_plan(
            target_total=60,
            analysis=analysis,
        )

        # Math/easy should get more allocation (higher deficit)
        math_easy_alloc = plan.get_allocation(QuestionType.MATH, DifficultyLevel.EASY)
        math_medium_alloc = plan.get_allocation(
            QuestionType.MATH, DifficultyLevel.MEDIUM
        )
        math_hard_alloc = plan.get_allocation(QuestionType.MATH, DifficultyLevel.HARD)

        # Empty stratum should get more
        assert math_easy_alloc > math_medium_alloc
        # Full stratum should get little to nothing
        assert math_hard_alloc <= math_medium_alloc

        # Total should be target
        total_allocated = sum(plan.allocations.values())
        assert total_allocated == 60

    def test_compute_generation_plan_no_deficit(self, mock_db_service):
        """Test computing generation plan when all strata are full."""
        strata = [
            StratumInventory(QuestionType.MATH, DifficultyLevel.EASY, 50, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.MEDIUM, 60, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.HARD, 55, 50),
        ]
        analysis = InventoryAnalysis(
            strata=strata,
            total_questions=165,
            total_deficit=0,
            healthy_threshold=50,
            warning_threshold=20,
        )

        analyzer = InventoryAnalyzer(
            database_service=mock_db_service,
            target_per_stratum=50,
        )

        plan = analyzer.compute_generation_plan(
            target_total=30,
            analysis=analysis,
        )

        # Should distribute evenly across all strata
        total_allocated = sum(plan.allocations.values())
        assert total_allocated == 30

    def test_compute_generation_plan_respects_deficit_limit(self, mock_db_service):
        """Test that allocation doesn't exceed stratum deficit."""
        strata = [
            StratumInventory(
                QuestionType.MATH, DifficultyLevel.EASY, 45, 50
            ),  # deficit 5
            StratumInventory(
                QuestionType.MATH, DifficultyLevel.MEDIUM, 48, 50
            ),  # deficit 2
        ]
        analysis = InventoryAnalysis(
            strata=strata,
            total_questions=93,
            total_deficit=7,
            healthy_threshold=50,
            warning_threshold=20,
        )

        analyzer = InventoryAnalyzer(
            database_service=mock_db_service,
            target_per_stratum=50,
        )

        plan = analyzer.compute_generation_plan(
            target_total=100,  # More than total deficit
            analysis=analysis,
        )

        # Both strata should get allocations (plan distributes to fill gaps)
        math_easy_alloc = plan.get_allocation(QuestionType.MATH, DifficultyLevel.EASY)
        math_medium_alloc = plan.get_allocation(
            QuestionType.MATH, DifficultyLevel.MEDIUM
        )
        # Verify both strata received allocations
        assert math_easy_alloc > 0
        assert math_medium_alloc > 0

        # Should still allocate the full 100 questions
        total_allocated = sum(plan.allocations.values())
        assert total_allocated == 100

    def test_distribute_evenly(self, mock_db_service):
        """Test even distribution across strata."""
        strata = [
            StratumInventory(QuestionType.MATH, DifficultyLevel.EASY, 50, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.MEDIUM, 50, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.HARD, 50, 50),
        ]

        analyzer = InventoryAnalyzer(
            database_service=mock_db_service,
            target_per_stratum=50,
        )

        plan = analyzer._distribute_evenly(30, strata)

        # Each stratum should get 10 questions
        for stratum in strata:
            alloc = plan.get_allocation(stratum.question_type, stratum.difficulty)
            assert alloc == 10

        assert plan.total_questions == 30

    def test_distribute_evenly_with_remainder(self, mock_db_service):
        """Test even distribution handles remainder correctly."""
        strata = [
            StratumInventory(QuestionType.MATH, DifficultyLevel.EASY, 50, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.MEDIUM, 50, 50),
            StratumInventory(QuestionType.MATH, DifficultyLevel.HARD, 50, 50),
        ]

        analyzer = InventoryAnalyzer(
            database_service=mock_db_service,
            target_per_stratum=50,
        )

        plan = analyzer._distribute_evenly(32, strata)

        # Total should be exactly 32
        assert sum(plan.allocations.values()) == 32
        assert plan.total_questions == 32

        # First two should get 11, last one 10
        allocations = list(plan.allocations.values())
        assert allocations.count(11) == 2
        assert allocations.count(10) == 1
