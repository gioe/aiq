# handleError Weak Self Audit

**Audit Date:** January 8, 2026
**Ticket:** BTS-208
**Auditor:** Claude Code

## Summary

This audit reviewed all `handleError` usages across iOS ViewModels to identify potential retain cycles caused by missing `[weak self]` in retry closures.

**Result: All handleError usages with retry closures correctly use `[weak self]`. No fixes required.**

## Background

The `handleError()` method in `BaseViewModel` stores a retry closure in `lastFailedOperation`. If `self` is captured strongly in this closure, it creates a retain cycle:

```
ViewModel → BaseViewModel.lastFailedOperation → closure → ViewModel
   (strong)            (strong)                 (strong capture)
```

This prevents the ViewModel from being deallocated, causing memory leaks.

## Audit Findings

### ViewModels Audited

| ViewModel | File Location |
|-----------|---------------|
| DashboardViewModel | `AIQ/ViewModels/DashboardViewModel.swift` |
| FeedbackViewModel | `AIQ/ViewModels/FeedbackViewModel.swift` |
| HistoryViewModel | `AIQ/ViewModels/HistoryViewModel.swift` |
| NotificationSettingsViewModel | `AIQ/ViewModels/NotificationSettingsViewModel.swift` |
| TestTakingViewModel | `AIQ/ViewModels/TestTakingViewModel.swift` |
| BaseViewModel | `AIQ/ViewModels/BaseViewModel.swift` |

### handleError Usage Details

| File | Line | Has Retry Closure | Uses `[weak self]` | Status |
|------|------|-------------------|-------------------|--------|
| DashboardViewModel.swift | 106 | Yes | Yes | OK |
| FeedbackViewModel.swift | 107 | Yes | Yes | OK |
| HistoryViewModel.swift | 102 | Yes | Yes | OK |
| HistoryViewModel.swift | 203 | Yes | Yes | OK |
| NotificationSettingsViewModel.swift | 63 | Yes | Yes | OK |
| NotificationSettingsViewModel.swift | 92 | Yes | Yes | OK |
| TestTakingViewModel.swift | 216 | Yes | Yes | OK |
| TestTakingViewModel.swift | 232 | Yes | Yes | OK |
| TestTakingViewModel.swift | 330 | No | N/A | OK |
| TestTakingViewModel.swift | 339 | No | N/A | OK |
| TestTakingViewModel.swift | 383 | No | N/A | OK |
| TestTakingViewModel.swift | 423 | No | N/A | OK |
| TestTakingViewModel.swift | 438 | No | N/A | OK |
| TestTakingViewModel.swift | 467 | No | N/A | OK |
| TestTakingViewModel.swift | 530 | Yes | Yes | OK |
| TestTakingViewModel.swift | 586 | Yes | Yes | OK |

### Notes

1. **DashboardViewModel.abandonActiveTest()** - Previously identified as having a retain cycle (PR #476). Now fixed with `[weak self]`.

2. **NotificationSettingsViewModel** - Lines 63-65 and 92-94 were tracked in BTS-207 as having similar issues. Current code shows they already use `[weak self]`, indicating BTS-207 may have been resolved or was preemptively fixed.

3. **handleError calls without retry closures** - Several calls in TestTakingViewModel pass no retry closure (e.g., for non-retryable errors like "no questions available"). These don't create retain cycles since there's no closure to capture `self`.

## Documentation Status

The `[weak self]` requirement for `handleError` retry closures is already documented in:
- `ios/docs/CODING_STANDARDS.md` (lines 504-524, "Memory Management in Error Handlers")

The documentation includes:
- Critical warning about using `[weak self]`
- Code examples showing wrong vs correct patterns
- Explanation of the retain cycle mechanism
- Why optional chaining (`self?`) is necessary

## SwiftLint Enforcement

A custom SwiftLint rule exists in `.swiftlint.yml` (lines 65-66) to detect this anti-pattern:

```yaml
regex: 'handleError\([^}]+\{\s*\n\s*await self\.'
message: "handleError retry closure must use [weak self] to avoid retain cycles. See CODING_STANDARDS.md 'Memory Management in Error Handlers'"
```

This rule will warn developers if they write `handleError` closures that directly reference `self` without weak capture.

## Recommendations

1. **No immediate fixes required** - All current usages are correct.

2. **Close BTS-207** - If not already closed, BTS-207 (NotificationSettingsViewModel retain cycles) can be closed as the code already uses `[weak self]`.

3. **Maintain vigilance** - The SwiftLint rule and code review processes should continue to catch any future violations.

## Related Tickets

- **BTS-208** (this audit)
- **BTS-207** - Fix Retain Cycles in NotificationSettingsViewModel (appears resolved)
- **BTS-57** - [ICG-091] Audit Timer Closures for Retain Cycles (separate audit)
- **PR #476** - [BTS-56] Fix retain cycle in DashboardViewModel (merged)
