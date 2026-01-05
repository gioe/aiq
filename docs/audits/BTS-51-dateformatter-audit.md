# DateFormatter Usage Audit - BTS-51

**Date:** 2026-01-05
**Auditor:** Claude (Opus 4.5)
**Objective:** Document all DateFormatter usage across the iOS codebase to prepare for consolidation (ICG-086)

---

## Executive Summary

**Total DateFormatter Instances (Production Code):** 9
**Unique Locations:** 6 files
**Format Categories:** 5
**Test Code Instances:** 13 (in 1 file)

### Key Findings

The AIQ iOS app creates `DateFormatter` instances **inline at call sites** throughout the codebase. This is a **performance concern** because:

1. **DateFormatter is expensive** - Creating a DateFormatter is one of the most expensive operations in Foundation
2. **No caching** - Each formatting operation creates a new instance
3. **Duplicate patterns** - The same format (e.g., `.medium` date style) is created in multiple locations
4. **Good: Date+Extensions exists** - There's already a central extension file that could house shared formatters

**Recommendation:** Consolidate all DateFormatter usage into cached, static formatters in `Date+Extensions.swift`.

---

## Detailed Findings by Category

### Category 1: Medium Date Style (Date Only)

**Format:** `dateStyle = .medium, timeStyle = .none`
**Output Example:** "Jan 15, 2024"
**Usage Count:** 4

| File | Line | Function/Context | Current Implementation |
|------|------|------------------|------------------------|
| `Date+Extensions.swift` | 8-13 | `toShortString(locale:)` | Creates new formatter per call |
| `DashboardViewModel.swift` | 241-244 | `latestTestDateFormatted` | Creates new formatter per call |
| `IQTrendChart.swift` | 170-172 | `generateAccessibilityLabel()` | Creates new formatter per call |
| `CODING_STANDARDS.md` | 425-428 | Documentation example | N/A (documentation) |

**Notes:**
- `DashboardViewModel` duplicates the exact same formatting logic as `Date.toShortString()`
- `IQTrendChart` could use `Date.toShortString()` instead of creating its own formatter

---

### Category 2: Long Date + Short Time

**Format:** `dateStyle = .long, timeStyle = .short`
**Output Example:** "January 15, 2024 at 3:45 PM"
**Usage Count:** 2

| File | Line | Function/Context | Current Implementation |
|------|------|------------------|------------------------|
| `Date+Extensions.swift` | 19-23 | `toLongString(locale:)` | Creates new formatter per call |
| `TestDetailView+Helpers.swift` | 141-144 | `formatFullDate(_:)` | Creates new formatter per call |

**Notes:**
- `TestDetailView+Helpers.formatFullDate()` duplicates `Date.toLongString()`
- Should use the extension method instead

---

### Category 3: Short Date + Short Time

**Format:** `dateStyle = .short, timeStyle = .short`
**Output Example:** "1/15/24, 3:45 PM"
**Usage Count:** 1

| File | Line | Function/Context | Current Implementation |
|------|------|------------------|------------------------|
| `TestResultsView.swift` | 367-370 | `formatDate(_:)` | Creates new formatter per call |

**Notes:**
- This format is unique - no extension method exists for it
- Consider adding `Date.toCompactString()` to extensions

---

### Category 4: Relative Date/Time

**Format:** `RelativeDateTimeFormatter` with `unitsStyle = .full`
**Output Example:** "2 days ago", "in 3 hours"
**Usage Count:** 2

| File | Line | Function/Context | Current Implementation |
|------|------|------------------|------------------------|
| `Date+Extensions.swift` | 30-33 | `toRelativeString(locale:)` | Creates new formatter per call |
| `PerformanceInsights.swift` | 178-181 | `identifyBestPeriod(from:)` | Creates new formatter per call |

**Notes:**
- `PerformanceInsights` duplicates `Date.toRelativeString()`
- Should use the extension method instead

---

### Category 5: ISO8601 (API Communication)

**Format:** `ISO8601DateFormatter`
**Output Example:** "2024-01-15T15:45:30Z"
**Usage Count (Production):** 1
**Usage Count (Tests):** 13

| File | Line | Function/Context | Current Implementation |
|------|------|------------------|------------------------|
| `Date+Extensions.swift` | 40-41 | `toAPIString()` | Creates new formatter per call |
| `APIClientIntegrationTests.swift` | 194, 195, 429, 430, 456, 457, 501, 532, 533, 546, 616, 628, 661 | Test data generation | Creates new formatter per use |

**Notes:**
- Production code has a single location (good!)
- Test code creates many inline formatters (acceptable for tests, but could be improved)

---

## Files Summary

### Production Code Files

| File | Path | Formatter Count | Categories |
|------|------|-----------------|------------|
| `Date+Extensions.swift` | `ios/AIQ/Utilities/Extensions/` | 4 | Medium, Long+Time, Relative, ISO8601 |
| `DashboardViewModel.swift` | `ios/AIQ/ViewModels/` | 1 | Medium |
| `IQTrendChart.swift` | `ios/AIQ/Views/History/` | 1 | Medium |
| `TestDetailView+Helpers.swift` | `ios/AIQ/Views/History/` | 1 | Long+Time |
| `TestResultsView.swift` | `ios/AIQ/Views/Test/` | 1 | Short+Time |
| `PerformanceInsights.swift` | `ios/AIQ/Models/` | 1 | Relative |

### Test Code Files

| File | Path | Formatter Count | Categories |
|------|------|-----------------|------------|
| `APIClientIntegrationTests.swift` | `ios/AIQTests/Integration/` | 13 | ISO8601 |

### Documentation Files (Not Code)

| File | Path | Notes |
|------|------|-------|
| `CODING_STANDARDS.md` | `ios/docs/` | Contains DateFormatter examples in documentation - not actual code |

---

## Redundancy Analysis

### Exact Duplicates

| Extension Method | Duplicate Location | Can Replace? |
|------------------|-------------------|--------------|
| `Date.toShortString()` | `DashboardViewModel.latestTestDateFormatted` | ✅ Yes |
| `Date.toShortString()` | `IQTrendChart.generateAccessibilityLabel()` | ✅ Yes |
| `Date.toLongString()` | `TestDetailView+Helpers.formatFullDate()` | ✅ Yes |
| `Date.toRelativeString()` | `PerformanceInsights.identifyBestPeriod()` | ✅ Yes |

### Missing Extension Methods

| Format | Current Usage | Suggested Extension |
|--------|--------------|---------------------|
| Short date + short time | `TestResultsView.formatDate()` | `Date.toCompactString()` |

---

## Migration Plan for ICG-086

### Phase 1: Create Cached Formatters (High Impact)

Replace inline formatter creation with cached static formatters in `Date+Extensions.swift`:

```swift
extension Date {
    // MARK: - Cached Formatters (Performance Optimization)

    private static let mediumDateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter
    }()

    private static let longDateShortTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .long
        formatter.timeStyle = .short
        return formatter
    }()

    private static let shortDateShortTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter
    }()

    private static let relativeFormatter: RelativeDateTimeFormatter = {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full
        return formatter
    }()

    private static let iso8601Formatter: ISO8601DateFormatter = {
        ISO8601DateFormatter()
    }()
}
```

**Considerations:**
- Static formatters are NOT thread-safe for mutation but ARE thread-safe for read-only use
- The above patterns use only read-only operations after initialization
- For locale-specific formatting, consider using `formatted()` API on iOS 15+ instead

### Phase 2: Update Extension Methods

Modify existing extension methods to use cached formatters:

```swift
func toShortString(locale: Locale = .current) -> String {
    // If custom locale, create new formatter (rare case)
    if locale != .current {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        formatter.locale = locale
        return formatter.string(from: self)
    }
    // Use cached formatter for default locale (common case)
    return Self.mediumDateFormatter.string(from: self)
}
```

### Phase 3: Replace Duplicate Code

| File | Change Required |
|------|-----------------|
| `DashboardViewModel.swift` | Replace inline formatter with `latest.completedAt.toShortString()` |
| `IQTrendChart.swift` | Replace inline formatter with `date.toShortString()` |
| `TestDetailView+Helpers.swift` | Replace `formatFullDate()` with `date.toLongString()` |
| `PerformanceInsights.swift` | Replace inline formatter with `bestTest.completedAt.toRelativeString()` |
| `TestResultsView.swift` | Add new `toCompactString()` extension and use it |

### Phase 4: Add New Extension Method

Add missing format to `Date+Extensions.swift`:

```swift
/// Format date as compact string (e.g., "1/15/24, 3:45 PM")
func toCompactString() -> String {
    Self.shortDateShortTimeFormatter.string(from: self)
}
```

### Phase 5: Update Tests (Optional)

Consider creating a test helper for ISO8601 formatting:

```swift
// In test support file
extension Date {
    static let testISO8601Formatter = ISO8601DateFormatter()

    var testAPIString: String {
        Self.testISO8601Formatter.string(from: self)
    }
}
```

---

## Task Breakdown for ICG-086

1. **Create cached static formatters** in `Date+Extensions.swift`
2. **Add `toCompactString()` extension** for short date/time format
3. **Update `DashboardViewModel`** to use `toShortString()`
4. **Update `IQTrendChart`** to use `toShortString()`
5. **Update `TestDetailView+Helpers`** to use `toLongString()`
6. **Update `PerformanceInsights`** to use `toRelativeString()`
7. **Update `TestResultsView`** to use new `toCompactString()`
8. **Update tests** with shared formatter (optional)
9. **Update `CODING_STANDARDS.md`** with cached formatter pattern guidance
10. **Run all tests** to verify no regressions

---

## Appendix: Code Snippets

### Current State - DashboardViewModel.swift (Line 238-245)

```swift
/// Formatted latest test date
var latestTestDateFormatted: String? {
    guard let latest = latestTestResult else { return nil }
    let formatter = DateFormatter()
    formatter.dateStyle = .medium
    formatter.timeStyle = .none
    return formatter.string(from: latest.completedAt)
}
```

### After Migration

```swift
/// Formatted latest test date
var latestTestDateFormatted: String? {
    latestTestResult?.completedAt.toShortString()
}
```

---

## References

- [Apple: DateFormatter Performance](https://developer.apple.com/documentation/foundation/dateformatter)
- [WWDC: Formatters Make Data Human-Friendly](https://developer.apple.com/videos/play/wwdc2020/10160/)
- Related Jira: ICG-086 (Consolidate DateFormatter Implementations)
