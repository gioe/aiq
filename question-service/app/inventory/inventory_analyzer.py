"""Inventory analysis for intelligent question generation balancing.

This module provides functionality to analyze current question inventory
levels and compute balanced generation targets to fill gaps across
question type and difficulty strata.

Used by run_generation.py with --auto-balance flag to prioritize
generation for underrepresented strata.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func

from app.data.database import DatabaseService, QuestionModel
from app.data.models import DifficultyLevel, QuestionType

logger = logging.getLogger(__name__)

# Default thresholds for inventory health assessment
# These match the backend inventory health endpoint defaults
DEFAULT_HEALTHY_THRESHOLD = 50  # Questions per stratum for healthy status
DEFAULT_WARNING_THRESHOLD = 20  # Below this is critical

# Configuration for balancing algorithm
DEFAULT_TARGET_QUESTIONS_PER_STRATUM = 50  # Target inventory level


@dataclass
class StratumInventory:
    """Inventory status for a single question type/difficulty stratum."""

    question_type: QuestionType
    difficulty: DifficultyLevel
    current_count: int
    target_count: int = DEFAULT_TARGET_QUESTIONS_PER_STRATUM

    @property
    def deficit(self) -> int:
        """Return the number of questions needed to reach target."""
        return max(0, self.target_count - self.current_count)

    @property
    def is_below_target(self) -> bool:
        """Check if stratum is below target level."""
        return self.current_count < self.target_count

    @property
    def fill_priority(self) -> float:
        """Calculate priority score for filling this stratum.

        Higher values indicate higher priority. Strata with larger deficits
        relative to their target get higher priority.

        Returns:
            float: Priority score between 0.0 and 1.0
        """
        if self.target_count == 0:
            return 0.0
        # Deficit as proportion of target, capped at 1.0
        return min(1.0, self.deficit / self.target_count)


@dataclass
class InventoryAnalysis:
    """Complete inventory analysis with generation recommendations."""

    strata: List[StratumInventory]
    total_questions: int
    total_deficit: int
    healthy_threshold: int
    warning_threshold: int

    @property
    def strata_below_target(self) -> List[StratumInventory]:
        """Get strata that are below their target counts."""
        return [s for s in self.strata if s.is_below_target]

    @property
    def critical_strata(self) -> List[StratumInventory]:
        """Get strata that are in critical state (below warning threshold)."""
        return [s for s in self.strata if s.current_count < self.warning_threshold]

    @property
    def strata_by_priority(self) -> List[StratumInventory]:
        """Get strata sorted by fill priority (highest priority first)."""
        return sorted(self.strata, key=lambda s: s.fill_priority, reverse=True)


@dataclass
class GenerationPlan:
    """Plan for balanced question generation."""

    allocations: Dict[Tuple[QuestionType, DifficultyLevel], int] = field(
        default_factory=dict
    )
    total_questions: int = 0

    def get_allocation(
        self, question_type: QuestionType, difficulty: DifficultyLevel
    ) -> int:
        """Get the number of questions allocated to a stratum."""
        return self.allocations.get((question_type, difficulty), 0)

    def get_types_to_generate(self) -> List[Tuple[QuestionType, int]]:
        """Get question types with their total allocations.

        Returns:
            List of (question_type, count) tuples for types that have allocations
        """
        type_totals: Dict[QuestionType, int] = {}
        for (q_type, _), count in self.allocations.items():
            type_totals[q_type] = type_totals.get(q_type, 0) + count

        return [(q_type, count) for q_type, count in type_totals.items() if count > 0]

    def to_log_summary(self) -> str:
        """Generate a human-readable summary of the generation plan."""
        lines = ["Generation Plan:"]
        lines.append(f"  Total questions: {self.total_questions}")
        lines.append("  Allocations by stratum:")

        for (q_type, difficulty), count in sorted(
            self.allocations.items(),
            key=lambda x: (-x[1], x[0][0].value, x[0][1].value),
        ):
            if count > 0:
                lines.append(f"    {q_type.value}/{difficulty.value}: {count}")

        return "\n".join(lines)


class InventoryAnalyzer:
    """Analyzes question inventory and computes balanced generation targets.

    This class queries the database to assess current inventory levels
    and provides recommendations for balanced question generation.

    Example usage:
        analyzer = InventoryAnalyzer(database_service)
        analysis = analyzer.analyze_inventory()

        # Get generation plan for 100 questions
        plan = analyzer.compute_generation_plan(
            target_total=100,
            analysis=analysis
        )
    """

    def __init__(
        self,
        database_service: DatabaseService,
        healthy_threshold: int = DEFAULT_HEALTHY_THRESHOLD,
        warning_threshold: int = DEFAULT_WARNING_THRESHOLD,
        target_per_stratum: int = DEFAULT_TARGET_QUESTIONS_PER_STRATUM,
    ):
        """Initialize the inventory analyzer.

        Args:
            database_service: Database service for querying inventory
            healthy_threshold: Minimum count for healthy status
            warning_threshold: Minimum count for warning status (below is critical)
            target_per_stratum: Target inventory level per stratum
        """
        self.db = database_service
        self.healthy_threshold = healthy_threshold
        self.warning_threshold = warning_threshold
        self.target_per_stratum = target_per_stratum

    def analyze_inventory(self) -> InventoryAnalysis:
        """Analyze current inventory levels across all strata.

        Returns:
            InventoryAnalysis with complete inventory breakdown

        Raises:
            Exception: If database query fails
        """
        session = self.db.get_session()
        try:
            # Query database for active question counts grouped by type and difficulty
            # Only count questions where is_active == True (deactivated questions are excluded)
            stratum_counts = (
                session.query(
                    QuestionModel.question_type,
                    QuestionModel.difficulty_level,
                    func.count(QuestionModel.id).label("count"),
                )
                .filter(
                    QuestionModel.is_active == True,  # noqa: E712
                )
                .group_by(QuestionModel.question_type, QuestionModel.difficulty_level)
                .all()
            )

            # Build count map
            count_map: Dict[Tuple[str, str], int] = {}
            for row in stratum_counts:
                # Handle both enum and string types from the database
                q_type = row[0].value if hasattr(row[0], "value") else str(row[0])
                diff = row[1].value if hasattr(row[1], "value") else str(row[1])
                count_map[(q_type, diff)] = row[2]

            # Generate complete stratum list with all combinations
            strata: List[StratumInventory] = []
            total_questions = 0
            total_deficit = 0

            for q_type in QuestionType:
                for difficulty in DifficultyLevel:
                    count = count_map.get((q_type.value, difficulty.value), 0)
                    stratum = StratumInventory(
                        question_type=q_type,
                        difficulty=difficulty,
                        current_count=count,
                        target_count=self.target_per_stratum,
                    )
                    strata.append(stratum)
                    total_questions += count
                    total_deficit += stratum.deficit

            logger.info(
                f"Inventory analysis complete: {total_questions} total questions, "
                f"{total_deficit} total deficit across {len(strata)} strata"
            )

            return InventoryAnalysis(
                strata=strata,
                total_questions=total_questions,
                total_deficit=total_deficit,
                healthy_threshold=self.healthy_threshold,
                warning_threshold=self.warning_threshold,
            )

        finally:
            self.db.close_session(session)

    def compute_generation_plan(
        self,
        target_total: int,
        analysis: Optional[InventoryAnalysis] = None,
        min_per_stratum: int = 0,
    ) -> GenerationPlan:
        """Compute a balanced generation plan based on inventory gaps.

        The algorithm prioritizes strata with larger deficits, allocating
        questions proportionally to fill gaps efficiently.

        Args:
            target_total: Total number of questions to generate
            analysis: Pre-computed inventory analysis (will compute if not provided)
            min_per_stratum: Minimum questions to allocate per stratum (0 = no minimum)

        Returns:
            GenerationPlan with allocations per stratum
        """
        if analysis is None:
            analysis = self.analyze_inventory()

        plan = GenerationPlan()
        remaining = target_total

        # If no deficit, distribute evenly across all strata
        if analysis.total_deficit == 0:
            logger.info(
                "No inventory deficit - distributing questions evenly across strata"
            )
            return self._distribute_evenly(target_total, analysis.strata)

        # Get strata sorted by priority (highest deficit ratio first)
        priority_strata = analysis.strata_by_priority

        # Phase 1: Allocate proportionally based on deficit
        for stratum in priority_strata:
            if remaining <= 0:
                break

            if stratum.deficit == 0:
                continue

            # Allocate proportionally to deficit
            proportion = stratum.deficit / analysis.total_deficit
            allocation = int(target_total * proportion)

            # Don't allocate more than the deficit
            allocation = min(allocation, stratum.deficit)
            # Don't exceed remaining
            allocation = max(min_per_stratum, min(allocation, remaining))

            if allocation > 0:
                key = (stratum.question_type, stratum.difficulty)
                plan.allocations[key] = allocation
                remaining -= allocation

        # Phase 2: Distribute any remaining questions to strata with deficits
        if remaining > 0:
            for stratum in priority_strata:
                if remaining <= 0:
                    break

                if stratum.deficit == 0:
                    continue

                key = (stratum.question_type, stratum.difficulty)
                current_allocation = plan.allocations.get(key, 0)
                additional = min(remaining, stratum.deficit - current_allocation)

                if additional > 0:
                    plan.allocations[key] = current_allocation + additional
                    remaining -= additional

        # Phase 3: If still remaining, distribute to any stratum
        if remaining > 0:
            strata_cycle = priority_strata[:]
            idx = 0
            while remaining > 0 and strata_cycle:
                stratum = strata_cycle[idx % len(strata_cycle)]
                key = (stratum.question_type, stratum.difficulty)
                plan.allocations[key] = plan.allocations.get(key, 0) + 1
                remaining -= 1
                idx += 1

        plan.total_questions = target_total - remaining

        logger.info(
            f"Generation plan computed: {plan.total_questions} questions "
            f"across {len([a for a in plan.allocations.values() if a > 0])} strata"
        )
        logger.debug(plan.to_log_summary())

        return plan

    def _distribute_evenly(
        self, target_total: int, strata: List[StratumInventory]
    ) -> GenerationPlan:
        """Distribute questions evenly across all strata.

        Args:
            target_total: Total questions to distribute
            strata: List of strata to distribute across

        Returns:
            GenerationPlan with even distribution
        """
        plan = GenerationPlan()
        num_strata = len(strata)

        if num_strata == 0:
            return plan

        base_allocation = target_total // num_strata
        extra = target_total % num_strata

        for i, stratum in enumerate(strata):
            allocation = base_allocation + (1 if i < extra else 0)
            if allocation > 0:
                plan.allocations[(stratum.question_type, stratum.difficulty)] = (
                    allocation
                )

        plan.total_questions = target_total
        return plan

    def log_inventory_summary(self, analysis: InventoryAnalysis) -> None:
        """Log a summary of inventory status.

        Args:
            analysis: Inventory analysis to summarize
        """
        logger.info("=" * 60)
        logger.info("INVENTORY ANALYSIS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total active questions: {analysis.total_questions}")
        logger.info(f"Total deficit: {analysis.total_deficit}")
        logger.info(f"Strata below target: {len(analysis.strata_below_target)}")
        logger.info(f"Critical strata: {len(analysis.critical_strata)}")

        if analysis.critical_strata:
            logger.warning("Critical strata (immediate attention needed):")
            for stratum in analysis.critical_strata:
                logger.warning(
                    f"  {stratum.question_type.value}/{stratum.difficulty.value}: "
                    f"{stratum.current_count} questions (deficit: {stratum.deficit})"
                )

        logger.info("-" * 60)
        logger.info("Inventory by stratum:")
        for stratum in sorted(
            analysis.strata,
            key=lambda s: (s.question_type.value, s.difficulty.value),
        ):
            status = "OK" if stratum.current_count >= self.healthy_threshold else "LOW"
            if stratum.current_count < self.warning_threshold:
                status = "CRITICAL"
            logger.info(
                f"  {stratum.question_type.value}/{stratum.difficulty.value}: "
                f"{stratum.current_count} [{status}]"
            )
        logger.info("=" * 60)
