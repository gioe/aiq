# Memory Questions: Two-Phase Model Implementation

## Overview

This plan outlines the implementation of a two-phase data model for memory questions in the AIQ system. Currently, memory questions combine stimulus (data to memorize) and question (what to recall) in a single `question_text` field, causing a 50% judge rejection rate because the stimulus remains visible when answering.

## Strategic Context

### Problem Statement

Memory questions inherently have two distinct phases:
1. **Stimulus Phase**: Data to memorize (e.g., a list, sequence, or passage) that should be shown first
2. **Question Phase**: What to recall (shown after the stimulus is hidden)

Currently, the `GeneratedQuestion` model has a single `question_text` field that combines both:
```
"MEMORIZE THIS LIST: maple, oak, dolphin... Which item is a mammal?"
```

This creates a fundamental UX/delivery problem:
- When the judge evaluates the question, it sees both stimulus and question together
- The judge correctly identifies that this isn't a real memory test (data is still visible)
- ~50% rejection rate for memory questions despite being otherwise valid
- The judge is treating a delivery mechanism problem as a content quality problem

### Success Criteria

1. Memory questions achieve approval rates comparable to other question types (70%+)
2. The judge prompt correctly evaluates memory questions understanding the two-phase delivery
3. Generator produces properly structured memory questions with separate stimulus and question
4. Backend API exposes the stimulus field for client consumption
5. iOS app implements two-phase rendering (show stimulus → hide → show question)
6. No breaking changes to existing questions or API contracts (backward compatible)

### Why Now?

- Memory questions are critical for comprehensive cognitive assessment
- Current 50% rejection rate is creating an artificial bottleneck in question generation
- Recent judge prompt improvements (TASK-445) have addressed related issues, making this the right time to solve the underlying structural problem
- The fix is well-scoped and has clear benefits without complex dependencies

## Technical Approach

### High-Level Architecture

The solution adds an optional `stimulus` field to the question data model throughout the entire stack:

```
question-service (generation)
  → database (storage)
    → backend API (delivery)
      → iOS app (rendering)
```

**Key Design Decisions:**
1. **Optional Field**: `stimulus` is nullable to maintain backward compatibility with existing questions
2. **Type-Specific**: Only memory questions will have non-null stimulus values
3. **Judge-Aware**: Judge prompt will be updated to understand and evaluate two-phase structure
4. **Generator-Aware**: Memory question generation prompt will instruct LLMs to output structured format

### Key Decisions & Tradeoffs

#### Decision 1: Optional vs Required Field
**Choice**: Make `stimulus` an optional field (nullable)

**Rationale**:
- Maintains backward compatibility with existing questions in the database
- Only memory questions need this field; other question types would have NULL values
- Allows incremental rollout without requiring data migration for existing questions

**Tradeoff**: Requires nil-checks throughout the codebase, but this is standard practice and worth the flexibility

#### Decision 2: Database Column vs JSON Metadata
**Choice**: Add dedicated `stimulus` column to questions table

**Rationale**:
- First-class field allows efficient querying and indexing if needed
- Clearer data model that makes the two-phase structure explicit
- Avoids JSON parsing overhead in API layer
- Type safety at database level

**Tradeoff**: Requires database migration, but this is a one-time cost and aligns with our schema evolution strategy

#### Decision 3: Judge Prompt Update Strategy
**Choice**: Update existing judge prompt with memory-specific guidance rather than creating separate memory judge

**Rationale**:
- Simpler architecture with single judge implementation
- Memory questions should still be evaluated on same quality dimensions (clarity, validity, creativity, etc.)
- Only the interpretation of what constitutes a valid memory question needs clarification

**Tradeoff**: Slightly more complex prompt, but still maintainable and clearer than multiple judge implementations

### Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Breaking changes to existing API consumers | High | Low | Make field optional, maintain backward compatibility |
| Judge still rejects properly structured questions | Medium | Low | Update judge prompt with explicit two-phase guidance, test thoroughly |
| Generator fails to produce structured format | Medium | Medium | Update prompts with clear examples, validate output parsing |
| iOS app rendering complexity | Low | Low | Phased rollout: deploy backend first, then iOS update |
| Database migration issues on production | Medium | Low | Test migration on staging, ensure rollback capability |

## Implementation Plan

### Phase 1: Data Model & Database Foundation
**Goal**: Establish the stimulus field in core data structures and database
**Duration**: 2-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Add `stimulus` field to `GeneratedQuestion` model in question-service | None | 30 min | Update `/Users/mattgioe/aiq/question-service/app/models.py` with Optional[str] field |
| 1.2 | Update `GeneratedQuestion.to_dict()` method to include stimulus | 1.1 | 15 min | Ensure stimulus is serialized for database insertion |
| 1.3 | Add `stimulus` column to questions table in question-service database.py | 1.1 | 30 min | Update `QuestionModel` in `/Users/mattgioe/aiq/question-service/app/database.py` |
| 1.4 | Update database insert methods to handle stimulus field | 1.3 | 30 min | Modify `insert_question`, `insert_evaluated_question`, and batch methods |
| 1.5 | Create Alembic migration for adding stimulus column to backend database | None | 45 min | Generate migration in `/Users/mattgioe/aiq/backend/alembic/versions/` |
| 1.6 | Add `stimulus` field to backend Question model | None | 30 min | Update `/Users/mattgioe/aiq/backend/app/models/models.py` |
| 1.7 | Add `stimulus` field to backend QuestionResponse schema | 1.6 | 20 min | Update `/Users/mattgioe/aiq/backend/app/schemas/questions.py` |

### Phase 2: Question Generation & Evaluation
**Goal**: Update generation prompts and judge to handle two-phase structure
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Update memory question generation prompt to output structured format | 1.1 | 60 min | Modify `QUESTION_TYPE_PROMPTS[QuestionType.MEMORY]` in prompts.py to request separate stimulus and question_text |
| 2.2 | Update JSON response format schema to include optional stimulus field | 2.1 | 20 min | Add stimulus to `JSON_RESPONSE_FORMAT` in prompts.py |
| 2.3 | Update judge prompt to evaluate memory questions with two-phase understanding | None | 45 min | Modify `build_judge_prompt` in prompts.py to clarify memory question delivery |
| 2.4 | Update question parsing logic in generator to handle stimulus field | 2.1, 1.1 | 45 min | Modify `_parse_generated_response` in generator.py to extract stimulus |
| 2.5 | Update regeneration prompt to handle stimulus field | 2.1 | 30 min | Modify `build_regeneration_prompt` in prompts.py |
| 2.6 | Increment PROMPT_VERSION in database.py | 2.1, 2.3 | 5 min | Update from "2.0" to "2.1" to track this change |

### Phase 3: Testing & Validation
**Goal**: Ensure changes work correctly and don't break existing functionality
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Update unit tests for GeneratedQuestion model with stimulus field | 1.1 | 30 min | Update tests in `/Users/mattgioe/aiq/question-service/tests/test_models.py` if exists |
| 3.2 | Update unit tests for database operations with stimulus field | 1.4 | 30 min | Update `/Users/mattgioe/aiq/question-service/tests/test_database.py` |
| 3.3 | Update unit tests for judge evaluation with memory questions | 2.3 | 45 min | Update `/Users/mattgioe/aiq/question-service/tests/test_judge.py` |
| 3.4 | Generate test memory questions to validate end-to-end flow | 2.4, 1.4 | 45 min | Use run_generation.py to generate memory questions and verify structure |
| 3.5 | Verify backward compatibility with existing questions (no stimulus) | 1.4, 2.4 | 30 min | Test that questions without stimulus field still work correctly |

### Phase 4: Backend API Deployment
**Goal**: Deploy database migration and expose stimulus field in API
**Duration**: 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Run Alembic migration on development database | 1.5 | 15 min | Test migration locally first |
| 4.2 | Verify API returns stimulus field in question responses | 1.7, 4.1 | 20 min | Test GET /v1/questions endpoints |
| 4.3 | Update OpenAPI schema if needed | 1.7 | 15 min | Regenerate if using automated schema generation |
| 4.4 | Deploy backend changes to staging Railway environment | 1.5, 1.6, 1.7 | 30 min | Deploy and verify migration runs successfully |
| 4.5 | Run Alembic migration on production database | 4.4 | 15 min | Execute migration on production after staging validation |
| 4.6 | Deploy backend changes to production Railway environment | 4.5 | 20 min | Deploy API changes to production |

### Phase 5: iOS Client Implementation
**Goal**: Implement two-phase rendering in iOS app for memory questions
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Regenerate OpenAPI client in iOS to include stimulus field | 4.3 | 20 min | Run openapi-generator to update AIQAPIClient package |
| 5.2 | Create MemoryQuestionView component for two-phase rendering | 5.1 | 90 min | New SwiftUI view: show stimulus → "Continue" button → hide stimulus → show question |
| 5.3 | Update QuestionCardView to conditionally render MemoryQuestionView | 5.2 | 30 min | Add logic to detect memory questions with stimulus and use new view |
| 5.4 | Add unit tests for MemoryQuestionView | 5.2 | 45 min | Test phase transitions and state management |
| 5.5 | Update question mocks to include stimulus field | 5.1 | 20 min | Add stimulus to MockDataFactory for testing |
| 5.6 | Manual testing of memory question flow in iOS simulator | 5.3 | 30 min | Validate UX and ensure smooth transitions |

### Phase 6: Validation & Monitoring
**Goal**: Confirm improved approval rates and monitor for issues
**Duration**: Ongoing (1 week observation)

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Generate batch of memory questions with new prompts | 2.4, 4.6 | 30 min | Run production generation of memory questions |
| 6.2 | Monitor memory question approval rates | 6.1 | 30 min | Track judge scores for memory questions over 3-5 days |
| 6.3 | Compare approval rates before/after change | 6.2 | 20 min | Calculate improvement vs baseline ~50% rate |
| 6.4 | Collect user feedback on memory question UX (if beta available) | 5.6 | Ongoing | Monitor for any confusion or issues with two-phase flow |
| 6.5 | Document findings and close out project | 6.3 | 30 min | Update this plan with actual results and learnings |

## Open Questions

1. **Should we backfill existing memory questions?**
   - Existing memory questions in the database have combined stimulus+question in question_text
   - Options: (a) Leave as-is and only new questions use stimulus field, (b) Write script to parse and split existing questions
   - Recommendation: Leave as-is for Phase 1. If we want to backfill, create separate project after validating new structure works

2. **Should stimulus support rich formatting?**
   - Current: Plain text stimulus
   - Future consideration: Markdown or HTML for formatted lists, tables, etc.
   - Recommendation: Start with plain text, revisit if formatting becomes a real need

3. **What is the optimal stimulus display duration?**
   - iOS app should show stimulus for some duration before allowing user to proceed
   - Options: (a) User-controlled (continue button), (b) Fixed timer (e.g., 10 seconds), (c) Adaptive based on stimulus length
   - Recommendation: Start with user-controlled button, add analytics to inform future timer-based approach

4. **Should we add stimulus to question embeddings?**
   - Current: Embeddings generated from question_text only
   - Consideration: Should embeddings include stimulus for more accurate semantic similarity?
   - Recommendation: Include stimulus in embedding generation for memory questions (concatenate stimulus + question_text)

## Dependencies

### External Services
- **PostgreSQL Database**: Backend production database (Railway)
- **OpenAPI Generator**: iOS client code generation
- **Alembic**: Database migration tool

### Internal Components
- **question-service**: Question generation pipeline
- **backend**: FastAPI backend
- **iOS app**: SwiftUI mobile client
- **OpenAPI schema**: API contract definition

### Testing Requirements
- SQLite local database for question-service testing
- Railway staging environment for integration testing
- iOS Simulator for client testing

## Rollback Strategy

If issues arise in production:

1. **Database rollback**: Alembic migration is non-destructive (adds nullable column). Can rollback via `alembic downgrade -1`
2. **API rollback**: Field is optional, so old clients will continue working. Can rollback to previous commit if needed.
3. **iOS rollback**: App will gracefully handle missing stimulus field (optional). Can push hotfix if rendering issues occur.

**Key principle**: All changes are backward compatible, minimizing rollback risk.

## Success Metrics

- **Primary**: Memory question approval rate increases from ~50% to 70%+ (matching other question types)
- **Secondary**: Zero API errors related to stimulus field in production logs (first 48 hours)
- **User Experience**: No user-reported issues with memory question rendering (if beta feedback available)
- **Technical**: All unit tests pass, database migrations complete successfully

## Approval Rate Comparison (TASK-757 Analysis)

**Date**: January 28, 2026

### Before/After Summary

| Period | Total Questions | Approved | Approval Rate | Avg Judge Score |
|--------|-----------------|----------|---------------|-----------------|
| **Pre-Fix** (before 1/27) | 30 | 8 | 26.7% | 0.71 |
| **Post-Fix** (1/27-1/28) | 89 | 89 | **100.0%** | 0.92 |

### Improvement Calculation

```
Baseline approval rate: 26.7% (30 questions before TASK-755)
Post-fix approval rate: 100.0% (89 questions after TASK-755)

Absolute improvement: +73.3 percentage points
Relative improvement: 3.75x (from 26.7% to 100%)
```

**Note**: The original plan estimated ~50% baseline, but actual measured baseline was 26.7% (primarily due to the January 26 batch with 25% approval rate). The improvement is therefore even more significant than expected.

### Day-by-Day Breakdown

| Date | Total | Approved | Rate | Avg Score | Notes |
|------|-------|----------|------|-----------|-------|
| 2025-11-17 | 1 | 1 | 100% | 0.895 | Pre-fix, passed |
| 2025-11-18 | 1 | 0 | 0% | 0.690 | Pre-fix, failed |
| 2026-01-26 | 28 | 7 | **25%** | 0.709 | Pre-fix, stimulus missing |
| 2026-01-27 | 6 | 6 | **100%** | 0.912 | Post-fix |
| 2026-01-28 | 83 | 83 | **100%** | 0.919 | Post-fix, production batch |

### Root Cause Confirmed

The pre-fix questions failed because they embedded stimulus content directly in `question_text` with `stimulus: NULL`. The judge correctly identified these as invalid memory tests (data visible during answering).

**Example rejected question (pre-fix)**:
```
question_text: "MEMORIZE THIS SEQUENCE: 7, 3, 9, 2, 5, 8, 4. What is the sum..."
stimulus: NULL
judge_score: 0.640 (rejected, below 0.7 threshold)
```

**Example approved question (post-fix)**:
```
stimulus: "7, 3, 9, 2, 5, 8, 4"
question_text: "What is the sum of the first three numbers?"
judge_score: 0.850 (approved)
```

### Comparison to Success Criteria

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Approval rate improvement | ≥70% | **100%** | ✅ Exceeded |
| vs baseline ~50% | +20pp | **+73.3pp** | ✅ Exceeded |
| Avg judge score | ≥0.85 | **0.92** | ✅ Met |
| Zero API errors | 0 | 0 | ✅ Met |

### Conclusion

The TASK-755 fix (stimulus field validation) has successfully resolved the memory question approval rate issue:

- **Improvement**: 73.3 percentage point increase (26.7% → 100%)
- **Relative improvement**: 3.75x better than baseline
- **Quality**: Average judge score improved from 0.71 to 0.92
- **Consistency**: 89 consecutive questions approved post-fix

Memory questions now perform at parity with other high-performing question types (LOGIC, PATTERN, MATH all at 99-100% approval rates).

## Appendix

### Example Memory Question Structure

**Before (current)**:
```json
{
  "question_text": "MEMORIZE THIS LIST: maple, oak, dolphin, cherry, whale, birch, salmon. Which item from the list is a mammal that is NOT the fourth item?",
  "correct_answer": "whale",
  "answer_options": ["dolphin", "whale", "salmon", "cherry", "oak"]
}
```

**After (new structure)**:
```json
{
  "stimulus": "maple, oak, dolphin, cherry, whale, birch, salmon",
  "question_text": "Which item from the list is a mammal that is NOT the fourth item?",
  "correct_answer": "whale",
  "answer_options": ["dolphin", "whale", "salmon", "cherry", "oak"]
}
```

### Prompt Update Preview

**Generator Prompt Addition** (for memory questions):
```
For memory questions, structure your response with TWO parts:
1. stimulus: The information to be memorized (list, sequence, or passage) - presented first
2. question_text: The actual question asking for recall - shown after stimulus is hidden

Example structure:
{
  "stimulus": "2, 7, 3, 9, 1, 8, 4",
  "question_text": "What was the fourth number in the sequence?",
  "correct_answer": "9",
  "answer_options": ["7", "9", "1", "8"],
  "explanation": "The fourth number in the sequence 2, 7, 3, 9, 1, 8, 4 is 9."
}
```

**Judge Prompt Addition**:
```
MEMORY QUESTIONS: For questions of type "memory", note that these have a two-phase delivery:
1. Stimulus (data to memorize) is shown first, then hidden
2. Question (what to recall) is shown afterward

When evaluating memory questions:
- Assume the app handles the two-phase delivery correctly
- Do NOT penalize for "stimulus being visible" - that's a UX concern
- Focus on whether the memory task itself is appropriate and well-designed
- Evaluate if the stimulus is clear and the question tests actual recall
```

### Related Documents

- [Architecture Overview](/Users/mattgioe/aiq/docs/architecture/OVERVIEW.md)
- [Question Service README](/Users/mattgioe/aiq/question-service/README.md)
- [Backend Deployment](/Users/mattgioe/aiq/backend/DEPLOYMENT.md)
