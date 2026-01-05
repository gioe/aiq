# Timer Closures Retain Cycle Audit

**Issue:** BTS-57
**Ticket:** ICG-091
**Date:** 2026-01-05
**Status:** Audit Complete - No Issues Found

## Executive Summary

A comprehensive audit of `Timer` usage across the iOS codebase found **2 Timer instances** in production code. Both instances already correctly use `[weak self]` capture lists to prevent retain cycles.

**Finding:** No retain cycle risks identified. The codebase follows best practices for Timer closure memory management.

**Priority Fixes for ICG-092:** None required - all Timer usage is safe.

---

## Background

### Why Timer Closures Can Cause Retain Cycles

Timer closures can cause retain cycles because:

1. **Timer holds a strong reference** to its closure
2. **RunLoop holds a strong reference** to the Timer
3. If the closure captures `self` strongly, a cycle forms:
   ```
   self → timer (stored property) → closure → self
   ```

This prevents `deinit` from ever being called, causing memory leaks.

### The Pattern to Avoid

```swift
// ❌ WRONG - Creates retain cycle
class MyViewModel {
    var timer: Timer?

    func startTimer() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            self.tick()  // Strong capture of self
        }
    }
}
```

### The Correct Pattern

```swift
// ✅ CORRECT - No retain cycle
class MyViewModel {
    var timer: Timer?

    func startTimer() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.tick()  // Weak capture prevents cycle
        }
    }

    deinit {
        timer?.invalidate()
    }
}
```

---

## Audit Findings

### Timer Instances Found

| # | File | Line | Risk Level | Status |
|---|------|------|------------|--------|
| 1 | `AIQ/Services/Analytics/AnalyticsService.swift` | 461 | None | Safe |
| 2 | `AIQ/ViewModels/TestTimerManager.swift` | 133 | None | Safe |

### Detailed Analysis

#### 1. AnalyticsService.swift (Line 461)

**Code:**
```swift
private func startBatchTimer() {
    DispatchQueue.main.async { [weak self] in
        guard let self else { return }
        batchTimer = Timer.scheduledTimer(
            withTimeInterval: batchInterval,
            repeats: true
        ) { [weak self] _ in       // ✅ [weak self]
            Task { [weak self] in  // ✅ [weak self] again in nested Task
                await self?.submitBatch()
            }
        }
    }
}
```

**Assessment:** **SAFE**
- Uses `[weak self]` in Timer closure
- Uses `[weak self]` in nested Task for double safety
- Timer is invalidated in `deinit`:
  ```swift
  deinit {
      batchTimer?.invalidate()
  }
  ```

#### 2. TestTimerManager.swift (Line 133)

**Code:**
```swift
func start() {
    guard timer == nil else { return } // Already running

    currentSegmentStartTime = Date()

    timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
        Task { @MainActor in
            self?.tick()  // ✅ Uses weak self from capture list
        }
    }

    if let timer {
        RunLoop.main.add(timer, forMode: .common)
    }
}
```

**Assessment:** **SAFE**
- Uses `[weak self]` in Timer closure
- Timer is invalidated in `deinit`:
  ```swift
  deinit {
      NotificationCenter.default.removeObserver(self)
      timer?.invalidate()
  }
  ```

---

## Related Patterns Audited

### DispatchQueue.asyncAfter Usage

Also checked `DispatchQueue.main.asyncAfter` calls which can have similar risks:

| File | Line | Pattern | Status |
|------|------|---------|--------|
| `TestTakingViewModel.swift` | 628 | `execute: workItem` | Safe - uses DispatchWorkItem with `[weak self]` in closure |
| `AnswerInputView.swift` | 79 | UI state modification | Safe - SwiftUI View, no self reference needed |
| `TimeWarningBanner.swift` | 36 | Callback invocation | Safe - calls external closure, no self reference |

**Note:** The `TestTakingViewModel.swift` auto-save pattern correctly uses a `DispatchWorkItem` that captures `[weak self]`:

```swift
let workItem = DispatchWorkItem { [weak self] in
    self?.saveProgress()
}
```

---

## Priority Fixes for ICG-092

**None required.**

All Timer usage in the codebase follows the correct pattern with `[weak self]` capture lists. No retain cycle risks were identified.

---

## Recommendations

### Preventive Measures

1. **SwiftLint Rule**: Consider adding a custom SwiftLint rule to detect Timer closures without `[weak self]` (similar to the existing `handleError` rule from BTS-56).

2. **Code Review Checklist**: Add Timer closure patterns to the iOS code review checklist:
   - [ ] Timer closures use `[weak self]`
   - [ ] Timer is invalidated in `deinit`
   - [ ] Nested async closures (Task, DispatchQueue) also capture `[weak self]`

3. **Documentation**: Add Timer best practices to `CODING_STANDARDS.md` if not already present.

### Suggested SwiftLint Rule (Future Enhancement)

```yaml
# Custom rule idea for future implementation
custom_rules:
  timer_weak_self:
    name: "Timer Weak Self"
    regex: 'Timer\.scheduledTimer[^}]*\{[^}]*(?<!\[weak self\])[^}]*self\.'
    message: "Timer closures should capture [weak self] to prevent retain cycles"
    severity: warning
```

---

## Test Coverage

Timer behavior is tested in:
- `AIQTests/ViewModels/TestTimerManagerTests.swift` - Comprehensive tests for timer lifecycle
- `AIQTests/Services/AnalyticsServiceTests.swift` - Tests with `startTimer: false` to isolate timer behavior

---

## Conclusion

The iOS codebase demonstrates excellent memory management practices for Timer usage. Both production Timer instances correctly implement `[weak self]` capture lists and proper `deinit` cleanup.

No code changes are required as a result of this audit. The audit serves as documentation that Timer memory management has been verified as of this date.
