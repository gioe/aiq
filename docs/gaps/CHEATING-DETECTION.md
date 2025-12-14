# Cheating Detection

## Problem Statement

AIQ administers tests in an unproctored online environment. Users take tests on personal devices without supervision, creating opportunities for:
- Looking up answers online
- Using calculators or tools
- Consulting others
- Taking screenshots to share questions
- Creating multiple accounts to preview questions

Without detection mechanisms, cheating undermines score validity and fairness for honest users.

## Types of Cheating Behavior

| Behavior | Detection Difficulty | Impact on Scores |
|----------|---------------------|------------------|
| Answer lookup (Google) | Medium | Inflated scores |
| Calculator use | Hard | Inflated math scores |
| Consulting others | Hard | Inflated scores |
| Multiple accounts | Medium | Preview advantage |
| Sharing questions | Hard | Pool contamination |
| Random clicking | Easy | Deflated scores |
| Account sharing | Medium | Score attribution |

## Detection Approaches

### 1. Statistical Detection (Person-Fit Statistics)

Detect aberrant response patterns that deviate from expected patterns.

### 2. Response Time Analysis

Identify implausible timing patterns (too fast, too slow, suspicious pauses).

### 3. Response Pattern Analysis

Detect patterns inconsistent with genuine test-taking (Guttman errors, answer patterns).

### 4. Technical Detection

Device fingerprinting, IP analysis, account behavior patterns.

## Current State

### What Exists

1. **Response data** - All answers recorded
2. **Timestamps** - When each answer submitted
3. **Session tracking** - Start/end times
4. **User accounts** - One per user (theoretically)

### What's Missing

1. **Person-fit statistics** - No lz or other fit indices
2. **Response time anomaly detection** - No flagging of suspicious times
3. **Guttman error analysis** - No pattern consistency checks
4. **Device/account analysis** - No multi-account detection
5. **Session validity flags** - No aggregate validity indicators

## Solution Requirements

### 1. Person-Fit Statistics (lz Index)

The lz (standardized log-likelihood) statistic measures how well a person's response pattern fits the expected pattern based on their ability level.

**Formula:**
```
lz = (l₀ - E(l₀)) / √Var(l₀)

Where:
l₀ = Σ[xᵢlog(Pᵢ) + (1-xᵢ)log(1-Pᵢ)]
xᵢ = response to item i (0 or 1)
Pᵢ = expected probability of correct response based on ability
```

**Interpretation:**
| lz Value | Interpretation |
|----------|---------------|
| -2 to +2 | Normal response pattern |
| < -2 | Unexpectedly poor performance (possible sandbagging, inattention) |
| > +2 | Unexpectedly good performance (possible cheating) |

**Simplified Implementation (without IRT):**

Without IRT parameters, use a heuristic approach:
```python
def calculate_person_fit_heuristic(
    responses: List[Tuple[bool, str]],  # (is_correct, difficulty_level)
    total_score: int
) -> Dict:
    """
    Calculate heuristic person-fit based on difficulty-response patterns.

    For a person with score X, we expect:
    - High probability of correct on easy items
    - Medium probability on medium items
    - Lower probability on hard items

    Deviations from this pattern are suspicious.
    """
    # Expected correct rates by difficulty given total score
    # (These are heuristic; real IRT would give precise values)

    expected_by_difficulty = {
        "easy": 0.85 if total_score >= 15 else 0.70 if total_score >= 10 else 0.50,
        "medium": 0.65 if total_score >= 15 else 0.50 if total_score >= 10 else 0.35,
        "hard": 0.45 if total_score >= 15 else 0.30 if total_score >= 10 else 0.15
    }

    # Count unexpected outcomes
    unexpected_correct = 0  # Got hard one right when expected wrong
    unexpected_incorrect = 0  # Got easy one wrong when expected right

    for is_correct, difficulty in responses:
        expected_p = expected_by_difficulty[difficulty]
        if is_correct and expected_p < 0.3:
            unexpected_correct += 1
        if not is_correct and expected_p > 0.7:
            unexpected_incorrect += 1

    # Flag if too many unexpected outcomes
    fit_ratio = (unexpected_correct + unexpected_incorrect) / len(responses)

    return {
        "unexpected_correct": unexpected_correct,
        "unexpected_incorrect": unexpected_incorrect,
        "fit_ratio": fit_ratio,
        "fit_flag": "aberrant" if fit_ratio > 0.25 else "normal"
    }
```

### 2. Response Time Plausibility Checks

**Function:**
```python
def check_response_time_plausibility(
    session_id: int,
    responses: List[Dict]  # Each has time_spent_seconds
) -> Dict:
    """
    Analyze response times for plausibility.

    Flags:
    - rapid_responses: < 3 seconds (can't have read the question)
    - suspiciously_fast: Correct on hard questions in < 10 seconds
    - extended_pause: > 5 minutes on single question
    - total_too_fast: Entire test in < 5 minutes
    - total_too_slow: Entire test > 2 hours
    """
    flags = []

    rapid_count = sum(1 for r in responses if r["time_seconds"] < 3)
    if rapid_count >= 3:
        flags.append({
            "type": "multiple_rapid_responses",
            "count": rapid_count,
            "severity": "high"
        })

    fast_correct_hard = sum(
        1 for r in responses
        if r["is_correct"] and r["difficulty"] == "hard" and r["time_seconds"] < 10
    )
    if fast_correct_hard >= 2:
        flags.append({
            "type": "suspiciously_fast_on_hard",
            "count": fast_correct_hard,
            "severity": "high"
        })

    extended = [r for r in responses if r["time_seconds"] > 300]
    if extended:
        flags.append({
            "type": "extended_pauses",
            "count": len(extended),
            "severity": "medium"
        })

    total_time = sum(r["time_seconds"] for r in responses)
    if total_time < 300:  # < 5 minutes for 20 questions
        flags.append({
            "type": "total_time_too_fast",
            "total_seconds": total_time,
            "severity": "high"
        })

    if total_time > 7200:  # > 2 hours
        flags.append({
            "type": "total_time_excessive",
            "total_seconds": total_time,
            "severity": "medium"
        })

    return {
        "flags": flags,
        "flag_count": len(flags),
        "high_severity_count": sum(1 for f in flags if f["severity"] == "high"),
        "validity_concern": any(f["severity"] == "high" for f in flags)
    }
```

### 3. Guttman Error Detection

A Guttman error occurs when someone gets a hard question right but an easier question wrong. While some Guttman errors are normal, too many suggest aberrant responding.

**Concept:**
If items are ordered by difficulty, a "perfect" Guttman pattern would be:
- Score 15/20: First 15 correct, last 5 incorrect
- Reality: Some deviation expected, but not too much

**Function:**
```python
def count_guttman_errors(
    responses: List[Tuple[bool, float]]  # (is_correct, empirical_difficulty)
) -> Dict:
    """
    Count Guttman-type errors in response pattern.

    A Guttman error: Getting a harder item correct while missing an easier item.

    Args:
        responses: List of (is_correct, empirical_difficulty) tuples
                  where empirical_difficulty is the p-value (higher = easier)

    Returns:
        {
            "guttman_errors": int,
            "max_possible_errors": int,
            "error_rate": float,
            "interpretation": str
        }
    """
    # Sort by difficulty (hardest first, lowest p-value first)
    sorted_by_difficulty = sorted(responses, key=lambda x: x[1])

    errors = 0
    max_errors = 0

    # For each pair, check if harder item correct & easier item incorrect
    for i in range(len(sorted_by_difficulty)):
        for j in range(i + 1, len(sorted_by_difficulty)):
            harder_item = sorted_by_difficulty[i]
            easier_item = sorted_by_difficulty[j]

            # This is a potential error situation
            max_errors += 1

            # Guttman error: harder correct, easier incorrect
            if harder_item[0] and not easier_item[0]:
                errors += 1

    error_rate = errors / max_errors if max_errors > 0 else 0

    if error_rate > 0.30:
        interpretation = "high_errors_aberrant"
    elif error_rate > 0.20:
        interpretation = "elevated_errors"
    else:
        interpretation = "normal"

    return {
        "guttman_errors": errors,
        "max_possible_errors": max_errors,
        "error_rate": error_rate,
        "interpretation": interpretation
    }
```

### 4. Session Validity Flag

Combine all validity checks into a single assessment:

**Database Addition:**
```python
# Add to TestSession or TestResult model
validity_flags = Column(JSON, nullable=True)
validity_status = Column(String(20), default="valid")  # valid, suspect, invalid
```

**Function:**
```python
def assess_session_validity(
    session_id: int,
    person_fit: Dict,
    time_check: Dict,
    guttman_check: Dict
) -> Dict:
    """
    Combine all validity checks into overall assessment.

    Returns:
        {
            "status": "valid" | "suspect" | "invalid",
            "flags": [...],
            "confidence": float,  # 0-1, how confident we are it's valid
            "details": {...}
        }
    """
    flags = []
    severity_score = 0

    # Person fit
    if person_fit.get("fit_flag") == "aberrant":
        flags.append("aberrant_response_pattern")
        severity_score += 2

    # Time checks
    if time_check.get("validity_concern"):
        flags.extend([f["type"] for f in time_check.get("flags", [])])
        severity_score += time_check.get("high_severity_count", 0) * 2

    # Guttman errors
    if guttman_check.get("interpretation") == "high_errors_aberrant":
        flags.append("high_guttman_errors")
        severity_score += 2
    elif guttman_check.get("interpretation") == "elevated_errors":
        flags.append("elevated_guttman_errors")
        severity_score += 1

    # Determine status
    if severity_score >= 4:
        status = "invalid"
    elif severity_score >= 2:
        status = "suspect"
    else:
        status = "valid"

    # Confidence (inverse of severity, normalized)
    confidence = max(0, 1 - (severity_score / 6))

    return {
        "status": status,
        "flags": flags,
        "severity_score": severity_score,
        "confidence": round(confidence, 2),
        "details": {
            "person_fit": person_fit,
            "time_check": time_check,
            "guttman_check": guttman_check
        }
    }
```

### 5. Device/Account Analysis (Optional, Privacy-Sensitive)

**Note:** This section involves collecting additional user data. Implementation requires careful consideration of:
- Privacy regulations (GDPR, CCPA)
- App Store guidelines
- User consent
- Data storage policies

**Potential Signals:**

1. **Device fingerprint**
   - Device model, OS version
   - Screen dimensions
   - Unique device ID (if available)
   - Purpose: Detect same device used by multiple accounts

2. **IP analysis**
   - Geographic consistency
   - VPN/proxy detection
   - Multiple accounts from same IP
   - Purpose: Detect account sharing or multi-account abuse

3. **Behavioral patterns**
   - Time of day patterns
   - Test pacing consistency
   - Navigation patterns
   - Purpose: Detect account sharing (different users, same account)

**Implementation Considerations:**
- Store hashed/anonymized identifiers, not raw data
- Allow users to opt out
- Don't use for punitive action without clear evidence
- Focus on flagging, not automatic bans

**Recommendation:** Start with statistical detection (person-fit, Guttman errors, timing) before implementing device tracking. These are less privacy-invasive and often sufficient.

## Implementation Dependencies

### Prerequisites
- Per-question response times (see TIME-STANDARDIZATION.md)
- Empirical difficulty values (for Guttman analysis)
- Response data ✓

### Database Changes

Add to TestResult or TestSession:
```python
validity_status = Column(String(20), default="valid")
validity_flags = Column(JSON, nullable=True)
validity_checked_at = Column(DateTime, nullable=True)
```

### When to Run Checks

**Option A: Post-submission (synchronous)**
- Run all checks when test is submitted
- Store results immediately
- Pro: Results available instantly
- Con: Adds latency to submission

**Option B: Post-submission (async)**
- Submit test normally
- Run checks in background job
- Update validity status when complete
- Pro: Fast submission
- Con: Validity not immediately available

**Option C: Batch processing**
- Run validity checks nightly on recent submissions
- Pro: No submission impact
- Con: Delayed detection

**Recommendation:** Option A for MVP (checks are fast), Option B for scale.

### Related Code Locations
- `backend/app/core/question_analytics.py` - Similar analytics patterns
- Test submission endpoint - Trigger validity checks
- `backend/app/models/models.py` - Add validity fields

## What To Do With Flags

### Immediate Actions (Automated)

1. **Flag the session** - Store validity status for admin review
2. **Log for analysis** - Track patterns across users
3. **Exclude from analytics** - Don't use invalid sessions for norming

### No Immediate Action

1. **Don't auto-ban users** - False positives are possible
2. **Don't hide scores from users** - Show them, but flag internally
3. **Don't notify users of suspicion** - Avoid false accusations

### Admin Review

For sessions flagged as "invalid" or "suspect":
1. Provide detailed breakdown of flags
2. Show response pattern visualization
3. Allow manual override of validity status
4. Track admin decisions for model improvement

## Validity Dashboard

**Endpoint:** `GET /v1/admin/validity-report`

**Response:**
```json
{
    "summary": {
        "total_sessions_analyzed": 1000,
        "valid": 920,
        "suspect": 60,
        "invalid": 20
    },
    "by_flag_type": {
        "aberrant_response_pattern": 15,
        "multiple_rapid_responses": 25,
        "suspiciously_fast_on_hard": 18,
        "extended_pauses": 45,
        "high_guttman_errors": 12
    },
    "trends": {
        "invalid_rate_7d": 0.018,
        "invalid_rate_30d": 0.022,
        "trend": "stable"
    },
    "action_needed": [
        {
            "session_id": 4567,
            "user_id": 123,
            "flags": ["aberrant_response_pattern", "suspiciously_fast_on_hard"],
            "severity_score": 4,
            "completed_at": "2025-12-05T14:30:00Z"
        }
    ]
}
```

## Success Criteria

1. **Detection:** All completed sessions have validity status assigned
2. **Accuracy:** False positive rate < 5% (manually verified sample)
3. **Coverage:** All major cheating patterns have detection logic
4. **Visibility:** Admin dashboard shows validity metrics
5. **Non-punitive:** Users are not auto-banned; human review required
6. **Privacy-respecting:** Statistical methods used before device tracking

## Testing Strategy

1. **Unit Tests:**
   - Test person-fit calculation with known patterns
   - Test Guttman error counting with constructed sequences
   - Test time plausibility at threshold boundaries

2. **Integration Tests:**
   - Create sessions with known cheating patterns
   - Verify correct flagging
   - Verify valid sessions not falsely flagged

3. **Simulation:**
   - Generate synthetic response patterns
   - Known-cheater patterns vs. known-valid patterns
   - Verify detection rates and false positive rates

4. **Manual Validation:**
   - Review sample of flagged sessions
   - Estimate false positive rate
   - Tune thresholds if needed

## Ethical Considerations

1. **Presumption of innocence** - Flags are indicators, not proof
2. **Human review required** - No automated punishment
3. **Right to explanation** - If action taken, explain basis
4. **Appeal mechanism** - Users can contest decisions
5. **Privacy protection** - Minimal data collection
6. **Proportional response** - Punishment fits severity

## References

- Person-fit statistics: Meijer, R.R. & Sijtsma, K. (2001)
- Guttman scaling and errors
- IQ_METHODOLOGY.md, Section 11 (Limitations - cheating risk)
- Classical Test Theory response pattern analysis
