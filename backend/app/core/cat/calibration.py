"""
Bayesian 2PL IRT calibration module (TASK-856).

Estimates IRT discrimination (a) and difficulty (b) parameters using Marginal
Maximum Likelihood via the girth library, with bootstrap standard errors.

Functions:
    calibrate_questions_2pl - Core 2PL parameter estimation
    build_priors_from_ctt - Build informative priors from CTT metrics
    run_calibration_job - Full orchestration pipeline with DB updates
    validate_calibration - Validation comparing IRT vs empirical difficulty
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import girth
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Question, Response, TestSession, TestStatus

logger = logging.getLogger(__name__)

# --- Calibration thresholds ---

# Minimum responses per item for the calibration job to include an item
MIN_RESPONSES_FOR_CALIBRATION = 50

# Minimum items required for 2PL model identification
MIN_ITEMS_FOR_2PL = 2

# Minimum examinees required for stable 2PL parameter estimates
MIN_EXAMINEES_FOR_CALIBRATION = 10

# Minimum responses per item within the response matrix
MIN_RESPONSES_PER_ITEM = 10

# Maximum sparsity (fraction missing) before calibration is unreliable
MAX_SPARSITY_THRESHOLD = 0.95

# Minimum examinees for reliable bootstrap SE via CLT
MIN_EXAMINEES_FOR_BOOTSTRAP = 30

# --- Bootstrap configuration ---

BOOTSTRAP_ITERATIONS = 2000
BOOTSTRAP_N_PROCESSORS = 1  # Use 1 for Railway single-core; increase for multi-core

# --- P-value clamping for logit transform ---

P_VALUE_CLAMP_MIN = 0.01  # Prevent log(0) in logit transform
P_VALUE_CLAMP_MAX = 0.99  # Prevent log(0) in logit transform

# --- Validation fit thresholds ---

GOOD_FIT_CORRELATION = 0.80  # Pearson r indicating strong IRT-CTT agreement
GOOD_FIT_RMSE = 0.50  # RMSE in logit units for acceptable fit
MODERATE_FIT_CORRELATION = 0.60  # Minimum r for moderate agreement

# Minimum items needed for meaningful correlation computation
MIN_ITEMS_FOR_VALIDATION = 3

# --- Validation interpretation strings ---

FIT_GOOD = "Good fit"
FIT_MODERATE = "Moderate fit - review outlier items"
FIT_POOR = "Poor fit - review calibration data quality"
FIT_INSUFFICIENT = "Insufficient items for validation"


# --- TypedDicts for structured return types ---


class ItemCalibrationResult(TypedDict):
    """Parameter estimates for a single calibrated item."""

    difficulty: float
    discrimination: float
    se_difficulty: float
    se_discrimination: float
    information_peak: float


class CalibrationJobSummary(TypedDict):
    """Summary statistics from a calibration job run."""

    calibrated: int
    skipped: int
    mean_difficulty: float
    mean_discrimination: float
    timestamp: str


class ValidationReport(TypedDict):
    """Validation report comparing IRT and empirical difficulty."""

    correlation_irt_empirical: float
    rmse: float
    n_items: int
    mean_se_difficulty: float
    mean_se_discrimination: float
    interpretation: str


class CalibrationError(Exception):
    """Custom exception for IRT calibration errors."""

    def __init__(  # noqa: D107
        self,
        message: str,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.original_error = original_error
        self.context = context or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        msg = self.message
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            msg = f"{msg} (context: {ctx_str})"
        if self.original_error:
            msg = f"{msg} - caused by: {str(self.original_error)}"
        return msg


def _p_to_logit_difficulty(p: float) -> float:
    """Convert p-value (proportion correct) to IRT difficulty via logit transform.

    b = -log(p / (1-p)) = log((1-p)/p)
    Clamps p to [P_VALUE_CLAMP_MIN, P_VALUE_CLAMP_MAX] to avoid log(0).
    """
    p_clamped = max(P_VALUE_CLAMP_MIN, min(P_VALUE_CLAMP_MAX, p))
    return -math.log(p_clamped / (1 - p_clamped))


def calibrate_questions_2pl(
    responses: List[Dict[str, Any]],
    question_ids: Optional[List[int]] = None,
    bootstrap_se: bool = True,
    bootstrap_iterations: int = BOOTSTRAP_ITERATIONS,
    bootstrap_n_processors: int = BOOTSTRAP_N_PROCESSORS,
) -> Dict[int, ItemCalibrationResult]:
    """
    Calibrate questions using 2PL IRT via Marginal Maximum Likelihood.

    Uses girth.twopl_mml for parameter estimation and bootstrap resampling
    for standard error computation.

    Args:
        responses: List of response records, each containing:
            - user_id (int)
            - question_id (int)
            - is_correct (bool or int)
        question_ids: Optional list of question IDs to include. If None,
            all question IDs found in responses are used.
        bootstrap_se: Whether to compute bootstrap standard errors.
        bootstrap_iterations: Number of bootstrap resamples for SE estimation.
        bootstrap_n_processors: Number of parallel processes for bootstrap.

    Returns:
        Dictionary mapping question_id to ItemCalibrationResult.

    Raises:
        CalibrationError: If calibration fails due to insufficient data,
            convergence failure, or other issues.
    """
    if not responses:
        raise CalibrationError(
            "No responses provided for calibration",
            context={"n_responses": 0},
        )

    # Extract unique user and question IDs
    all_user_ids = sorted(set(r["user_id"] for r in responses))
    all_question_ids = sorted(set(r["question_id"] for r in responses))

    if question_ids is not None:
        all_question_ids = sorted(set(all_question_ids) & set(question_ids))

    if len(all_question_ids) < MIN_ITEMS_FOR_2PL:
        raise CalibrationError(
            f"At least {MIN_ITEMS_FOR_2PL} items required for 2PL calibration",
            context={"n_items": len(all_question_ids)},
        )

    if len(all_user_ids) < MIN_EXAMINEES_FOR_CALIBRATION:
        raise CalibrationError(
            f"At least {MIN_EXAMINEES_FOR_CALIBRATION} examinees required "
            "for 2PL calibration",
            context={"n_examinees": len(all_user_ids)},
        )

    # Build index mappings
    item_to_idx = {qid: i for i, qid in enumerate(all_question_ids)}
    user_to_idx = {uid: j for j, uid in enumerate(all_user_ids)}

    n_items = len(all_question_ids)
    n_users = len(all_user_ids)

    # Build response matrix: [n_items x n_users]
    # girth expects items as rows, participants as columns
    response_matrix = np.full((n_items, n_users), girth.INVALID_RESPONSE, dtype=int)

    for r in responses:
        qid = r["question_id"]
        uid = r["user_id"]
        if qid in item_to_idx and uid in user_to_idx:
            i = item_to_idx[qid]
            j = user_to_idx[uid]
            response_matrix[i, j] = 1 if r["is_correct"] else 0

    # Check sparsity: warn if too many missing responses
    total_cells = n_items * n_users
    observed_cells = np.sum(response_matrix != girth.INVALID_RESPONSE)
    sparsity = 1.0 - (observed_cells / total_cells)
    logger.info(
        f"Response matrix: {n_items} items x {n_users} users, "
        f"sparsity={sparsity:.1%} ({observed_cells}/{total_cells} observed)"
    )

    if sparsity > MAX_SPARSITY_THRESHOLD:
        raise CalibrationError(
            "Response matrix too sparse for reliable calibration",
            context={"sparsity": f"{sparsity:.1%}", "observed": int(observed_cells)},
        )

    # Filter out items with too few responses
    responses_per_item = np.sum(response_matrix != girth.INVALID_RESPONSE, axis=1)
    valid_item_mask = responses_per_item >= MIN_RESPONSES_PER_ITEM

    if not np.any(valid_item_mask):
        raise CalibrationError(
            "No items have sufficient responses for calibration",
            context={
                "min_required": MIN_RESPONSES_PER_ITEM,
                "max_observed": int(responses_per_item.max()),
            },
        )

    # Filter matrix to valid items only
    filtered_matrix = response_matrix[valid_item_mask]
    filtered_question_ids = [
        qid for qid, mask in zip(all_question_ids, valid_item_mask) if mask
    ]
    n_filtered = len(filtered_question_ids)

    if n_filtered < len(all_question_ids):
        logger.warning(
            f"Filtered {len(all_question_ids) - n_filtered} items with "
            f"< {MIN_RESPONSES_PER_ITEM} responses; {n_filtered} items remain"
        )

    # Run 2PL MML estimation
    try:
        logger.info(
            f"Running 2PL MML calibration: {n_filtered} items, {n_users} examinees"
        )
        result = girth.twopl_mml(filtered_matrix)
        est_discrimination = result["Discrimination"]
        est_difficulty = result["Difficulty"]
    except Exception as e:
        raise CalibrationError(
            "2PL MML estimation failed",
            original_error=e,
            context={"n_items": n_filtered, "n_users": n_users},
        ) from e

    # Compute bootstrap standard errors if requested
    se_discrimination = np.zeros(n_filtered)
    se_difficulty = np.zeros(n_filtered)

    if bootstrap_se and n_users >= MIN_EXAMINEES_FOR_BOOTSTRAP:
        try:
            logger.info(
                f"Computing bootstrap SEs: {bootstrap_iterations} iterations, "
                f"{bootstrap_n_processors} processor(s)"
            )
            bootstrap_result = girth.standard_errors_bootstrap(
                dataset=filtered_matrix,
                irt_model=girth.twopl_mml,
                bootstrap_iterations=bootstrap_iterations,
                n_processors=bootstrap_n_processors,
                solution=result,
                seed=42,
            )
            se_discrimination = bootstrap_result["Standard Errors"]["Discrimination"]
            se_difficulty = bootstrap_result["Standard Errors"]["Difficulty"].ravel()
        except Exception as e:
            logger.warning(f"Bootstrap SE computation failed, using zeros: {e}")
    elif bootstrap_se and n_users < MIN_EXAMINEES_FOR_BOOTSTRAP:
        logger.warning(
            "Skipping bootstrap SE: insufficient examinees "
            f"({n_users} < {MIN_EXAMINEES_FOR_BOOTSTRAP} minimum for reliable bootstrap)"
        )

    # Build results dictionary
    results: Dict[int, ItemCalibrationResult] = {}
    for idx, qid in enumerate(filtered_question_ids):
        b = float(est_difficulty[idx])
        a = float(est_discrimination[idx])
        results[qid] = {
            "difficulty": b,
            "discrimination": a,
            "se_difficulty": float(se_difficulty[idx]),
            "se_discrimination": float(se_discrimination[idx]),
            "information_peak": b,  # For 2PL, information peaks at θ = b
        }

    logger.info(
        f"Calibration complete: {len(results)} items. "
        f"Mean b={np.mean(est_difficulty):.2f} (SD={np.std(est_difficulty):.2f}), "
        f"Mean a={np.mean(est_discrimination):.2f} (SD={np.std(est_discrimination):.2f})"
    )

    return results


def build_priors_from_ctt(
    db: Session,
    question_ids: List[int],
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """
    Build informative priors for IRT calibration from CTT metrics.

    Converts empirical_difficulty (p-value) to IRT difficulty (b) via logit
    transformation, and uses CTT discrimination directly as a prior for
    IRT discrimination (a).

    Args:
        db: Database session
        question_ids: List of question IDs to build priors for

    Returns:
        Tuple of (prior_difficulties, prior_discriminations) where each is
        a dict mapping question_id to the prior value.

    Raises:
        CalibrationError: If database query fails.
    """
    try:
        questions = (
            db.query(
                Question.id,
                Question.empirical_difficulty,
                Question.discrimination,
            )
            .filter(Question.id.in_(question_ids))
            .all()
        )

        prior_difficulties: Dict[int, float] = {}
        prior_discriminations: Dict[int, float] = {}

        for q in questions:
            # Difficulty prior: logit transformation of p-value
            # Assumes population mean ability θ = 0
            if q.empirical_difficulty is not None:
                prior_difficulties[q.id] = _p_to_logit_difficulty(
                    q.empirical_difficulty
                )

            # Discrimination prior: CTT point-biserial correlation
            # Used directly (no scaling) as a reasonable starting estimate
            if q.discrimination is not None and q.discrimination > 0:
                prior_discriminations[q.id] = q.discrimination

        logger.info(
            f"Built CTT priors: {len(prior_difficulties)} difficulty priors, "
            f"{len(prior_discriminations)} discrimination priors "
            f"from {len(questions)} questions"
        )

        return prior_difficulties, prior_discriminations

    except CalibrationError:
        raise
    except Exception as e:
        logger.exception("Failed to build CTT priors")
        raise CalibrationError(
            "Failed to build CTT priors from database",
            original_error=e,
            context={"n_question_ids": len(question_ids)},
        ) from e


def run_calibration_job(
    db: Session,
    question_ids: Optional[List[int]] = None,
    min_responses: int = MIN_RESPONSES_FOR_CALIBRATION,
    bootstrap_se: bool = True,
) -> CalibrationJobSummary:
    """
    Run full IRT calibration pipeline and update database.

    Steps:
        1. Identify eligible questions (>= min_responses from completed fixed-form tests)
        2. Extract response data
        3. Run 2PL MML calibration
        4. Update database with estimated parameters
        5. Return summary statistics

    Args:
        db: Database session
        question_ids: Specific questions to calibrate. If None, all questions
            with sufficient responses are calibrated.
        min_responses: Minimum response count required per item.
        bootstrap_se: Whether to compute bootstrap standard errors.

    Returns:
        CalibrationJobSummary with counts and statistics.

    Raises:
        CalibrationError: If calibration fails.
    """
    try:
        logger.info(
            f"Starting calibration job: min_responses={min_responses}, "
            f"question_ids={'all' if question_ids is None else len(question_ids)}"
        )

        # Step 1: Find eligible questions
        response_counts_query = (
            db.query(
                Response.question_id,
                func.count(Response.id).label("response_count"),
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(
                TestSession.status == TestStatus.COMPLETED,
                TestSession.is_adaptive == False,  # noqa: E712
                Response.is_correct.isnot(None),
            )
            .group_by(Response.question_id)
            .having(func.count(Response.id) >= min_responses)
        )

        if question_ids is not None:
            response_counts_query = response_counts_query.filter(
                Response.question_id.in_(question_ids)
            )

        response_counts = response_counts_query.all()
        eligible_ids = [row.question_id for row in response_counts]
        count_by_id: Dict[int, int] = {
            row.question_id: row.response_count for row in response_counts
        }

        if not eligible_ids:
            logger.warning(
                "No questions meet minimum response threshold for calibration"
            )
            return {
                "calibrated": 0,
                "skipped": 0,
                "mean_difficulty": 0.0,
                "mean_discrimination": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"Found {len(eligible_ids)} eligible questions for calibration")

        # Step 2: Extract response data from completed, fixed-form tests
        response_rows = (
            db.query(
                Response.user_id,
                Response.question_id,
                Response.is_correct,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(
                TestSession.status == TestStatus.COMPLETED,
                TestSession.is_adaptive == False,  # noqa: E712
                Response.question_id.in_(eligible_ids),
                Response.is_correct.isnot(None),
            )
            .all()
        )

        response_dicts = [
            {
                "user_id": r.user_id,
                "question_id": r.question_id,
                "is_correct": r.is_correct,
            }
            for r in response_rows
        ]

        logger.info(
            f"Extracted {len(response_dicts)} responses for "
            f"{len(eligible_ids)} questions"
        )

        # Step 3: Run calibration
        calibration_results = calibrate_questions_2pl(
            responses=response_dicts,
            question_ids=eligible_ids,
            bootstrap_se=bootstrap_se,
        )

        # Step 4: Update database (batch-load questions to avoid N+1)
        now = datetime.now(timezone.utc)
        calibrated_count = 0
        skipped_count = 0

        question_ids_to_update = list(calibration_results.keys())
        questions_map = {
            q.id: q
            for q in db.query(Question)
            .filter(Question.id.in_(question_ids_to_update))
            .all()
        }

        for qid, params in calibration_results.items():
            question = questions_map.get(qid)
            if question is None:
                skipped_count += 1
                continue

            question.irt_difficulty = params["difficulty"]
            question.irt_discrimination = params["discrimination"]
            question.irt_se_difficulty = params["se_difficulty"]
            question.irt_se_discrimination = params["se_discrimination"]
            question.irt_information_peak = params["information_peak"]
            question.irt_calibrated_at = now
            question.irt_calibration_n = count_by_id.get(qid, 0)
            calibrated_count += 1

        db.commit()

        # Step 5: Summary statistics
        difficulties = [r["difficulty"] for r in calibration_results.values()]
        discriminations = [r["discrimination"] for r in calibration_results.values()]

        summary: CalibrationJobSummary = {
            "calibrated": calibrated_count,
            "skipped": skipped_count,
            "mean_difficulty": float(np.mean(difficulties)) if difficulties else 0.0,
            "mean_discrimination": (
                float(np.mean(discriminations)) if discriminations else 0.0
            ),
            "timestamp": now.isoformat(),
        }

        logger.info(
            f"Calibration job complete: {calibrated_count} calibrated, "
            f"{skipped_count} skipped. "
            f"Mean b={summary['mean_difficulty']:.2f}, "
            f"Mean a={summary['mean_discrimination']:.2f}"
        )

        return summary

    except CalibrationError:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Calibration job failed")
        raise CalibrationError(
            "Calibration job failed",
            original_error=e,
            context={"min_responses": min_responses},
        ) from e


def validate_calibration(
    db: Session,
    question_ids: Optional[List[int]] = None,
) -> ValidationReport:
    """
    Validate IRT calibration by comparing IRT difficulty with empirical difficulty.

    Computes correlation and RMSE between IRT difficulty (b) and logit-transformed
    empirical difficulty. A strong correlation indicates the IRT model is
    consistent with observed item statistics.

    Args:
        db: Database session
        question_ids: Specific questions to validate. If None, all calibrated
            questions with empirical difficulty are included.

    Returns:
        ValidationReport with correlation, RMSE, and interpretation.

    Raises:
        CalibrationError: If database query fails.
    """
    try:
        query = db.query(Question).filter(
            Question.irt_difficulty.isnot(None),
            Question.empirical_difficulty.isnot(None),
        )

        if question_ids is not None:
            query = query.filter(Question.id.in_(question_ids))

        questions = query.all()

        if len(questions) < MIN_ITEMS_FOR_VALIDATION:
            return {
                "correlation_irt_empirical": 0.0,
                "rmse": 0.0,
                "n_items": len(questions),
                "mean_se_difficulty": 0.0,
                "mean_se_discrimination": 0.0,
                "interpretation": FIT_INSUFFICIENT,
            }

        irt_difficulties = np.array([q.irt_difficulty for q in questions])

        # Convert empirical p-values to logit scale for comparison
        # empirical_difficulty is guaranteed non-None by the query filter above
        logit_empirical = np.array(
            [
                _p_to_logit_difficulty(q.empirical_difficulty)  # type: ignore[arg-type]
                for q in questions
            ]
        )

        # Pearson correlation (handle degenerate case of zero variance)
        correlation = float(np.corrcoef(irt_difficulties, logit_empirical)[0, 1])
        if not np.isfinite(correlation):
            correlation = 0.0
            logger.warning("Correlation is NaN (likely zero variance in difficulties)")

        # RMSE
        rmse = float(np.sqrt(np.mean((irt_difficulties - logit_empirical) ** 2)))

        # Mean SEs
        se_diffs = [q.irt_se_difficulty for q in questions if q.irt_se_difficulty]
        se_discs = [
            q.irt_se_discrimination for q in questions if q.irt_se_discrimination
        ]
        mean_se_diff = float(np.mean(se_diffs)) if se_diffs else 0.0
        mean_se_disc = float(np.mean(se_discs)) if se_discs else 0.0

        # Interpretation
        if correlation > GOOD_FIT_CORRELATION and rmse < GOOD_FIT_RMSE:
            interpretation = FIT_GOOD
        elif correlation > MODERATE_FIT_CORRELATION:
            interpretation = FIT_MODERATE
        else:
            interpretation = FIT_POOR

        result: ValidationReport = {
            "correlation_irt_empirical": correlation,
            "rmse": rmse,
            "n_items": len(questions),
            "mean_se_difficulty": mean_se_diff,
            "mean_se_discrimination": mean_se_disc,
            "interpretation": interpretation,
        }

        logger.info(
            f"Calibration validation: r={correlation:.3f}, RMSE={rmse:.3f}, "
            f"n={len(questions)}, interpretation='{interpretation}'"
        )

        return result

    except CalibrationError:
        raise
    except Exception as e:
        logger.exception("Calibration validation failed")
        raise CalibrationError(
            "Calibration validation failed",
            original_error=e,
        ) from e
