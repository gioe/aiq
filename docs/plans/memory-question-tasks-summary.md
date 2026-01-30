# Memory Question Two-Phase Model - Task Summary

This document provides a summary of the tasks created in the SQLite database for implementing the memory question two-phase model.

## Quick Stats

- **Total Tasks**: 36 tasks (including 1 documentation task in separate domain)
- **Estimated Duration**: 11-17 hours total across 6 phases
- **Task IDs**: 725-759

## Phase Breakdown

### Phase 1: Data Model & Database Foundation (7 tasks)
**Goal**: Establish stimulus field in core data structures and database
**Duration**: 2-4 hours

| Task ID | Summary | Domain | Priority |
|---------|---------|--------|----------|
| 725 | Add stimulus field to GeneratedQuestion model | question-service | high (90) |
| 726 | Update GeneratedQuestion.to_dict() for stimulus | question-service | high (85) |
| 727 | Add stimulus column to QuestionModel in database.py | question-service | high (90) |
| 728 | Update database insert methods to handle stimulus | question-service | high (85) |
| 729 | Create Alembic migration for stimulus column | backend | high (88) |
| 730 | Add stimulus field to backend Question model | backend | high (90) |
| 731 | Add stimulus field to QuestionResponse schema | backend | high (85) |

**Key Dependencies**:
- 726 depends on 725
- 728 depends on 727
- 731 depends on 730

### Phase 2: Question Generation & Evaluation (6 tasks)
**Goal**: Update generation prompts and judge to handle two-phase structure
**Duration**: 3-4 hours

| Task ID | Summary | Domain | Priority |
|---------|---------|--------|----------|
| 732 | Update memory question generation prompt | question-service | high (92) |
| 733 | Update JSON response format schema for stimulus | question-service | medium (70) |
| 734 | Update judge prompt for two-phase memory questions | question-service | high (90) |
| 735 | Update generator question parsing for stimulus | question-service | high (88) |
| 736 | Update regeneration prompt for stimulus | question-service | medium (65) |
| 737 | Increment PROMPT_VERSION to 2.1 | question-service | low (40) |

**Key Dependencies**:
- 733 depends on 732
- 735 depends on 732, 725
- 736 depends on 732
- 737 depends on 732, 734

### Phase 3: Testing & Validation (5 tasks)
**Goal**: Ensure changes work correctly without breaking existing functionality
**Duration**: 2-3 hours

| Task ID | Summary | Domain | Priority |
|---------|---------|--------|----------|
| 738 | Update unit tests for GeneratedQuestion with stimulus | question-service | medium (75) |
| 739 | Update database operation tests for stimulus | question-service | medium (75) |
| 740 | Update judge evaluation tests for memory questions | question-service | medium (78) |
| 741 | Generate test memory questions end-to-end | question-service | high (82) |
| 742 | Verify backward compatibility with no stimulus | question-service | high (85) |

**Key Dependencies**:
- 738 depends on 725
- 739 depends on 728
- 740 depends on 734
- 741 depends on 735, 728
- 742 depends on 728, 735

### Phase 4: Backend API Deployment (6 tasks)
**Goal**: Deploy database migration and expose stimulus field in API
**Duration**: 1-2 hours

| Task ID | Summary | Domain | Priority |
|---------|---------|--------|----------|
| 743 | Run Alembic migration on development database | backend | high (88) |
| 744 | Verify API returns stimulus in responses | backend | medium (75) |
| 745 | Update OpenAPI schema if needed | backend | medium (70) |
| 746 | Deploy backend to staging Railway environment | backend | high (85) |
| 747 | Run Alembic migration on production database | backend | high (90) |
| 748 | Deploy backend to production Railway | backend | high (88) |

**Key Dependencies**:
- 743 depends on 729
- 744 depends on 731, 743
- 745 depends on 731
- 746 depends on 729, 730, 731
- 747 depends on 746
- 748 depends on 747

### Phase 5: iOS Client Implementation (6 tasks)
**Goal**: Implement two-phase rendering in iOS app
**Duration**: 3-4 hours

| Task ID | Summary | Domain | Priority |
|---------|---------|--------|----------|
| 749 | Regenerate OpenAPI client for iOS with stimulus | ios | medium (75) |
| 750 | Create MemoryQuestionView component | ios | high (88) |
| 751 | Update QuestionCardView for memory questions | ios | high (85) |
| 752 | Add unit tests for MemoryQuestionView | ios | medium (70) |
| 753 | Update question mocks with stimulus field | ios | low (50) |
| 754 | Manual testing of memory question flow | ios | high (80) |

**Key Dependencies**:
- 749 depends on 745
- 750 depends on 749
- 751 depends on 750
- 752 depends on 750
- 753 depends on 749
- 754 depends on 751

### Phase 6: Validation & Monitoring (5 tasks + 1 documentation)
**Goal**: Confirm improved approval rates and monitor for issues
**Duration**: Ongoing (1 week observation)

| Task ID | Summary | Domain | Priority |
|---------|---------|--------|----------|
| 755 | Generate production batch of memory questions | question-service | high (85) |
| 756 | Monitor memory question approval rates | question-service | high (82) |
| 757 | Compare approval rates before/after | question-service | medium (75) |
| 758 | Collect user feedback on memory UX | ios | low (45) |
| 759 | Document findings and close project | documentation | low (40) |

**Key Dependencies**:
- 755 depends on 735, 748
- 756 depends on 755
- 757 depends on 756
- 758 depends on 754
- 759 depends on 757

## Task Execution Order

### Critical Path (Must be done sequentially)
1. **Phase 1 Foundation**: 725 → 726, 727 → 728, 729 → 730 → 731
2. **Phase 2 Prompts**: 732 → 733, 735, 736, 734 → 737
3. **Phase 3 Testing**: 738, 739, 740, 741, 742 (can run in parallel after dependencies)
4. **Phase 4 Deployment**: 743 → 744, 745 → 746 → 747 → 748
5. **Phase 5 iOS**: 749 → 750 → 751 → 754
6. **Phase 6 Monitoring**: 755 → 756 → 757, 759

### Parallelizable Tasks
Within each phase, many tasks can be done in parallel:

**Phase 1** (parallel after foundation):
- Group A: 725 → 726
- Group B: 727 → 728
- Group C: 729 → 730 → 731

**Phase 2** (parallel after prompt update):
- 732 enables: 733, 735, 736
- 734 is independent
- 737 depends on 732 + 734

**Phase 3** (all parallel once dependencies met):
- 738, 739, 740, 741, 742

**Phase 5** (parallel after client regen):
- Group A: 749 → 750 → 751, 752
- Group B: 749 → 753
- Then: 754

## Querying Tasks

### View all tasks for this project
```sql
SELECT id, summary, status, priority
FROM tasks
WHERE id BETWEEN 725 AND 759
ORDER BY id;
```

### View by phase
```sql
-- Phase 1
SELECT id, summary, status FROM tasks WHERE id BETWEEN 725 AND 731;

-- Phase 2
SELECT id, summary, status FROM tasks WHERE id BETWEEN 732 AND 737;

-- Phase 3
SELECT id, summary, status FROM tasks WHERE id BETWEEN 738 AND 742;

-- Phase 4
SELECT id, summary, status FROM tasks WHERE id BETWEEN 743 AND 748;

-- Phase 5
SELECT id, summary, status FROM tasks WHERE id BETWEEN 749 AND 754;

-- Phase 6
SELECT id, summary, status FROM tasks WHERE id BETWEEN 755 AND 759;
```

### View by domain
```sql
SELECT domain, COUNT(*) as task_count,
       SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
FROM tasks
WHERE id BETWEEN 725 AND 759
GROUP BY domain;
```

### View high priority tasks
```sql
SELECT id, summary, domain, priority_score
FROM tasks
WHERE id BETWEEN 725 AND 759
  AND priority = 'high'
ORDER BY priority_score DESC;
```

## Next Steps

1. **Start with Phase 1**: Tasks 725-731 establish the foundation
2. **Prioritize high-impact tasks**: Focus on tasks with priority_score >= 85
3. **Test incrementally**: Run Phase 3 tests after each phase completion
4. **Deploy carefully**: Phase 4 requires staging validation before production
5. **Monitor closely**: Phase 6 tracks success metrics and user impact

## Related Documents

- [Full Implementation Plan](/Users/mattgioe/aiq/docs/plans/memory-question-two-phase-model.md)
- [Tasks Database](/Users/mattgioe/aiq/tasks.db)
