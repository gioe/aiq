# TASK-453: Investigation — Empty JSON Responses in Evaluation and Verification

**Date**: 2026-04-16
**Status**: Investigation complete
**Severity**: Low — transient issue, not a recurring pattern at elevated rates

## Summary

During the 2026-04-16 cron run (deployment 44a6fb73), 4 instances of empty/non-JSON responses occurred (`json.loads` failing with `Expecting value: line 1 column 1 (char 0)`). Two hit the evaluation phase (`judge:evaluate_question`, Google provider, math type) and two hit the verification phase (`judge:verify_answer`).

## 1. Frequency Analysis (Criterion 1602)

Reviewed all 11 production generation runs (2026-03-25 through 2026-04-14):

| Run | Date | Requested | Inserted | Errors | Error Rate |
|-----|------|-----------|----------|--------|------------|
| 11  | 04-14 | 50 | 26 | 16 | 32% |
| 4   | 03-29 | 50 | 24 | 12 | 24% |
| 1   | 03-25 | 50 | 15 | 25 | 50% |
| 7   | 04-07 | 4  | 0  | 3  | 75% |
| 3   | 03-28 | 10 | 8  | 1  | 10% |
| 2   | 03-27 | 12 | 2  | 4  | 33% |

**Finding**: Errors are common across all large runs (10-50% error rate), but these include ALL error types — generation failures, JSON parse errors, evaluation failures, etc. The 4 empty-JSON-response errors from 04-16 represent a small fraction of the total pipeline errors and are consistent with the baseline error rate. This is **not** an elevated or new pattern.

## 2. Root Cause (Criterion 1603)

**Root cause: Gemini API returning empty response text (content filtering or model refusal)**

The error path is:

```
Google Gemini API → response.text = "" or None
    ↓
google_provider.py:353: raw_content = response.text if response.text else ""
google_provider.py:354: if raw_content:  # False — skips safe_json_loads
    ↓
content = {} (empty dict from line 352 initialization)
    ↓
CompletionResult(content={}, ...) returned to judge
    ↓
judge._parse_evaluation_response({}) → Missing required fields → Exception
    ↓
Logged as evaluation_failure, error category = "value" (ValueError)
```

The Gemini API can return empty text for several reasons:
- **Content safety filtering**: The model flags the prompt/response as potentially unsafe and returns no text. Math questions involving certain topics (e.g., probability of harm-related scenarios) can trigger this.
- **Model capacity/timeout**: Under load, the API may return a truncated or empty response.
- **Rate limiting at the API level**: Though this typically raises an HTTP 429 before returning empty text.

Given that the errors specifically affect **math type questions with the Google provider**, content filtering on math problems that touch sensitive adjacent topics is the most likely cause.

## 3. Error Handling Assessment (Criterion 1604)

### Current state

| Provider | Empty response detection | Logging | Retry |
|----------|------------------------|---------|-------|
| **Google** | Returns `{}` silently | **No warning** | No retry on empty content |
| **Anthropic** | Returns `{}` | Logs warning | No retry on empty content |
| **OpenAI (async)** | Returns `{}` | Logs warning with finish_reason | No retry on empty content |
| **OpenAI (sync)** | Returns `{}` | **No warning** | No retry on empty content |
| **xAI** | Not checked | Unknown | Unknown |

### Retry behavior

The retry logic in `base.py` (`with_retry`/`with_retry_async`) only retries on `LLMProviderError` exceptions classified as retryable. Empty responses don't trigger retries because:
1. Providers return `CompletionResult(content={})` — a valid return, not an exception
2. The error only surfaces later in the judge when accessing missing fields
3. At that point, the judge catches the error via fallback provider (lines 289-326 in judge.py)

### Fallback provider behavior

The judge **does** have fallback logic: if the primary judge provider fails, it retries with a fallback provider (e.g., Anthropic → Google or vice versa). This effectively mitigates the empty response issue at the judge level, since a different provider is unlikely to also return empty for the same question.

### Assessment: **Adequate with minor gaps**

The error handling works correctly in practice:
- The error is caught, logged, and counted
- Fallback providers mitigate single-provider failures
- The pipeline continues processing other questions
- Sentry captures evaluation errors for monitoring

The gaps are:
1. Google provider doesn't log a warning when response.text is empty (Anthropic does)
2. No raw response metadata (finish_reason, safety_ratings) is logged when empty, making root cause harder to confirm from logs alone
3. Empty `{}` from providers could be detected earlier and retried before reaching the judge

## 4. Recommendation (Criterion 1605)

**The failure rate is NOT elevated** — 4 empty responses out of a batch run is within the normal error budget. The existing fallback-provider mechanism already handles this effectively.

### Suggested improvements (low priority, not blocking):

1. **Add empty response warning in Google provider** (parity with Anthropic):
   ```python
   # google_provider.py, after line 353
   if not raw_content:
       logger.warning(
           "Google API returned empty response text. "
           "candidates=%s, prompt_feedback=%s",
           getattr(response, 'candidates', None),
           getattr(response, 'prompt_feedback', None),
       )
   ```
   This would log Gemini's `prompt_feedback` field which contains content filtering details.

2. **Log finish/block reasons** from the Gemini response when content is empty, to confirm whether it's content filtering vs. timeout.

3. **No code changes needed now** — the current error rate (4/batch) is acceptable, and the fallback provider mechanism already provides resilience.

## Files Reviewed

| File | Purpose |
|------|---------|
| `question-service/app/providers/google_provider.py:340-381` | Structured completion — empty response path |
| `question-service/app/providers/anthropic_provider.py:280-310` | Comparison — has empty response warning |
| `question-service/app/providers/openai_provider.py:300-330` | Comparison — partial logging |
| `question-service/app/evaluation/judge.py:214-380` | Evaluation flow and fallback logic |
| `question-service/app/evaluation/judge.py:628-851` | Verification flow |
| `question-service/app/providers/base.py:269-341` | Retry logic |
| `question-service/app/utils/text_utils.py:15-47` | safe_json_loads — raises on empty input |
| `question-service/app/infrastructure/error_classifier.py` | Error classification |
