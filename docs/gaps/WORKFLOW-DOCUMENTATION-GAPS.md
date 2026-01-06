# Workflow Documentation Gaps

**Source**: PR #484 Code Review Analysis (2026-01-06)
**Priority**: High
**Status**: Identified

## Problem Statement

During the review of PR #484 (BTS-45: Create FeedbackView), several documentation gaps were identified that could prevent future confusion and inconsistent practices:

1. **UI-First Development** is a valid pattern used in the codebase but is completely undocumented
2. **Backend-Frontend Coordination** has no clear workflow or decision tree
3. **iOS-specific PR checklist** items are missing from the PR template
4. **Code Review Severity Labels** (CRITICAL vs BLOCKER vs MEDIUM) are ambiguous

## Current State

### What Exists
- Comprehensive `ios/docs/CODING_STANDARDS.md` (1200+ lines) covering architecture, testing, accessibility
- PR template at `.github/PULL_REQUEST_TEMPLATE.md` with backend-focused checklists
- Code review patterns documented in `docs/code-review-patterns.md`

### What's Missing
- No guidance on when UI-first development is acceptable
- No process for coordinating backend/frontend work on shared features
- No iOS-specific items in PR template (property wrappers, design system compliance)
- No definition of review severity labels

## Impact

| Issue | Impact |
|-------|--------|
| UI-first development undocumented | PR reviews may incorrectly flag documented, intentional UI-only implementations as "CRITICAL" |
| No backend coordination workflow | Features may ship to production without backend integration |
| Missing iOS PR checklist | Common iOS issues (e.g., @StateObject anti-pattern) slip through reviews |
| Ambiguous severity labels | Inconsistent triaging of review feedback |

## Proposed Solutions

### 1. UI-First Development Pattern (Priority: HIGH)

**Location**: `ios/docs/CODING_STANDARDS.md` (new section after Architecture Patterns)

**Content to add**:
- When to use UI-first development (and when NOT to)
- Implementation pattern with code template
- Required process steps:
  - Document intent with `/// - Note:` comment
  - Link backend ticket in comment
  - Comment out intended API call with TODO
  - Create follow-up integration ticket
- Testing guidance for UI-first code

### 2. Backend Coordination Workflow (Priority: MEDIUM)

**Location**: `docs/workflow/BACKEND_COORDINATION.md` (new file)

**Content to add**:
- Decision tree: Backend-first vs UI-first vs Contract-first
- When to use each approach
- Jira ticket structure examples
- PR review guidelines for UI-first PRs
- Production-readiness checklist

### 3. iOS PR Checklist (Priority: HIGH)

**Location**: `.github/PULL_REQUEST_TEMPLATE.md`

**Items to add under new "iOS Changes Checklist" section**:
```markdown
### Architecture & Patterns
- [ ] ViewModels inherit from `BaseViewModel` and marked with `@MainActor`
- [ ] Property wrappers used correctly:
  - `@StateObject` only for view-owned objects (new instances)
  - `@ObservedObject` for singletons (`.shared`) or parent-provided objects
- [ ] Views follow MVVM (no business logic in views)

### Design System & Accessibility
- [ ] Uses `ColorPalette`, `Typography`, and `DesignSystem.Spacing`
- [ ] Interactive elements have accessibility labels and meet 44pt touch targets
- [ ] Dynamic Type tested at large sizes
- [ ] VoiceOver tested for key flows

### Backend Coordination (if applicable)
- [ ] Backend ticket created and linked (if UI-only implementation)
- [ ] Code documents UI-only status with `/// - Note:`
- [ ] Follow-up integration ticket created
```

### 4. Review Severity Guidelines (Priority: LOW)

**Location**: `docs/workflow/REVIEW_GUIDELINES.md` or append to `docs/code-review-patterns.md`

**Content to add**:
```markdown
## Review Severity Labels

| Label | Definition | Examples |
|-------|------------|----------|
| **CRITICAL** | Security, data loss, production user trust violations | XSS, SQL injection, secrets in code |
| **BLOCKER** | Must resolve before merge to production | Missing error handling, broken flows |
| **MEDIUM** | Should resolve with tracked follow-up | Missing tests, UI-only implementations |
| **LOW** | Nice-to-have improvements | Code style, minor UX enhancements |
```

## Implementation Plan

**Tracking Ticket**: [BTS-213](https://gioematt.atlassian.net/browse/BTS-213)

| Task | Priority | Effort |
|------|----------|--------|
| Add UI-First Development section to CODING_STANDARDS.md | HIGH | 1 hour |
| Add iOS Changes Checklist to PR template | HIGH | 30 min |
| Create BACKEND_COORDINATION.md workflow doc | MEDIUM | 2 hours |
| Add Review Severity Guidelines | LOW | 30 min |

## Related

- **PR #484**: https://github.com/gioe/aiq/pull/484 (source of this analysis)
- **BTS-45**: Create FeedbackView (the PR that triggered this analysis)
- **BTS-209**: Backend endpoint for feedback (created from deferred items)
- **Existing Docs**:
  - `ios/docs/CODING_STANDARDS.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `docs/code-review-patterns.md`

## Notes

This gap was identified when Claude's PR review labeled a documented UI-first implementation as "CRITICAL: Missing Backend Integration". The code was properly documented with `/// - Note: This is a UI-only implementation since the backend endpoint doesn't exist yet`, but the review process had no guidance on how to handle this legitimate development pattern.

The key insight: **UI-first development is valid**, but without documentation, reviewers may incorrectly flag it as a defect rather than a tracked, intentional approach.
