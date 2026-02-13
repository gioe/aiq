# Test Validity System

The validity system detects aberrant response patterns that may indicate cheating or invalid test-taking behavior in unproctored online testing. It uses statistical methods rather than privacy-invasive device tracking.

**Design Philosophy:**
- Flags are indicators, not proof of cheating
- Human review is required before any action
- Users have the right to explanation and appeal
- Statistical methods prioritized over device tracking

## Validity Check Methods

The system performs three complementary analyses on each completed test session:

### 1. Person-Fit Analysis

Analyzes whether a test-taker's response pattern matches expected patterns for their overall score. Detects when someone gets unexpected questions right/wrong given their ability level.

**How it works:**
- Categorizes test score into percentiles (high >70%, medium 40-70%, low <40%)
- Compares actual correct rates by difficulty against expected rates
- Calculates "fit ratio" = unexpected responses / total responses

**Flag:** `aberrant_response_pattern`
- Triggered when: fit_ratio >= 0.25 (or >= 0.40 for short tests)
- Severity: High
- Example: Low scorer getting multiple hard questions right while missing easy ones

### 2. Response Time Plausibility

Examines per-question response times to identify patterns suggesting invalid test-taking:

| Flag | Threshold | Severity | Meaning |
|------|-----------|----------|---------|
| `multiple_rapid_responses` | 3+ responses < 3 seconds | High | Random clicking or pre-known answers |
| `suspiciously_fast_on_hard` | 2+ correct hard < 10 seconds | High | Prior knowledge of specific answers |
| `extended_pauses` | Any response > 300 seconds | Medium | Answer lookup or distraction |
| `total_time_too_fast` | Total < 300 seconds | High | Unrealistically fast completion |
| `total_time_excessive` | Total > 7200 seconds | Medium | Extended lookup or multi-session |

### 3. Guttman Error Detection

Counts violations of expected difficulty ordering. In a "perfect" pattern, easier items are answered correctly and harder items incorrectly. Errors occur when harder items are correct but easier items are wrong.

**How it works:**
- Sorts items by empirical difficulty (p-value from historical data)
- Counts pairs where harder item correct + easier item incorrect
- Calculates error_rate = errors / (correct_count x incorrect_count)

**Interpretations:**
| Error Rate | Interpretation | Severity |
|------------|----------------|----------|
| > 30% | `high_errors_aberrant` | High |
| > 20% | `elevated_errors` | Medium |
| <= 20% | `normal` | None |

## Validity Status Determination

The three checks are combined into an overall validity status using severity scoring:

**Severity Points:**
| Finding | Points |
|---------|--------|
| Aberrant person-fit pattern | +2 |
| Each high-severity time flag | +2 |
| High Guttman errors | +2 |
| Elevated Guttman errors | +1 |

**Status Thresholds:**
| Severity Score | Status | Action |
|----------------|--------|--------|
| >= 4 | `invalid` | Requires admin review before trust |
| >= 2 | `suspect` | Flagged for potential review |
| < 2 | `valid` | No concerns |

**Confidence Score:** Calculated as `max(0.0, 1.0 - severity_score * 0.15)`

## Threshold Configuration

All thresholds are defined as constants in `app/core/validity_analysis.py`:

```python
# Person-Fit
FIT_RATIO_ABERRANT_THRESHOLD = 0.25        # Flag if >= 25% unexpected responses
SHORT_TEST_FIT_RATIO_THRESHOLD = 0.40      # Higher threshold for < 5 questions

# Response Time
RAPID_RESPONSE_THRESHOLD_SECONDS = 3       # Minimum time for legitimate response
RAPID_RESPONSE_COUNT_THRESHOLD = 3         # Count needed to flag
FAST_HARD_CORRECT_THRESHOLD_SECONDS = 10   # Fast correct on hard question
FAST_HARD_CORRECT_COUNT_THRESHOLD = 2      # Count needed to flag
EXTENDED_PAUSE_THRESHOLD_SECONDS = 300     # 5 minutes
TOTAL_TIME_TOO_FAST_SECONDS = 300          # 5 minutes minimum
TOTAL_TIME_EXCESSIVE_SECONDS = 7200        # 2 hours maximum

# Guttman Errors
GUTTMAN_ERROR_ABERRANT_THRESHOLD = 0.30    # High concern threshold
GUTTMAN_ERROR_ELEVATED_THRESHOLD = 0.20    # Elevated concern threshold
SHORT_TEST_GUTTMAN_ABERRANT_THRESHOLD = 0.45  # Adjusted for < 5 questions
SHORT_TEST_GUTTMAN_ELEVATED_THRESHOLD = 0.30

# Overall Assessment
SEVERITY_THRESHOLD_INVALID = 4             # Score for "invalid" status
SEVERITY_THRESHOLD_SUSPECT = 2             # Score for "suspect" status
MINIMUM_QUESTIONS_FOR_FULL_ANALYSIS = 5    # Threshold for short test adjustments
```

**Threshold Rationale:**
- Rapid response (3s): Minimum time to read and comprehend even simple questions
- Fast hard correct (10s): Hard questions require more processing time
- Extended pause (5 min): Normal breaks don't exceed this; longer suggests lookup
- Guttman 30%: Statistical research suggests this indicates aberrant patterns
- Short test adjustments: Smaller samples have higher variance, require larger deviations

## Edge Case Handling

| Edge Case | Behavior |
|-----------|----------|
| Empty responses | Skip checks, return `valid` by default |
| Missing time data | Skip time checks only, run other analyses |
| Missing difficulty data | Use fallback estimates (easy=0.75, medium=0.50, hard=0.25) |
| Short tests (< 5 items) | Use adjusted (higher) thresholds |
| Abandoned sessions | Return `incomplete` status, no flags |
| Re-validation | Idempotent - skip if already validated unless forced |

## Admin Endpoints

### View Session Validity
```
GET /v1/admin/sessions/{session_id}/validity
```
Returns detailed validity analysis including overall status, severity score, all flags with severity and details, breakdown by analysis type, and confidence score.

**Authentication:** `X-Admin-Token` header required

### Validity Report
```
GET /v1/admin/validity-report?days=30&status=suspect
```
Returns aggregate statistics: status counts, flag type breakdown, 7-day vs 30-day trend comparison, and sessions needing review.

**Query Parameters:**
- `days`: Time period to analyze (default: 30)
- `status`: Filter by validity status

**Authentication:** `X-Admin-Token` header required

### Override Validity
```
PATCH /v1/admin/sessions/{session_id}/validity
```
Allows admin to manually override validity status after review.

**Request Body:**
```json
{
  "validity_status": "valid",
  "override_reason": "Manual review confirmed legitimate pattern. User has consistent test history."
}
```

**Requirements:**
- Override reason must be at least 10 characters (audit trail)
- Override is logged with timestamp and admin ID
- Previous status is preserved for audit

**Authentication:** `X-Admin-Token` header required

## Admin Review Workflow

1. **Monitor:** Regularly check `/v1/admin/validity-report` for flagged sessions
2. **Investigate:** For suspect/invalid sessions, review:
   - Flag types and details
   - User's test history
   - Response patterns
   - Time distribution
3. **Decision:** Based on investigation:
   - **Clear false positive:** Override to `valid` with explanation
   - **Confirm concern:** Leave as `suspect`/`invalid`
   - **Take action:** Contact user or apply policy as appropriate
4. **Document:** Always provide detailed override reason for audit trail

## Ethical Considerations

1. **Presumption of Innocence:** Flags indicate statistical anomalies, not proof of cheating. Many legitimate test-takers may trigger flags due to reading speed, test anxiety, or unusual (but valid) cognitive profiles.

2. **Human Review Required:** The system never automatically penalizes users. All enforcement actions require human judgment after reviewing the full context.

3. **Right to Explanation:** If any action is taken based on validity flags, users must be informed of the basis for the decision in understandable terms.

4. **Appeal Mechanism:** Users should have a pathway to contest decisions and provide context that may explain flagged patterns.

5. **Privacy Protection:** The system uses only statistical analysis of response patterns. It does not collect:
   - Device fingerprints
   - IP tracking
   - Webcam/proctoring data
   - Keystroke dynamics
   - Browser history

6. **Proportional Response:** Any consequences should be proportional to the severity and confidence of the validity concern:
   - Minor flags: No action, monitoring only
   - Moderate concerns: Request explanation, offer retest
   - Clear violations: Policy enforcement with appeal rights

## Success Metrics

The validity system aims for:
- **Coverage:** All completed sessions have validity status assigned
- **Accuracy:** False positive rate < 5% (manually verified on sample)
- **Detection:** All major cheating patterns have detection logic
- **Non-punitive:** No automatic bans; human review required
- **Transparency:** All thresholds and logic documented
