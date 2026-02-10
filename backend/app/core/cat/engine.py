"""
CATSessionManager: Orchestrator for adaptive test sessions (TASK-864).

Manages item selection, ability estimation (EAP), and stopping criteria during
a Computerized Adaptive Testing (CAT) session. The engine is stateless between
requests—all state is stored in the CATSession object.
"""
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.cat.ability_estimation import estimate_ability_eap
from app.core.cat.item_selection import fisher_information_2pl
from app.core.cat.stopping_rules import check_stopping_criteria
from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.core.scoring import IQ_CI_LOWER_BOUND, IQ_CI_UPPER_BOUND, IQ_POPULATION_SD
from app.models.models import QuestionType

logger = logging.getLogger(__name__)


def compute_prior_theta(
    previous_thetas: List[float],
    previous_ses: List[float],
    include_abandoned: bool = True,
    min_items_for_abandoned: int = 5,
) -> tuple[float, float]:
    """
    Compute a prior ability estimate from a user's previous test sessions.

    Uses precision-weighted averaging of previous theta estimates, where
    precision = 1/SE². This gives more weight to sessions with lower SE
    (more items administered, better estimate quality).

    Abandoned sessions are included if they have enough items for a
    meaningful estimate (controlled by min_items_for_abandoned, which
    should be checked by the caller when filtering sessions).

    Args:
        previous_thetas: List of final theta estimates from past sessions.
        previous_ses: List of corresponding SE values. Must be same length
            as previous_thetas and all values must be positive.
        include_abandoned: Whether abandoned session data was included
            (informational only; filtering happens at the caller level).
        min_items_for_abandoned: Minimum items an abandoned session must
            have to be included (informational; enforced by caller).

    Returns:
        Tuple of (prior_mean, prior_sd) for initializing a new CAT session.
        If no valid sessions are provided, returns the population prior (0.0, 1.0).
    """
    if not previous_thetas or not previous_ses:
        return (0.0, 1.0)

    if len(previous_thetas) != len(previous_ses):
        raise ValueError(
            f"previous_thetas length ({len(previous_thetas)}) must match "
            f"previous_ses length ({len(previous_ses)})"
        )

    # Precision-weighted average: weight_i = 1 / SE_i^2
    total_precision = 0.0
    weighted_sum = 0.0
    for theta, se in zip(previous_thetas, previous_ses):
        if se <= 0:
            logger.warning(f"Skipping session with non-positive SE: {se}")
            continue
        precision = 1.0 / (se**2)
        total_precision += precision
        weighted_sum += theta * precision

    if total_precision == 0:
        return (0.0, 1.0)

    prior_mean = weighted_sum / total_precision
    prior_sd = 1.0 / math.sqrt(total_precision)

    # Clamp to reasonable bounds
    prior_mean = max(-3.0, min(3.0, prior_mean))
    prior_sd = max(0.1, min(1.0, prior_sd))

    return (prior_mean, prior_sd)


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
    # Theta estimate recorded after each item response. Used by the theta_stable
    # stopping criterion to detect convergence (|theta_t - theta_{t-1}| < threshold).
    # Design: stored as a flat list rather than a rolling window because:
    # 1. Full history enables post-hoc analysis of convergence trajectories
    # 2. Max length is bounded by MAX_ITEMS (15), so memory is trivial
    # 3. Persisted to TestSession.theta_history for shadow CAT comparison
    theta_history: List[float] = field(default_factory=list)


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
    # Stopping requires >= 1 item per domain (relaxed from item selection's 2).
    # Item selection still prioritizes underrepresented domains via
    # content_balancing.MIN_ITEMS_PER_DOMAIN=2, so in practice most tests
    # will have >= 2 per domain. The stopping threshold of 1 prevents blocking
    # when a domain has limited calibrated items in the pool.
    MIN_ITEMS_PER_DOMAIN = 1
    DOMAIN_WEIGHT_TOLERANCE = 0.10  # ±10% soft constraint (used by item selection)
    PRIOR_THETA = 0.0  # Default prior ability
    PRIOR_SE = 1.0  # Default prior SE
    IQ_MEAN = 100  # IQ scale mean (Wechsler convention)
    DELTA_THETA_THRESHOLD = 0.03  # Max theta change for convergence
    SE_STABILIZATION_THRESHOLD = (
        0.35  # SE must be below this for theta_stable to trigger
    )

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
        session.theta_history.append(theta_estimate)

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

        Delegates to :func:`stopping_rules.check_stopping_criteria` which evaluates
        all stopping rules in priority order: minimum items, maximum items,
        content balance, SE threshold, and theta stabilization.

        Args:
            session: The current CATSession

        Returns:
            Tuple of (should_stop, stop_reason)
        """
        decision = check_stopping_criteria(
            se=session.theta_se,
            num_items=len(session.administered_items),
            domain_coverage=session.domain_coverage,
            theta_history=session.theta_history,
            se_threshold=self.SE_THRESHOLD,
            min_items=self.MIN_ITEMS,
            max_items=self.MAX_ITEMS,
            min_items_per_domain=self.MIN_ITEMS_PER_DOMAIN,
            delta_theta_threshold=self.DELTA_THETA_THRESHOLD,
            se_stabilization_threshold=self.SE_STABILIZATION_THRESHOLD,
        )

        if decision.should_stop:
            d = decision.details
            logger.info(
                f"Session {session.session_id}: Stopping due to {decision.reason} "
                f"(SE={d['se']:.3f}, items={d['num_items']}, "
                f"content_balanced={d['content_balanced']}, "
                f"theta_stable={d.get('theta_stable', 'N/A')})"
            )

        return (decision.should_stop, decision.reason)

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
