# Memory Question Approval Rate Monitoring Report

**Task**: TASK-756
**Date**: January 28, 2026
**Status**: Analysis Complete

## Executive Summary

Memory question generation is performing well after the TASK-755 fix that added stimulus field validation. Questions with properly populated stimulus fields achieve a **100% approval rate** with an average judge score of **0.915**.

## Key Findings

### Overall Memory Question Statistics

| Metric | Value |
|--------|-------|
| Total Memory Questions (all time) | 119 |
| Overall Approval Rate | 81.5% |
| Average Judge Score | 0.867 |
| Min Judge Score | 0.640 |
| Max Judge Score | 0.990 |

### Approval Rate by Date

| Date | Total | Approved | Rejected | Approval Rate | Avg Score |
|------|-------|----------|----------|---------------|-----------|
| 2026-01-28 | 83 | 83 | 0 | 100.0% | 0.919 |
| 2026-01-27 | 6 | 6 | 0 | 100.0% | 0.912 |
| 2026-01-26 | 28 | 7 | 21 | 25.0% | 0.709 |
| 2025-11-18 | 1 | 0 | 1 | 0.0% | 0.690 |
| 2025-11-17 | 1 | 1 | 0 | 100.0% | 0.895 |

### Post-Fix Performance (Questions with Valid Stimulus)

| Date | Total | Approved | Approval Rate | Avg Score | Min Score |
|------|-------|----------|---------------|-----------|-----------|
| 2026-01-28 | 44 | 44 | 100.0% | 0.915 | 0.710 |

### Approval Rate by Difficulty Level

| Difficulty | Count | Approved | Approval Rate | Avg Score |
|------------|-------|----------|---------------|-----------|
| EASY | 16 | 14 | 87.5% | 0.865 |
| MEDIUM | 81 | 62 | 76.5% | 0.858 |
| HARD | 22 | 21 | 95.5% | 0.900 |

### Comparison to Other Question Types

| Question Type | Total | Approved | Approval Rate | Avg Score |
|---------------|-------|----------|---------------|-----------|
| PATTERN | 35 | 35 | 100.0% | 0.923 |
| LOGIC | 165 | 165 | 100.0% | 0.870 |
| MATH | 194 | 193 | 99.5% | 0.940 |
| VERBAL | 114 | 106 | 93.0% | 0.858 |
| MEMORY | 119 | 97 | 81.5% | 0.867 |
| SPATIAL | 1 | 0 | 0.0% | 0.610 |

## Root Cause Analysis

### Low Approval Rate on January 26, 2026

The 25% approval rate on January 26 was caused by memory questions **missing the required stimulus field**. These questions embedded the stimulus content in the question_text field instead of the dedicated stimulus field.

**Example of rejected question (id=208, score=0.640)**:
```
question_text: "MEMORIZE THIS SEQUENCE: 7, 3, 9, 2, 5, 8, 4. What is the sum..."
stimulus: NULL
```

This was fixed in **TASK-755** (commit 2299423) which added:
1. Stimulus field validation in the generator
2. Updated judge prompt to explicitly handle memory questions with two-phase delivery
3. Unit tests for stimulus validation

### Post-Fix Performance

After TASK-755, memory questions with properly populated stimulus fields achieve:
- **100% approval rate**
- **0.915 average judge score**
- **0.710 minimum score** (above the 0.7 threshold)

## Recommendations

### 1. Continue Monitoring

Memory question generation should continue to be monitored over the next 3-5 days to ensure consistent performance. Key metrics to track:

- Daily approval rate (target: ≥95%)
- Average judge score (target: ≥0.85)
- Questions with missing stimulus (target: 0)

### 2. Clean Up Legacy Questions

Consider deactivating the 22 rejected memory questions (judge_score < 0.7) from the question pool:

```sql
UPDATE questions
SET is_active = false
WHERE question_type = 'MEMORY'
  AND judge_score < 0.7;
```

### 3. Monitor Stimulus Field Population

Add a periodic check to ensure all new memory questions have valid stimulus fields:

```sql
SELECT COUNT(*) as missing_stimulus_count
FROM questions
WHERE question_type = 'MEMORY'
  AND created_at > NOW() - INTERVAL '24 hours'
  AND (stimulus IS NULL OR stimulus = '');
```

This should return 0 if the validation is working correctly.

## SQL Queries for Ongoing Monitoring

### Daily Approval Rate Check

```sql
SELECT
    DATE(created_at) as date,
    COUNT(*) as total,
    COUNT(CASE WHEN judge_score >= 0.7 THEN 1 END) as approved,
    ROUND(100.0 * COUNT(CASE WHEN judge_score >= 0.7 THEN 1 END) / COUNT(*), 1) as approval_rate_pct,
    ROUND(AVG(judge_score)::numeric, 3) as avg_score
FROM questions
WHERE question_type = 'MEMORY'
    AND judge_score IS NOT NULL
    AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY DATE(created_at) DESC;
```

### Stimulus Validation Check

```sql
SELECT
    CASE WHEN stimulus IS NULL OR stimulus = '' THEN 'Missing' ELSE 'Present' END as stimulus_status,
    COUNT(*) as count,
    ROUND(AVG(judge_score)::numeric, 3) as avg_score
FROM questions
WHERE question_type = 'MEMORY'
    AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY CASE WHEN stimulus IS NULL OR stimulus = '' THEN 'Missing' ELSE 'Present' END;
```

## Conclusion

Memory question generation is now functioning correctly. The TASK-755 fix resolved the stimulus field validation issue, and questions generated after the fix achieve a 100% approval rate with high judge scores. Continued monitoring over the next few days will confirm sustained performance.
