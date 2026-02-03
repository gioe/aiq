"""
CATSessionManager: Orchestrator for adaptive test sessions (TASK-864).

Manages item selection, ability estimation (EAP), and stopping criteria during
a Computerized Adaptive Testing (CAT) session. The engine is stateless between
requests—all state is stored in the CATSession object.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.cat.ability_estimation import estimate_ability_eap
from app.core.cat.item_selection import fisher_information_2pl
from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.core.scoring import IQ_CI_LOWER_BOUND, IQ_CI_UPPER_BOUND, IQ_POPULATION_SD
from app.models.models import QuestionType

logger = logging.getLogger(__name__)


@dataclass
class ItemResponse:
    """Single item response during a CAT session."""

    question_id: int
    is_correct: bool
    irt_difficulty: float  # b parameter
    irt_discrimination: float  # a parameter
    question_type: str  # Domain (e.g., "pattern", "logic")


@dataclass
class CATSession:
    """In-memory representation of an adaptive test session."""

    user_id: int
    session_id: int
    theta_estimate: float  # Current ability estimate
    theta_se: float  # Standard error of theta
    administered_items: List[int]  # Question IDs already shown
    responses: List[ItemResponse]  # Response history
    domain_coverage: Dict[str, int]  # Domain → count of items shown
    correct_count: int  # Total correct responses
    started_at: datetime


@dataclass
class CATStepResult:
    """Result after processing a single response."""

    theta_estimate: float
    theta_se: float
    correct_count: int
    items_administered: int
    should_stop: bool
    stop_reason: Optional[str]


@dataclass
class CATResult:
    """Final test result summary."""

    theta_estimate: float
    theta_se: float
    iq_score: int
    correct_count: int
    items_administered: int
    domain_scores: Dict[str, Dict[str, Any]]
    stop_reason: str


class CATSessionManager:
    """
    Orchestrator for Computerized Adaptive Testing sessions.

    Manages:
    - Session initialization with prior ability estimates
    - Response processing and ability re-estimation using EAP
    - Stopping criteria evaluation (SE threshold, min/max items)
    - Content balancing across cognitive domains
    - Final result calculation and IQ score conversion
    """

    # CAT configuration constants
    SE_THRESHOLD = 0.30  # Target precision for stopping
    MIN_ITEMS = 8  # Minimum items before stopping allowed
    MAX_ITEMS = 15  # Maximum items (safety limit)
    MIN_ITEMS_PER_DOMAIN = 2  # Hard constraint per domain
    DOMAIN_WEIGHT_TOLERANCE = 0.10  # ±10% soft constraint (used by item selection)
    PRIOR_THETA = 0.0  # Default prior ability
    PRIOR_SE = 1.0  # Default prior SE
    IQ_MEAN = 100  # IQ scale mean (Wechsler convention)

    def __init__(self):
        """Initialize CATSessionManager with domain weights from settings."""
        self.domain_weights = settings.TEST_DOMAIN_WEIGHTS

        # Validate domain weights
        expected_domains = {qt.value for qt in QuestionType}
        if set(self.domain_weights.keys()) != expected_domains:
            raise ValueError(
                f"Domain weights must include all question types: {expected_domains}"
            )

        logger.info(
            f"CATSessionManager initialized with domain weights: {self.domain_weights}"
        )

    def initialize(
        self,
        user_id: int,
        session_id: int,
        prior_theta: Optional[float] = None,
    ) -> CATSession:
        """
        Create a new CATSession with default or custom prior ability.

        Args:
            user_id: ID of the user taking the test
            session_id: ID of the test session
            prior_theta: Optional prior ability estimate (defaults to 0.0)

        Returns:
            CATSession with initial state
        """
        theta = prior_theta if prior_theta is not None else self.PRIOR_THETA

        # Initialize domain coverage with all 6 domains at 0
        domain_coverage = {domain: 0 for domain in self.domain_weights.keys()}

        session = CATSession(
            user_id=user_id,
            session_id=session_id,
            theta_estimate=theta,
            theta_se=self.PRIOR_SE,
            administered_items=[],
            responses=[],
            domain_coverage=domain_coverage,
            correct_count=0,
            started_at=utc_now(),
        )

        logger.info(
            f"Initialized CAT session {session_id} for user {user_id} "
            f"with prior theta={theta:.3f}"
        )

        return session

    def process_response(
        self,
        session: CATSession,
        question_id: int,
        is_correct: bool,
        question_type: str,
        irt_difficulty: float,
        irt_discrimination: float,
    ) -> CATStepResult:
        """
        Process a single response and update the session state.

        This method mutates the session in-place:
        - Adds the response to the response history
        - Updates domain coverage
        - Updates correct count
        - Re-estimates theta using EAP
        - Checks stopping criteria

        Args:
            session: The current CATSession (mutated in-place)
            question_id: ID of the question being answered
            is_correct: Whether the response was correct
            question_type: Domain of the question (e.g., "pattern", "logic")
            irt_difficulty: IRT b parameter for the item
            irt_discrimination: IRT a parameter for the item

        Returns:
            CATStepResult with updated estimates and stopping decision
        """
        if irt_discrimination <= 0:
            raise ValueError(
                f"irt_discrimination must be positive, got {irt_discrimination} "
                f"for question {question_id}"
            )

        # Record the response
        response = ItemResponse(
            question_id=question_id,
            is_correct=is_correct,
            irt_difficulty=irt_difficulty,
            irt_discrimination=irt_discrimination,
            question_type=question_type,
        )
        session.responses.append(response)
        session.administered_items.append(question_id)

        # Update domain coverage
        if question_type not in session.domain_coverage:
            raise ValueError(
                f"Unknown question type '{question_type}' for question {question_id}. "
                f"Expected one of: {list(session.domain_coverage.keys())}"
            )
        session.domain_coverage[question_type] += 1

        # Update correct count
        if is_correct:
            session.correct_count += 1

        # Re-estimate theta using EAP with current responses
        theta_estimate, theta_se = self.estimate_theta_eap(
            responses=session.responses,
            prior_mean=self.PRIOR_THETA,
            prior_sd=self.PRIOR_SE,
        )

        # Update session with new estimates
        session.theta_estimate = theta_estimate
        session.theta_se = theta_se

        # Check stopping criteria
        should_stop, stop_reason = self.should_stop(session)

        items_administered = len(session.administered_items)

        logger.debug(
            f"Session {session.session_id}: Response #{items_administered} "
            f"(Q{question_id}, correct={is_correct}) -> "
            f"theta={theta_estimate:.3f}, SE={theta_se:.3f}, "
            f"stop={should_stop}"
        )

        return CATStepResult(
            theta_estimate=theta_estimate,
            theta_se=theta_se,
            correct_count=session.correct_count,
            items_administered=items_administered,
            should_stop=should_stop,
            stop_reason=stop_reason,
        )

    def estimate_theta_eap(
        self,
        responses: List[ItemResponse],
        prior_mean: float = 0.0,
        prior_sd: float = 1.0,
    ) -> Tuple[float, float]:
        """
        Estimate ability using Expected A Posteriori (EAP) with numerical quadrature.

        Delegates to the standalone ``estimate_ability_eap`` function in
        ``ability_estimation.py``, converting ItemResponse objects to the
        (a, b, is_correct) tuple format expected by that module.

        Args:
            responses: List of item responses with IRT parameters
            prior_mean: Mean of the prior distribution (default 0.0)
            prior_sd: Standard deviation of the prior distribution (default 1.0)

        Returns:
            Tuple of (theta_estimate, theta_se)
        """
        # Convert ItemResponse objects to (a, b, is_correct) tuples
        response_tuples = [
            (r.irt_discrimination, r.irt_difficulty, r.is_correct) for r in responses
        ]
        return estimate_ability_eap(response_tuples, prior_mean, prior_sd)

    def should_stop(self, session: CATSession) -> Tuple[bool, Optional[str]]:
        """
        Determine whether the test should stop based on stopping criteria.

        Stopping rules (evaluated in order):
        1. If items < MIN_ITEMS: continue testing (False, None)
        2. If items >= MAX_ITEMS: stop immediately (True, "max_items")
        3. If content balance not met: continue testing (False, None)
        4. If SE < SE_THRESHOLD: stop due to sufficient precision (True, "se_threshold")
        5. Otherwise: continue testing (False, None)

        Args:
            session: The current CATSession

        Returns:
            Tuple of (should_stop, stop_reason)
        """
        items_administered = len(session.administered_items)

        # Rule 1: Minimum items required
        if items_administered < self.MIN_ITEMS:
            return (False, None)

        # Rule 2: Maximum items (safety limit — overrides all other rules)
        if items_administered >= self.MAX_ITEMS:
            logger.info(
                f"Session {session.session_id}: Stopping due to max items "
                f"({items_administered}/{self.MAX_ITEMS})"
            )
            return (True, "max_items")

        # Rule 3: Content balance must be satisfied before SE-based stopping
        if not self._check_content_balance(session):
            return (False, None)

        # Rule 4: SE threshold (sufficient precision)
        if session.theta_se < self.SE_THRESHOLD:
            logger.info(
                f"Session {session.session_id}: Stopping due to SE threshold "
                f"(SE={session.theta_se:.3f} < {self.SE_THRESHOLD})"
            )
            return (True, "se_threshold")

        # Continue testing
        return (False, None)

    def _check_content_balance(self, session: CATSession) -> bool:
        """
        Check if each domain has at least MIN_ITEMS_PER_DOMAIN items.

        This is a hard constraint for content validity. The test should not
        stop until all domains have sufficient coverage.

        Args:
            session: The current CATSession

        Returns:
            True if content balance is satisfied, False otherwise
        """
        for domain, count in session.domain_coverage.items():
            if count < self.MIN_ITEMS_PER_DOMAIN:
                logger.debug(
                    f"Session {session.session_id}: Domain '{domain}' has insufficient items "
                    f"({count}/{self.MIN_ITEMS_PER_DOMAIN})"
                )
                return False
        return True

    def calculate_fisher_information(
        self,
        theta: float,
        irt_difficulty: float,
        irt_discrimination: float,
    ) -> float:
        """
        Calculate Fisher information for a 2PL IRT item at a given ability level.

        Delegates to the standalone ``fisher_information_2pl`` function in
        ``item_selection.py``.

        Args:
            theta: Ability level
            irt_difficulty: IRT b parameter
            irt_discrimination: IRT a parameter

        Returns:
            Fisher information value (non-negative)
        """
        return fisher_information_2pl(theta, irt_discrimination, irt_difficulty)

    def finalize(self, session: CATSession, stop_reason: str) -> CATResult:
        """
        Finalize the test session and calculate the final result.

        Converts theta to IQ score and calculates domain-level statistics.

        IQ conversion:
            IQ = 100 + (θ × 15)

        Where:
            θ = ability estimate (mean 0, SD 1)
            15 = IQ standard deviation (traditional Wechsler scale)
            100 = IQ mean

        IQ is clamped to [40, 160] to avoid extreme values.

        Args:
            session: The completed CATSession
            stop_reason: Reason for stopping (e.g., "se_threshold", "max_items")

        Returns:
            CATResult with final scores and statistics
        """
        # Convert theta to IQ: IQ = mean + (theta × SD)
        raw_iq = self.IQ_MEAN + (session.theta_estimate * IQ_POPULATION_SD)

        # Clamp IQ to valid range
        iq_score = int(max(IQ_CI_LOWER_BOUND, min(IQ_CI_UPPER_BOUND, round(raw_iq))))

        # Calculate domain scores from response history
        domain_scores: Dict[str, Dict[str, Any]] = {}
        for domain in session.domain_coverage:
            domain_responses = [
                r for r in session.responses if r.question_type == domain
            ]
            domain_correct = sum(1 for r in domain_responses if r.is_correct)
            domain_total = len(domain_responses)
            domain_accuracy = domain_correct / domain_total if domain_total > 0 else 0.0
            domain_scores[domain] = {
                "items_administered": domain_total,
                "correct_count": domain_correct,
                "accuracy": round(domain_accuracy, 3),
            }

        logger.info(
            f"Session {session.session_id} finalized: "
            f"theta={session.theta_estimate:.3f}, SE={session.theta_se:.3f}, "
            f"IQ={iq_score}, items={len(session.administered_items)}, "
            f"correct={session.correct_count}, stop_reason={stop_reason}"
        )

        return CATResult(
            theta_estimate=session.theta_estimate,
            theta_se=session.theta_se,
            iq_score=iq_score,
            correct_count=session.correct_count,
            items_administered=len(session.administered_items),
            domain_scores=domain_scores,
            stop_reason=stop_reason,
        )
