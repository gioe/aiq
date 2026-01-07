# Code Review Pattern Reference

This document contains real examples from PR reviews, showing common issues and their fixes. These patterns were identified from analysis of 50+ follow-up tasks created across 8 completed feature implementations.

Use this reference to:
- Understand common anti-patterns and their solutions
- Learn from actual review feedback in this codebase
- Prevent these issues in future code submissions

---

## Table of Contents

1. [Magic Numbers](#pattern-1-magic-numbers)
2. [Missing Use of Existing Enums/Types](#pattern-2-missing-use-of-existing-enumstypes)
3. [Database Performance Issues](#pattern-3-database-performance-issues)
4. [Missing Error Handling](#pattern-4-missing-error-handling)
5. [Missing Caching](#pattern-5-missing-caching)
6. [Logging Gaps](#pattern-6-logging-gaps)
7. [Test Quality - Floating Point Comparisons](#pattern-7-test-quality---floating-point-comparisons)
8. [Test Quality - Edge Case Coverage](#pattern-8-test-quality---edge-case-coverage)
9. [Test Quality - Parametrized Tests](#pattern-9-test-quality---parametrized-tests)
10. [Test Isolation](#pattern-10-test-isolation)
11. [Type Safety - TypedDict](#pattern-11-type-safety---typeddict)
12. [Type Safety - Pydantic Validators](#pattern-12-type-safety---pydantic-validators)
13. [Code Duplication and Reuse](#pattern-13-code-duplication-and-reuse)
14. [Backend-iOS Schema Consistency](#pattern-14-backend-ios-schema-consistency)

---

## Pattern 1: Magic Numbers

### Description
Numeric literals that represent thresholds, limits, or configuration values should be extracted to named constants with documentation explaining the rationale.

### Example from IDA-F001 (PR #226)

**Original Comment:**
> "The 0.05 threshold for 'at' comparison is reasonable but could be a named constant"

**Original Code:**
```python
def compare_to_average(question_disc: float, type_avg: float) -> str:
    if abs(question_disc - type_avg) <= 0.05:
        return "at"
    elif question_disc > type_avg:
        return "above"
    return "below"
```

**Fixed Code:**
```python
# Tolerance for "at average" comparisons (IDA-F001)
# When comparing a question's discrimination to the type or difficulty average,
# values within this tolerance are considered "at" average rather than above/below.
COMPARISON_TOLERANCE = 0.05

def compare_to_average(question_disc: float, type_avg: float) -> str:
    if abs(question_disc - type_avg) <= COMPARISON_TOLERANCE:
        return "at"
    elif question_disc > type_avg:
        return "above"
    return "below"
```

### Example from RE-FI-001 (PR #251)

**Original Comment:**
> "The 0.30 (30%) threshold is a magic number without explanation... Extract to a named constant"

**Original Code:**
```python
def filter_questions(sessions: List[Session], questions: List[Question]) -> List[Question]:
    threshold = int(len(sessions) * 0.30)
    return [q for q in questions if q.appearances >= threshold]
```

**Fixed Code:**
```python
# Proportion of sessions a question must appear in for inclusion
# 30% threshold balances having enough data per question with including
# enough questions for reliable alpha calculation
MIN_QUESTION_APPEARANCE_RATIO = 0.30

# Minimum absolute floor for question appearances
# Even if 30% of sessions is less than 30, require at least 30 appearances
MIN_QUESTION_APPEARANCE_ABSOLUTE = 30

def filter_questions(sessions: List[Session], questions: List[Question]) -> List[Question]:
    threshold = max(
        int(len(sessions) * MIN_QUESTION_APPEARANCE_RATIO),
        MIN_QUESTION_APPEARANCE_ABSOLUTE
    )
    return [q for q in questions if q.appearances >= threshold]
```

### Example from RE-FI-011 (PR #256)

**Original Comment:**
> "The magic number `5` lacks context. Is this 5 IQ points?... Define as a constant with documentation"

**Original Code:**
```python
def check_practice_effect(score_diff: float) -> bool:
    if abs(score_diff) > 5:
        return True
    return False
```

**Fixed Code:**
```python
# Large practice effect threshold (IDA-F011)
# Represents approximately 1/3 of a standard deviation (SD=15 for IQ scores)
# This is a meaningful effect size in psychometrics. Practice effects exceeding
# this threshold may indicate insufficient question variety, test-taking strategy
# effects, or learning effects beyond true ability change.
LARGE_PRACTICE_EFFECT_THRESHOLD = 5.0

def check_practice_effect(score_diff: float) -> bool:
    if abs(score_diff) > LARGE_PRACTICE_EFFECT_THRESHOLD:
        return True
    return False
```

---

## Pattern 2: Missing Use of Existing Enums/Types

### Description
Using hardcoded strings or lists when enum types already exist in the codebase. This reduces type safety and can lead to inconsistencies.

### Example from IDA-F002 (PR #226)

**Original Comment:**
> "Difficulty levels are hardcoded as strings when DifficultyLevel enum exists"

**Original Code:**
```python
def get_by_difficulty_breakdown(db: Session) -> Dict[str, float]:
    breakdown = {}
    for difficulty in ["easy", "medium", "hard"]:
        avg = db.query(func.avg(Question.discrimination)).filter(
            Question.difficulty_level == difficulty
        ).scalar()
        breakdown[difficulty] = avg or 0.0
    return breakdown
```

**Fixed Code:**
```python
from app.models.models import DifficultyLevel

def get_by_difficulty_breakdown(db: Session) -> Dict[str, float]:
    breakdown = {}
    for difficulty in DifficultyLevel:
        avg = db.query(func.avg(Question.discrimination)).filter(
            Question.difficulty_level == difficulty.value
        ).scalar()
        breakdown[difficulty.value] = avg or 0.0
    return breakdown
```

### Example from RE-FI-009 (PR #254)

**Original Comment:**
> "Consider using the `ReliabilityInterpretation` enum type directly for stronger type safety... API validation will reject invalid values automatically, Better OpenAPI documentation with allowed values"

**Original Code:**
```python
class InternalConsistencyMetrics(BaseModel):
    cronbachs_alpha: Optional[float]
    interpretation: str  # Any string accepted
    meets_threshold: bool
```

**Fixed Code:**
```python
from enum import Enum

class ReliabilityInterpretation(str, Enum):
    EXCELLENT = "excellent"      # >= 0.90
    GOOD = "good"                # >= 0.80
    ACCEPTABLE = "acceptable"    # >= 0.70
    QUESTIONABLE = "questionable"  # >= 0.60
    POOR = "poor"                # >= 0.50
    UNACCEPTABLE = "unacceptable"  # < 0.50

class InternalConsistencyMetrics(BaseModel):
    cronbachs_alpha: Optional[float]
    interpretation: ReliabilityInterpretation  # Only valid enum values
    meets_threshold: bool
```

---

## Pattern 3: Database Performance Issues

### Description
Database queries that can cause performance problems at scale: missing LIMIT clauses, N+1 query patterns, or performing aggregations in Python instead of SQL.

### Example from IDA-F012 (PR #232)

**Original Comment:**
> "Lines 349-399: The `immediate_review` and `monitor` lists query individual question records. While the comment acknowledges 'these lists are typically small,' consider monitoring this in production: What's the expected maximum size of these lists? Should there be a `LIMIT` clause to prevent excessive memory usage?"

**Original Code:**
```python
def get_action_lists(db: Session) -> Dict[str, List]:
    immediate_review = db.query(Question).filter(
        Question.discrimination < 0,
        Question.response_count >= 30
    ).all()

    monitor = db.query(Question).filter(
        Question.discrimination < 0.10,
        Question.discrimination >= 0,
        Question.response_count >= 30
    ).all()

    return {
        "immediate_review": immediate_review,
        "monitor": monitor
    }
```

**Fixed Code:**
```python
# Default limit for action_needed lists (IDA-F012)
# Prevents excessive memory usage if many questions have poor discrimination.
DEFAULT_ACTION_LIST_LIMIT = 100

def get_action_lists(db: Session, action_list_limit: int = DEFAULT_ACTION_LIST_LIMIT) -> Dict[str, List]:
    immediate_review = db.query(Question).filter(
        Question.discrimination < 0,
        Question.response_count >= 30
    ).order_by(
        Question.discrimination.asc()  # Worst items first
    ).limit(action_list_limit).all()

    monitor = db.query(Question).filter(
        Question.discrimination < 0.10,
        Question.discrimination >= 0,
        Question.response_count >= 30
    ).order_by(
        Question.discrimination.asc()  # Worst items first
    ).limit(action_list_limit).all()

    return {
        "immediate_review": immediate_review,
        "monitor": monitor
    }
```

### Example from IDA-F003 (PR #226)

**Original Comment:**
> "For large datasets, consider if database aggregations would be more efficient"

**Original Code:**
```python
def get_tier_distribution(questions: List[Question]) -> Dict[str, int]:
    counts = {"excellent": 0, "good": 0, "acceptable": 0, "poor": 0, "very_poor": 0, "negative": 0}
    for q in questions:
        tier = get_quality_tier(q.discrimination)
        if tier:
            counts[tier] += 1
    return counts
```

**Fixed Code:**
```python
def get_tier_distribution(db: Session, min_responses: int) -> Dict[str, int]:
    """Use SQL CASE/WHEN for tier counting instead of loading all questions."""
    tier_query = db.query(
        func.count(case(
            (Question.discrimination >= 0.40, 1),
            else_=None
        )).label("excellent"),
        func.count(case(
            (Question.discrimination >= 0.30, 1),
            (Question.discrimination < 0.40, 1),
            else_=None
        )).label("good"),
        # ... additional CASE statements for other tiers
    ).filter(
        Question.is_active == True,
        Question.response_count >= min_responses
    ).first()

    return {
        "excellent": tier_query.excellent or 0,
        "good": tier_query.good or 0,
        # ...
    }
```

---

## Pattern 4: Missing Error Handling

### Description
Database operations and external calls should be wrapped in try-except blocks with appropriate error logging and custom exceptions for debugging.

### Example from IDA-F015 (PR #232)

**Original Comment:**
> "The code assumes database queries will succeed. Consider what happens if: Database connection is lost mid-query, Query timeout occurs with extremely large datasets... wrapping in try-except might provide better diagnostics in production."

**Original Code:**
```python
def get_discrimination_report(db: Session, min_responses: int = 30) -> Dict:
    tier_counts = db.query(...).first()
    by_difficulty = db.query(...).all()
    by_type = db.query(...).all()

    return {
        "tier_counts": tier_counts,
        "by_difficulty": by_difficulty,
        "by_type": by_type
    }
```

**Fixed Code:**
```python
class DiscriminationAnalysisError(Exception):
    """Base exception for discrimination analysis errors with structured context."""

    def __init__(
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
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"Context: {context_str}")
        if self.original_error:
            parts.append(
                f"Original error: {type(self.original_error).__name__}: {self.original_error}"
            )
        return " | ".join(parts)


def get_discrimination_report(db: Session, min_responses: int = 30) -> Dict:
    try:
        tier_counts = db.query(...).first()
        by_difficulty = db.query(...).all()
        by_type = db.query(...).all()

        return {
            "tier_counts": tier_counts,
            "by_difficulty": by_difficulty,
            "by_type": by_type
        }
    except SQLAlchemyError as e:
        logger.exception(f"Database error in get_discrimination_report: {e}")
        raise DiscriminationAnalysisError(
            message="Failed to generate discrimination report",
            original_error=e,
            context={"min_responses": min_responses}
        )
```

### Example from RE-FI-015 (PR #256)

**Original Comment:**
> "If any of these functions raise unexpected exceptions, the entire report generation fails. Consider adding error handling"

**Original Code:**
```python
def get_reliability_report(db: Session) -> Dict:
    alpha_result = calculate_cronbachs_alpha(db)
    test_retest_result = calculate_test_retest_reliability(db)
    split_half_result = calculate_split_half_reliability(db)

    return {
        "internal_consistency": alpha_result,
        "test_retest": test_retest_result,
        "split_half": split_half_result
    }
```

**Fixed Code:**
```python
def _create_error_result() -> Dict:
    """Create a fallback result when calculation fails."""
    return {
        "value": None,
        "insufficient_data": True,
        "error": "Calculation failed unexpectedly"
    }

def get_reliability_report(db: Session) -> Dict:
    # Calculate each metric with error handling for partial results
    try:
        alpha_result = calculate_cronbachs_alpha(db)
    except Exception:
        logger.exception("Cronbach's alpha calculation failed")
        alpha_result = _create_error_result()

    try:
        test_retest_result = calculate_test_retest_reliability(db)
    except Exception:
        logger.exception("Test-retest calculation failed")
        test_retest_result = _create_error_result()

    try:
        split_half_result = calculate_split_half_reliability(db)
    except Exception:
        logger.exception("Split-half calculation failed")
        split_half_result = _create_error_result()

    return {
        "internal_consistency": alpha_result,
        "test_retest": test_retest_result,
        "split_half": split_half_result
    }
```

---

## Pattern 5: Missing Caching

### Description
Expensive operations (database aggregations, complex calculations) that don't change frequently should be cached to improve response times and reduce database load.

### Example from IDA-F004 (PR #226)

**Original Comment:**
> "Consider adding caching for get_discrimination_report() since this is expensive and data changes infrequently"

**Original Code:**
```python
def get_discrimination_report(db: Session, min_responses: int = 30) -> Dict:
    # Complex aggregation queries that run on every call
    tier_counts = db.query(...).first()
    by_difficulty = db.query(...).all()
    by_type = db.query(...).all()

    return process_results(tier_counts, by_difficulty, by_type)
```

**Fixed Code:**
```python
from app.core.cache import get_cache, cache_key as generate_cache_key

DISCRIMINATION_REPORT_CACHE_PREFIX = "discrimination_report"
DISCRIMINATION_REPORT_CACHE_TTL = 300  # 5 minutes

def invalidate_discrimination_report_cache() -> None:
    """Call when underlying data changes (e.g., after test submission)."""
    cache = get_cache()
    cache.delete_by_prefix(DISCRIMINATION_REPORT_CACHE_PREFIX)

def get_discrimination_report(db: Session, min_responses: int = 30) -> Dict:
    # Generate cache key from parameters
    cache = get_cache()
    key_suffix = generate_cache_key(min_responses=min_responses)
    cache_key = f"{DISCRIMINATION_REPORT_CACHE_PREFIX}:{key_suffix}"

    # Check cache first
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for discrimination report")
        return cached

    # Compute expensive result
    tier_counts = db.query(...).first()
    by_difficulty = db.query(...).all()
    by_type = db.query(...).all()
    result = process_results(tier_counts, by_difficulty, by_type)

    # Cache for future requests
    cache.set(cache_key, result, ttl=DISCRIMINATION_REPORT_CACHE_TTL)

    return result
```

### Example from IDA-F018 (PR #244) - Error Caching

**Original Comment:**
> "When a SQLAlchemyError occurs, the function raises an exception without caching anything. On transient errors (timeouts, connection drops), this means every retry hits the database again. Should transient errors trigger a short-lived cache entry?"

**Fixed Code (adding error caching for thundering herd prevention):**
```python
ERROR_CACHE_TTL = 30  # Short TTL for quick recovery
ERROR_CACHE_KEY_PREFIX = "discrimination_report_error"

def get_discrimination_report(db: Session, min_responses: int = 30) -> Dict:
    cache = get_cache()

    # Check error cache first (prevents thundering herd during outages)
    error_key = f"{ERROR_CACHE_KEY_PREFIX}:{generate_cache_key(min_responses=min_responses)}"
    error_cached = cache.get(error_key)
    if error_cached is not None:
        logger.debug("Returning cached error response")
        return error_cached  # Return empty fallback without hitting DB

    try:
        # ... normal processing
        return result
    except SQLAlchemyError as e:
        # Cache empty fallback to prevent thundering herd
        empty_result = _get_empty_report()
        cache.set(error_key, empty_result, ttl=ERROR_CACHE_TTL)
        raise DiscriminationAnalysisError(...)
```

---

## Pattern 6: Logging Gaps

### Description
Loggers are imported but never used, or logging is inconsistent across the module. Proper logging aids debugging and production monitoring.

### Example from IDA-F005 (PR #226)

**Original Comment:**
> "Logger imported but never used... add logging for debugging"

**Original Code:**
```python
import logging

logger = logging.getLogger(__name__)

def get_discrimination_report(db: Session, min_responses: int = 30) -> Dict:
    # Logger never used
    tier_counts = db.query(...).first()
    # ...
    return result
```

**Fixed Code:**
```python
import logging

logger = logging.getLogger(__name__)

def get_discrimination_report(db: Session, min_responses: int = 30) -> Dict:
    logger.info(f"Generating discrimination report with min_responses={min_responses}")

    tier_counts = db.query(...).first()
    logger.info(f"Tier distribution: excellent={tier_counts.excellent}, poor={tier_counts.poor}")

    if immediate_review_count > 0:
        logger.warning(f"{immediate_review_count} questions have negative discrimination and require review")

    return result
```

### Example from IDA-F020 (PR #244) - Avoiding Duplicate Logs

**Original Comment:**
> "Both calculate_percentile_rank() and get_question_discrimination_detail() log errors. If calculate_percentile_rank() is called from get_question_discrimination_detail(), you might see duplicate log entries."

**Original Code (double logging):**
```python
def calculate_percentile_rank(db: Session, discrimination: float) -> int:
    try:
        # ...
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")  # ERROR logged here
        raise

def get_question_discrimination_detail(db: Session, question_id: int) -> Dict:
    try:
        percentile = calculate_percentile_rank(db, discrimination)
    except Exception as e:
        logger.error(f"Failed to get detail: {e}")  # ERROR logged again!
        raise
```

**Fixed Code (log at appropriate levels):**
```python
def calculate_percentile_rank(db: Session, discrimination: float) -> int:
    try:
        # ...
    except SQLAlchemyError as e:
        logger.debug(f"Database error in percentile calculation: {e}")  # DEBUG, not ERROR
        raise DiscriminationAnalysisError(...) from e

def get_question_discrimination_detail(db: Session, question_id: int) -> Dict:
    try:
        percentile = calculate_percentile_rank(db, discrimination)
    except DiscriminationAnalysisError:
        # Don't log - inner function already logged at debug level
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to get detail for question {question_id}")  # ERROR only here
        raise
```

---

## Pattern 7: Test Quality - Floating Point Comparisons

### Description
Direct equality comparisons with floats can cause flaky tests due to floating-point precision issues. Use `pytest.approx()` for all float comparisons.

### Example from IDA-F009 (PR #229)

**Original Comment:**
> "Direct equality comparisons with floats... Recommendation: Use pytest.approx() for floating-point comparisons to avoid flakiness."

**Original Code:**
```python
def test_quality_distribution_percentages():
    report = get_discrimination_report(db, min_responses=30)

    assert report["quality_distribution"]["excellent_pct"] == 20.0
    assert report["quality_distribution"]["good_pct"] == 40.0
    assert report["by_difficulty"]["easy"]["mean"] == 0.35
```

**Fixed Code:**
```python
import pytest

def test_quality_distribution_percentages():
    report = get_discrimination_report(db, min_responses=30)

    assert report["quality_distribution"]["excellent_pct"] == pytest.approx(20.0)
    assert report["quality_distribution"]["good_pct"] == pytest.approx(40.0)
    assert report["by_difficulty"]["easy"]["mean"] == pytest.approx(0.35)

# For very precise values, use explicit tolerance
def test_precise_calculation():
    result = calculate_complex_value()
    assert result == pytest.approx(3.14159, rel=1e-5)
```

---

## Pattern 8: Test Quality - Edge Case Coverage

### Description
Tests should cover boundary conditions including empty inputs, single elements, exactly-at-threshold values, and mathematically undefined cases.

### Example from RE-FI-003 (PR #251)

**Original Comment:**
> "Missing test: Verify behavior when exactly 2 items exist... Verify behavior with very high number of items"

**Original Code:**
```python
class TestCronbachsAlpha:
    def test_basic_calculation(self):
        # Only tests with typical values
        result = calculate_cronbachs_alpha(db)
        assert result["alpha"] is not None
```

**Fixed Code:**
```python
class TestEdgeCases:
    def test_exactly_two_items_minimum_for_alpha(self):
        """Test calculation with exactly 2 items (minimum for Cronbach's alpha)."""
        # Create test data with only 2 questions
        # k=2 is the edge case where formula is still valid
        result = calculate_cronbachs_alpha(db)
        assert result["alpha"] is not None
        assert 0 <= result["alpha"] <= 1

    def test_very_high_number_of_items(self):
        """Test calculation with 60 items to verify scalability."""
        # Create test data with 60 questions
        result = calculate_cronbachs_alpha(db)
        assert result["alpha"] is not None

    def test_single_item_returns_error(self):
        """Cronbach's alpha is undefined for k<2."""
        # Create test data with only 1 question
        result = calculate_cronbachs_alpha(db)
        assert result["error"] is not None
        assert "need at least 2" in result["error"]
```

### Example from RE-FI-016 (PR #256)

**Original Comment:**
> "Missing tests: Test with exactly zero correlation values, Test with negative correlation values, Test with practice effect exactly at threshold"

**Fixed Code:**
```python
class TestCorrelationEdgeCases:
    def test_exactly_zero_correlation(self):
        """Test with zero variance (correlation undefined)."""
        # Create data where all responses are identical
        result = calculate_test_retest(db)
        # Zero variance means correlation is undefined
        assert result["correlation"] is None or result["error"] is not None

    def test_practice_effect_exactly_at_threshold(self):
        """Test practice effect exactly at 5.0 IQ points."""
        result = calculate_test_retest(db)
        # Exactly at threshold should NOT trigger warning
        assert "practice effect" not in result.get("warnings", [])

    def test_practice_effect_just_above_threshold_triggers_warning(self):
        """Test practice effect at 5.1 IQ points."""
        result = calculate_test_retest(db)
        # Just above threshold SHOULD trigger warning
        assert any("practice effect" in w for w in result.get("warnings", []))
```

---

## Pattern 9: Test Quality - Parametrized Tests

### Description
Repetitive test methods with similar structure should be refactored to use `pytest.mark.parametrize` for cleaner, more maintainable tests.

### Example from IDA-F011 (PR #229)

**Original Comment:**
> "Several test classes have repetitive test methods that could be parametrized... Trade-off: Current approach is more readable for boundary testing; parametrization would be more compact."

**Original Code:**
```python
class TestGetQualityTier:
    def test_excellent_tier(self):
        assert get_quality_tier(0.45) == "excellent"

    def test_good_tier(self):
        assert get_quality_tier(0.35) == "good"

    def test_acceptable_tier(self):
        assert get_quality_tier(0.25) == "acceptable"

    def test_poor_tier(self):
        assert get_quality_tier(0.15) == "poor"

    def test_very_poor_tier(self):
        assert get_quality_tier(0.05) == "very_poor"

    def test_negative_tier(self):
        assert get_quality_tier(-0.15) == "negative"
```

**Fixed Code:**
```python
import pytest

class TestGetQualityTier:
    @pytest.mark.parametrize("value,expected_tier", [
        (0.45, "excellent"),
        (0.40, "excellent"),  # boundary
        (0.35, "good"),
        (0.30, "good"),       # boundary
        (0.25, "acceptable"),
        (0.20, "acceptable"), # boundary
        (0.15, "poor"),
        (0.10, "poor"),       # boundary
        (0.05, "very_poor"),
        (0.00, "very_poor"),  # boundary
        (-0.15, "negative"),
    ])
    def test_quality_tier_classification(self, value: float, expected_tier: str):
        assert get_quality_tier(value) == expected_tier

    def test_none_input_returns_none(self):
        assert get_quality_tier(None) is None
```

---

## Pattern 10: Test Isolation

### Description
Tests should not interfere with each other. Avoid committing after each item in loops and use batch operations instead.

### Example from IDA-F008 (PR #227)

**Original Comment:**
> "The test creates 6 questions in a loop and commits after each one. This could interact with other tests running concurrently."

**Original Code:**
```python
def test_discrimination_detail_quality_tiers():
    # Commits after each iteration - can interfere with concurrent tests
    for i, (disc_value, expected_tier) in enumerate([
        (0.45, "excellent"),
        (0.35, "good"),
        (0.25, "acceptable"),
        (0.15, "poor"),
        (0.05, "very_poor"),
        (-0.15, "negative"),
    ]):
        question = Question(
            discrimination=disc_value,
            response_count=50,
            is_active=True
        )
        db.add(question)
        db.commit()  # Multiple commits!

        result = get_question_discrimination_detail(db, question.id)
        assert result["quality_tier"] == expected_tier
```

**Fixed Code:**
```python
def test_discrimination_detail_quality_tiers():
    # Create all questions first
    test_cases = [
        (0.45, "excellent"),
        (0.35, "good"),
        (0.25, "acceptable"),
        (0.15, "poor"),
        (0.05, "very_poor"),
        (-0.15, "negative"),
    ]

    questions = []
    for disc_value, expected_tier in test_cases:
        question = Question(
            discrimination=disc_value,
            response_count=50,
            is_active=True
        )
        questions.append((question, expected_tier))
        db.add(question)

    db.commit()  # Single commit!

    # Now run assertions
    for question, expected_tier in questions:
        result = get_question_discrimination_detail(db, question.id)
        assert result["quality_tier"] == expected_tier
```

---

## Pattern 11: Type Safety - TypedDict

### Description
Functions returning dictionaries with known structures should use `TypedDict` instead of `Dict[str, Any]` for better type checking and IDE support.

### Example from RE-FI-002 (PR #251)

**Original Comment:**
> "The type: ignore comment suggests the type annotations for get_negative_item_correlations return type could be more specific"

**Original Code:**
```python
from typing import Any, Dict, List

def get_negative_item_correlations(db: Session) -> List[Dict[str, Any]]:  # type: ignore
    items = []
    for question in db.query(Question).filter(Question.correlation < 0).all():
        items.append({
            "question_id": question.id,
            "correlation": question.correlation,
            "recommendation": "Consider removing this question"
        })
    return items
```

**Fixed Code:**
```python
from typing import List
from typing_extensions import TypedDict

class ProblematicItem(TypedDict):
    """Type definition for items with negative or low item-total correlations."""
    question_id: int
    correlation: float
    recommendation: str

def get_negative_item_correlations(db: Session) -> List[ProblematicItem]:
    items: List[ProblematicItem] = []
    for question in db.query(Question).filter(Question.correlation < 0).all():
        items.append({
            "question_id": question.id,
            "correlation": question.correlation,
            "recommendation": "Consider removing this question"
        })
    return items
```

---

## Pattern 12: Type Safety - Pydantic Validators

### Description
Pydantic schemas should include validators to ensure logical consistency between fields, preventing impossible states from being serialized.

### Example from RE-FI-010 (PR #254)

**Original Comment:**
> "When cronbachs_alpha is None (insufficient data), what should meets_threshold be? Consider adding a Pydantic validator to ensure logical consistency"

**Original Code:**
```python
class InternalConsistencyMetrics(BaseModel):
    cronbachs_alpha: Optional[float]
    meets_threshold: bool
    interpretation: str
    # No validation - allows meets_threshold=True when cronbachs_alpha=None!
```

**Fixed Code:**
```python
from pydantic import BaseModel, model_validator
from typing import Optional
from typing_extensions import Self

ALPHA_THRESHOLD = 0.70

class InternalConsistencyMetrics(BaseModel):
    cronbachs_alpha: Optional[float]
    meets_threshold: bool
    interpretation: ReliabilityInterpretation

    @model_validator(mode="after")
    def validate_meets_threshold_consistency(self) -> Self:
        """Ensure meets_threshold is logically consistent with cronbachs_alpha."""
        if self.cronbachs_alpha is None and self.meets_threshold:
            raise ValueError("meets_threshold cannot be True when cronbachs_alpha is None")
        if self.cronbachs_alpha is not None:
            if self.cronbachs_alpha >= ALPHA_THRESHOLD and not self.meets_threshold:
                raise ValueError(
                    f"meets_threshold must be True when cronbachs_alpha >= {ALPHA_THRESHOLD}"
                )
            if self.cronbachs_alpha < ALPHA_THRESHOLD and self.meets_threshold:
                raise ValueError(
                    f"meets_threshold must be False when cronbachs_alpha < {ALPHA_THRESHOLD}"
                )
        return self
```

### Example from RE-FI-027 (PR #267)

**Original Comment:**
> "The test identifies an edge case where `raw_correlation=None` but `spearman_brown=0.75`. While the schema allows this, mathematically this shouldn't happen."

**Fixed Code:**
```python
class SplitHalfMetrics(BaseModel):
    raw_correlation: Optional[float]
    spearman_brown: Optional[float]
    meets_threshold: bool

    @model_validator(mode="after")
    def validate_spearman_brown_requires_correlation(self) -> Self:
        """Spearman-Brown correction requires a raw correlation value."""
        if self.raw_correlation is None and self.spearman_brown is not None:
            raise ValueError(
                "spearman_brown cannot be present when raw_correlation is None "
                "(Spearman-Brown correction requires a raw correlation value)"
            )
        return self
```

---

## Pattern 13: Code Duplication and Reuse

### Description
Implementing functionality that already exists in the codebase, particularly for security-sensitive operations like authentication. This leads to inconsistent behavior and maintenance burden.

### Example from BTS-46 (PR #486)

**Original Comment:**
> "The _get_optional_user() function duplicates existing functionality in app.core.auth.get_current_user_optional(). This creates inconsistent behavior - the existing function raises HTTP 503 on database errors while the new function silently returns None."

**Original Code:**
```python
from app.core.auth import security_optional
from app.core.security import decode_token

def _get_optional_user(credentials, db):
    """Custom implementation duplicating existing auth dependency."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload is None:
            return None
        user_id = payload.get("user_id")
        if user_id is None:
            return None
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except Exception as e:
        # Silent failure - swallows database errors!
        logger.debug(f"Optional auth failed: {e}")
        return None

@router.post("/submit")
async def submit_feedback(
    data: FeedbackRequest,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
):
    current_user = _get_optional_user(credentials, db)
    # ...
```

**Fixed Code:**
```python
from app.core.auth import get_current_user_optional

@router.post("/submit")
async def submit_feedback(
    data: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),  # Reuse existing
):
    # current_user is already resolved by the dependency
    # Database errors properly raise HTTP 503
    # ...
```

### Why This Matters

The original implementation had a **critical flaw**: it caught `Exception` broadly, meaning database errors (connection timeouts, transaction failures) would be silently ignored. The user would appear anonymous even when authenticated because the database was unavailable.

The existing `get_current_user_optional` in `app/core/auth.py`:
- Properly catches only `HTTPException` for invalid tokens
- Catches `SQLAlchemyError` separately and raises HTTP 503
- Has been tested and reviewed

### Prevention Checklist

- [ ] Search `app/core/` before implementing auth-related functionality
- [ ] Check if similar functionality exists: `grep -r "def similar_name" backend/app/`
- [ ] If extending existing functionality, modify the original rather than duplicating

---

## Pattern 14: Backend-iOS Schema Consistency

### Description
iOS models that don't match backend Pydantic schemas exactly, particularly making fields optional when the backend returns them as required. This masks decoding failures and can cause bugs that are difficult to debug.

### Example from BTS-46 (PR #486)

**Original Comment:**
> "The backend returns submission_id as required, but iOS defines it as optional. This could mask decoding failures."

**Backend Schema:**
```python
class FeedbackSubmitResponse(BaseModel):
    success: bool
    submission_id: int  # Required - always returned on success
    message: str
```

**Original iOS Code:**
```swift
struct FeedbackSubmitResponse: Decodable {
    let success: Bool
    let submissionId: Int?  // Wrong! Backend always returns this
    let message: String

    enum CodingKeys: String, CodingKey {
        case success
        case submissionId = "submission_id"
        case message
    }
}
```

**Fixed iOS Code:**
```swift
struct FeedbackSubmitResponse: Decodable {
    let success: Bool
    let submissionId: Int  // Correct - matches backend schema
    let message: String

    enum CodingKeys: String, CodingKey {
        case success
        case submissionId = "submission_id"
        case message
    }
}
```

### Why This Matters

When `submissionId` is optional but the backend always returns it:
1. **If decoding fails** (e.g., backend returns `null` unexpectedly), `submissionId` becomes `nil` silently
2. **No error is thrown** - the app continues with missing data
3. **Debugging is difficult** - the issue manifests far from the actual problem

When `submissionId` is required and decoding fails:
1. **JSONDecoder throws an error** immediately
2. **Error handling kicks in** - user sees appropriate error message
3. **Easy to debug** - stack trace points directly to the schema mismatch

### Prevention Checklist

Before creating/modifying iOS models:
- [ ] Read the backend Pydantic schema in `backend/app/schemas/`
- [ ] Verify every field's optionality matches
- [ ] Test with actual backend response, not just mock data
- [ ] Use the type mapping table in iOS Coding Standards

### Related Documentation

- [iOS Coding Standards: API Schema Consistency](../ios/docs/CODING_STANDARDS.md#api-schema-consistency)
- [Backend README: Code Reuse and DRY Principles](../backend/README.md#code-reuse-and-dry-principles)

---

## Summary

These 14 patterns represent the most common issues found during code reviews. By understanding and avoiding these anti-patterns, you can:

1. **Reduce review iterations** - Fewer follow-up tasks from PR reviews
2. **Improve code quality** - More maintainable, type-safe, and performant code
3. **Enable faster debugging** - Better error handling and logging
4. **Ensure test reliability** - Avoid flaky tests in CI

For automated checking of some of these patterns, use:
- **Pre-commit hooks**: `check_float_comparisons.py`, `check_magic_numbers.py`
- **Slash command**: `/review-patterns` for manual review
- **Code reviewer agent**: Project-specific code reviewer at `.claude/agents/project-code-reviewer.md`
