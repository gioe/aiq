# PR #534 Coding Standards Update Recommendations

**Date**: 2026-01-13
**Status**: Pending Approval
**Impact**: 2 new sections in CODING_STANDARDS.md, 3 tracking tickets

---

## Quick Decision

**Should we update our coding standards based on PR #534 review feedback?**

**YES.** The review revealed two significant gaps:

1. **Background task patterns** - No guidance on race conditions, UserDefaults sync, or time budgets
2. **Test helper anti-patterns** - No guidance on when helpers duplicate business logic

---

## What Needs to Change

### 1. Add "Background Task Execution Patterns" Section

**Location**: Under "Concurrency" in CODING_STANDARDS.md
**Reason**: BGTaskScheduler has race conditions not covered by existing @MainActor guidance

**Key Patterns to Document**:
- ✅ Task completion race condition protection (use completion flag)
- ✅ UserDefaults.synchronize() requirement in background contexts
- ✅ Time budget management (30-second limit, target 15-20s)
- ✅ Battery optimization (fast-fail checks, minimal network)

**Impact**: Prevents race conditions and data loss in future background tasks

---

### 2. Add "Test Helper Anti-Patterns" Section

**Location**: Under "Testing" in CODING_STANDARDS.md
**Reason**: Test helpers that duplicate business logic give false confidence

**Key Anti-Pattern**:
```swift
// ❌ BAD - Helper encodes business rule
private func createOldTest() -> TestResult {
    // Assumes 90-day cadence (duplicates production logic)
    let date = Calendar.current.date(byAdding: .day, value: -91, to: Date())!
    return TestResult(completedAt: date, ...)
}

// ✅ GOOD - Explicit boundary testing
func testAvailability_ExactlyAt90Days() async throws {
    let exactly90DaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
    let test = TestResult(completedAt: exactly90DaysAgo, ...)
    XCTAssertTrue(try await sut.isAvailable(lastTest: test))
}
```

**Impact**: Improves test quality by making business rules explicit

---

### 3. Create Tracking Tickets (Deferred Work)

| Ticket | Title | Priority | Description |
|--------|-------|----------|-------------|
| BTS-281 | Refactor test helpers duplicating logic | Medium | Update BackgroundRefreshManagerTests to use explicit boundary testing |
| BTS-282 | Add defensive date calculation checks | Low | Add guards for negative day values (clock skew) |
| BTS-283 | Document manual testing procedures | Low | Add background task testing guide to docs |

---

## What We're NOT Changing (And Why)

### Badge Management - Document Pattern, Don't Build Yet

**Current Approach**: Defer badge setting to centralized management (future work)
```swift
// Note: Badge management should be handled centrally when app becomes active
content.userInfo = ["type": "test_reminder"]
```

**Rationale**:
- Only one notification source currently (background refresh)
- Don't over-engineer until we have 2-3 badge sources
- Document the pattern, create infrastructure later

**Action**: Add guidance to CODING_STANDARDS.md, no implementation needed

---

### Date Edge Cases - Defensive Checks, Not Framework

**Current Approach**: Add simple guards for edge cases
```swift
guard daysSinceLastTest >= 0 else {
    logger.warning("Last test date is in future (clock skew?)")
    return false
}
```

**Rationale**:
- Edge cases (clock skew, DST, timezone) are rare
- Simple defensive checks are sufficient
- Don't create complex date testing framework

**Action**: Document pattern in CODING_STANDARDS.md, add checks in BTS-282

---

## Review Questions Answered

### Do we agree with all review feedback?

**YES.** All six issues identified are valid:
1. Race condition in task completion → **Critical fix required**
2. UserDefaults synchronization → **Prevents data loss**
3. Badge hardcoded → **Coordination needed**
4. Test helpers duplicate logic → **Reduces test value**
5. Date edge cases → **Defensive checks needed**
6. Manual testing docs missing → **Aids future developers**

### What process improvements prevent future issues?

**Documentation** (this proposal):
- Background task patterns section
- Test helper anti-patterns section

**Code Review Checklists**:
- Flag UserDefaults usage in background contexts
- Flag test helpers that encode business logic
- Verify badge management approach

**CI/Automation**:
- SwiftLint could detect `content.badge =` (custom rule)
- CI could require manual testing docs for certain file changes

---

## Implementation Plan

### Phase 1: Update CODING_STANDARDS.md (2-3 hours)

**Add Section 1: Background Task Execution Patterns**
- Location: Under "Concurrency" (after "Main Actor Synchronization")
- Content:
  - Task completion race condition pattern (with code example)
  - UserDefaults.synchronize() requirement
  - Time budget management (30s limit)
  - Battery optimization strategies

**Add Section 2: Test Helper Anti-Patterns**
- Location: Under "Testing" (after "Test Coverage Completeness")
- Content:
  - When helpers duplicate business logic (anti-pattern)
  - Boundary testing best practices
  - When helpers are appropriate (boilerplate, shared data)

**Add Section 3: Badge Management Patterns**
- Location: Under "State Management" (new subsection)
- Content:
  - Badge as application-level state
  - Defer to centralized management pattern
  - Document future BadgeManager approach

**Add Section 4: Date and Time Calculations**
- Location: Under "Error Handling" (new subsection)
- Content:
  - Common pitfalls (clock skew, timezone, DST)
  - Defensive calculation pattern
  - Example: guard against negative day values

**Add Section 5: Manual Testing Requirements**
- Location: Under "Testing" (new subsection)
- Content:
  - When manual testing is required
  - Background task testing procedure (LLDB commands)
  - Monitoring with Instruments and Console.app

### Phase 2: Create Tracking Tickets (30 minutes)

- [ ] BTS-281: Refactor BackgroundRefreshManagerTests (remove `createTestResult(daysAgo:)` helper)
- [ ] BTS-282: Add defensive date calculation checks (guard negative values)
- [ ] BTS-283: Add manual testing docs (background task testing guide)

### Phase 3: Review Existing Code (Optional, 2-3 hours)

- [ ] Audit other notification code for badge management patterns
- [ ] Audit date calculations for defensive checks
- [ ] Audit other test helpers for logic duplication

---

## Success Metrics

**These standards updates are successful if**:
1. Future background task PRs don't have race condition issues
2. Test helpers are reviewed for logic duplication
3. Badge management approach is consistent across notification types
4. Date edge cases are defended against with simple guards
5. Manual testing procedures are documented and followed

---

## Decision Required

**Approve updating CODING_STANDARDS.md with background task patterns and test helper anti-patterns?**

- ✅ **Yes** - Prevents future issues, codifies lessons learned, improves code quality
- ❌ **No** - Risk repeating same issues in future PRs, no documented patterns

**If approved**:
1. I'll update CODING_STANDARDS.md with the five new sections
2. Create tickets BTS-281, BTS-282, BTS-283
3. Reference these patterns in future code reviews

**Estimated effort**: 3-4 hours (documentation updates + ticket creation)

---

## Appendix: Files to Review

- **Full Analysis**: `/docs/analysis/pr-534-standards-gap-analysis.md`
- **PR Review**: https://github.com/gioe/aiq/pull/534
- **Current Standards**: `/ios/docs/CODING_STANDARDS.md`
- **Implementation**: `/ios/AIQ/Services/Background/BackgroundRefreshManager.swift`
