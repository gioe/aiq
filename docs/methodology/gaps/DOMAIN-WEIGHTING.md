# Domain Weighting and Subscores

## Problem Statement

AIQ tests six cognitive domains (pattern, logic, spatial, math, verbal, memory) but treats all questions equally when computing the final IQ score. A correct answer on a pattern recognition question counts the same as a correct answer on a verbal reasoning question.

This equal weighting assumes all domains contribute equally to general intelligence (g). This assumption is testable and likely incorrect—research suggests different cognitive abilities have different "g-loadings" (correlations with general intelligence).

Additionally, users receive only a single composite score with no visibility into their domain-specific performance.

## What is g-Loading?

The g-loading of a cognitive ability is its correlation with general intelligence (g-factor). Higher g-loadings indicate abilities more central to general cognitive ability.

### Typical g-Loadings from Research

| Cognitive Ability | Typical g-Loading | Notes |
|-------------------|-------------------|-------|
| Fluid Reasoning (Gf) | 0.70-0.85 | Highest, core of g |
| Crystallized Intelligence (Gc) | 0.60-0.75 | Knowledge-based |
| Visual-Spatial (Gv) | 0.55-0.70 | Mental manipulation |
| Quantitative (Gq) | 0.60-0.75 | Math reasoning |
| Short-term Memory (Gsm) | 0.50-0.65 | Working memory |
| Processing Speed (Gs) | 0.45-0.55 | Lower, more peripheral |

**Implication:** If we weighted by g-loading, fluid reasoning questions should count more than processing speed questions.

## Current State

### What Exists

1. **Six cognitive domains tracked** (`backend/app/models/models.py:27-35`)
   ```python
   class QuestionType(str, enum.Enum):
       PATTERN = "pattern"
       LOGIC = "logic"
       SPATIAL = "spatial"
       MATH = "math"
       VERBAL = "verbal"
       MEMORY = "memory"
   ```

2. **Domain stored per question** - Each question has a type

3. **Response data** - Know which domain each response is for

4. **Simple scoring** (`backend/app/core/scoring.py`)
   - All correct answers count equally
   - No domain breakdown

### What's Missing

1. **Domain subscores**
   - No separate scores per domain
   - Users can't see relative strengths/weaknesses

2. **Empirical g-loading analysis**
   - No factor analysis infrastructure
   - Don't know actual g-loadings for our test

3. **Weighted composite scoring**
   - All domains weighted 1.0
   - No adjustment based on g-loadings

4. **Domain visualization**
   - No charts showing domain performance
   - No comparative feedback

## Why This Matters

### Measurement Precision

If fluid reasoning has g-loading of 0.80 and memory has 0.55, weighting them equally:
- Undervalues fluid reasoning's contribution to g
- Overvalues memory's contribution
- Produces less accurate g estimates

### User Value

Domain subscores provide:
- Actionable feedback (which areas to improve)
- More engaging experience (detailed profile)
- Longitudinal tracking per domain

### Scientific Validity

Major IQ tests (WAIS, Stanford-Binet) report:
- Composite score (overall IQ)
- Index scores (clusters of related abilities)
- Subtest scores (specific abilities)

AIQ providing only composite is incomplete.

## Solution Requirements

### 1. Domain Subscores

Calculate and store separate scores for each cognitive domain.

**Addition to TestResult:**
```python
domain_scores = Column(JSON, nullable=True)
# Example: {
#     "pattern": {"correct": 3, "total": 4, "pct": 75.0},
#     "logic": {"correct": 2, "total": 3, "pct": 66.7},
#     "spatial": {"correct": 2, "total": 3, "pct": 66.7},
#     "math": {"correct": 3, "total": 4, "pct": 75.0},
#     "verbal": {"correct": 3, "total": 3, "pct": 100.0},
#     "memory": {"correct": 2, "total": 3, "pct": 66.7}
# }
```

**Calculation Function:**
```python
def calculate_domain_scores(
    responses: List[Response],
    questions: Dict[int, Question]
) -> Dict[str, Dict]:
    """
    Calculate per-domain performance breakdown.

    Args:
        responses: List of user responses
        questions: Dict mapping question_id to Question

    Returns:
        Dict with domain scores
    """
    domain_stats = {}

    for domain in QuestionType:
        domain_responses = [
            r for r in responses
            if questions[r.question_id].question_type == domain
        ]

        correct = sum(1 for r in domain_responses if r.is_correct)
        total = len(domain_responses)

        domain_stats[domain.value] = {
            "correct": correct,
            "total": total,
            "pct": round(correct / total * 100, 1) if total > 0 else None
        }

    return domain_stats
```

### 2. Factor Analysis Infrastructure

To determine empirical g-loadings, need factor analysis capability.

**Requirements:**
- Minimum 500 completed test sessions
- Response matrix: users × items
- Statistical computing (numpy, scipy, or factor_analyzer library)

**Process:**
```python
from factor_analyzer import FactorAnalyzer
import numpy as np

def calculate_g_loadings(
    response_matrix: np.ndarray,
    question_domains: List[str]
) -> Dict[str, float]:
    """
    Calculate g-loadings for each domain using factor analysis.

    Args:
        response_matrix: n_users × n_items, values 0 or 1
        question_domains: Domain for each item (same order as matrix columns)

    Returns:
        Dict mapping domain to g-loading
    """
    # Extract single factor (g)
    fa = FactorAnalyzer(n_factors=1, rotation=None)
    fa.fit(response_matrix)

    # Get loadings per item
    item_loadings = fa.loadings_[:, 0]

    # Average loadings by domain
    domain_loadings = {}
    for domain in set(question_domains):
        domain_items = [
            i for i, d in enumerate(question_domains)
            if d == domain
        ]
        domain_loadings[domain] = np.mean(
            [item_loadings[i] for i in domain_items]
        )

    return domain_loadings
```

**Analysis Endpoint:**
```
GET /v1/admin/analytics/factor-analysis
```

Response:
```json
{
    "analysis_date": "2025-12-06",
    "sample_size": 850,
    "g_loadings": {
        "pattern": 0.72,
        "logic": 0.68,
        "spatial": 0.61,
        "math": 0.65,
        "verbal": 0.58,
        "memory": 0.52
    },
    "variance_explained": 0.45,
    "reliability": {
        "cronbachs_alpha": 0.78
    },
    "recommendations": [
        "Pattern recognition has highest g-loading - consider increasing weight",
        "Memory has lowest g-loading - consider reducing weight"
    ]
}
```

### 3. Weighted Composite Scoring

Once g-loadings are established, weight domain scores accordingly.

**Weighting Options:**

**Option A: Direct g-loading weights**
```python
# Normalize g-loadings to sum to 1
weights = {domain: loading / sum(loadings) for domain, loading in loadings.items()}
```

**Option B: Relative importance weights**
```python
# Use g-loadings relative to highest
max_loading = max(loadings.values())
weights = {domain: loading / max_loading for domain, loading in loadings.items()}
```

**Weighted Score Function:**
```python
def calculate_weighted_iq_score(
    domain_scores: Dict[str, Dict],
    weights: Dict[str, float]
) -> int:
    """
    Calculate IQ score with domain-weighted composite.

    Args:
        domain_scores: Per-domain correct/total counts
        weights: Per-domain weights (g-loadings or derived)

    Returns:
        Weighted IQ score
    """
    weighted_sum = 0
    total_weight = 0

    for domain, stats in domain_scores.items():
        if stats["total"] > 0:
            accuracy = stats["correct"] / stats["total"]
            weight = weights.get(domain, 1.0)
            weighted_sum += accuracy * weight
            total_weight += weight

    # Normalize to 0-1 scale
    weighted_accuracy = weighted_sum / total_weight if total_weight > 0 else 0.5

    # Apply IQ transformation
    iq_score = round(100 + ((weighted_accuracy - 0.5) * 30))

    return iq_score
```

### 4. iOS Domain Visualization

Display domain performance to users.

**Visualization Options:**

**Option A: Radar Chart**
6-pointed radar showing relative performance across domains.

**Option B: Bar Chart**
Horizontal bars for each domain, ordered by score.

**Option C: Percentile Badges**
Show domain percentiles with visual indicators (star ratings, colors).

**Implementation Location:** `ios/AIQ/Views/Test/TestResultView.swift`

**Data from API:**
```json
{
    "iq_score": 108,
    "domain_scores": {
        "pattern": {"correct": 3, "total": 4, "pct": 75.0, "percentile": 72},
        "logic": {"correct": 2, "total": 3, "pct": 66.7, "percentile": 58},
        "spatial": {"correct": 2, "total": 3, "pct": 66.7, "percentile": 55},
        "math": {"correct": 3, "total": 4, "pct": 75.0, "percentile": 68},
        "verbal": {"correct": 3, "total": 3, "pct": 100.0, "percentile": 95},
        "memory": {"correct": 2, "total": 3, "pct": 66.7, "percentile": 60}
    },
    "strongest_domain": "verbal",
    "weakest_domain": "spatial"
}
```

**User Messaging:**
> "Your strongest area is verbal reasoning, where you scored in the 95th percentile. Your spatial reasoning showed room for improvement at the 55th percentile."

## Implementation Dependencies

### Prerequisites
- Response data per domain ✓
- Question type tracking ✓
- For g-loadings: 500+ completed test sessions

### Phasing

**Phase 1: Domain Subscores (immediate)**
- Calculate and store per-domain scores
- Add to API response
- Display in iOS

**Phase 2: Factor Analysis (500+ users)**
- Implement factor analysis
- Calculate empirical g-loadings
- Admin dashboard for results

**Phase 3: Weighted Scoring (after validation)**
- Implement weighted composite
- A/B test against equal weighting
- Transition if improvement confirmed

### Database Changes

Add to TestResult:
```python
domain_scores = Column(JSON, nullable=True)
```

Consider system config table for weights:
```python
class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(100), primary_key=True)
    value = Column(JSON)
    updated_at = Column(DateTime)

# Store: domain_weights = {"pattern": 0.20, "logic": 0.18, ...}
```

### Related Code Locations
- `backend/app/core/scoring.py` - Add weighted scoring
- `backend/app/models/models.py` - Add domain_scores field
- Test submission endpoint - Calculate domain scores
- Test result API - Return domain data
- `ios/AIQ/Views/Test/TestResultView.swift` - Display domains

## Domain Score Percentiles

To make domain scores interpretable, need domain-specific norms.

**Challenge:** Different number of questions per domain (3-4 each).

**Solution:** Use aggregate statistics:
```python
def calculate_domain_percentile(
    domain: str,
    correct: int,
    total: int,
    population_stats: Dict
) -> float:
    """
    Calculate percentile for domain score.

    Uses population distribution for that domain.
    """
    accuracy = correct / total
    domain_mean = population_stats[domain]["mean_accuracy"]
    domain_sd = population_stats[domain]["sd_accuracy"]

    z = (accuracy - domain_mean) / domain_sd
    percentile = norm.cdf(z) * 100

    return round(percentile, 1)
```

## Alternative: Index Scores

Instead of 6 domains, could group into broader indices:

| Index | Domains | WAIS Equivalent |
|-------|---------|-----------------|
| Fluid Reasoning | pattern, logic | Fluid Reasoning Index |
| Verbal Ability | verbal, memory | Verbal Comprehension Index |
| Spatial-Math | spatial, math | Visual-Spatial / Quantitative |

This reduces noise from small per-domain samples while still providing differentiated feedback.

## Success Criteria

1. **Subscores:** Domain scores calculated and stored for all tests
2. **API:** Domain data included in test result responses
3. **Display:** iOS shows domain breakdown with visualization
4. **Factor Analysis:** G-loadings calculated when sample size permits
5. **Weighting:** Weighted scoring implemented (configurable)
6. **Interpretation:** Domain percentiles provided for context

## Testing Strategy

1. **Unit Tests:**
   - Test domain score calculation with known responses
   - Test weighted score calculation
   - Test percentile calculations

2. **Integration Tests:**
   - Create test sessions with controlled domain performance
   - Verify domain scores stored correctly
   - Verify API returns domain data

3. **Factor Analysis Validation:**
   - Use simulated data with known factor structure
   - Verify extracted loadings match expectations
   - Compare against published g-loading values

4. **iOS Tests:**
   - Test domain visualization rendering
   - Test with various score patterns
   - Test accessibility of domain display

## Research Considerations

### Stability of g-Loadings

G-loadings should be recalculated periodically:
- New questions may have different loadings
- Population changes over time
- Minimum: quarterly recalculation

### Cross-Validation

When implementing weighted scoring:
- Split sample in half
- Calculate weights on half A
- Validate on half B
- Ensure improvement is real, not overfitting

### Comparison to Theory

Compare empirical g-loadings to CHC theory predictions:
- Pattern/Logic (Gf) should be highest
- Verbal (Gc) should be substantial
- Memory (Gsm) typically lower

Major deviations may indicate question quality issues.

## References

- IQ_METHODOLOGY.md, Section 2 (CHC Theory framework)
- IQ_METHODOLOGY.md, Section 3 (Domain mapping to CHC abilities)
- Carroll, J.B. (1993). Human cognitive abilities: A survey of factor-analytic studies
- Cattell-Horn-Carroll (CHC) theory literature
- WAIS-V technical manual (index score structure)
