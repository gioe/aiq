# BTS-61: Magic Numbers Codebase Audit

## Overview

This document provides a comprehensive audit of magic numbers in the iOS codebase, categorized by priority for extraction to `Constants.swift`. The audit was conducted to identify hardcoded numeric values that should be centralized for maintainability.

## Already Extracted

The following constants have already been extracted to `Constants.swift`:

| Constant | Value | Location |
|----------|-------|----------|
| `Timing.criticalThresholdSeconds` | 60 | Timer warning threshold |
| `Timing.autoSaveDelay` | 1.0 | Test progress auto-save delay |
| `Network.slowRequestThreshold` | 2.0 | Slow request logging threshold |
| `Test.progressValidityDuration` | 86400 (24h) | Saved progress validity |

## Already Abstracted in DesignSystem.swift

The following UI values are already centralized in `DesignSystem.swift`:

- **Spacing**: xs(4), sm(8), md(12), lg(16), xl(20), xxl(24), xxxl(32), huge(40), section(60)
- **Corner Radius**: sm(8), md(12), lg(16), xl(20), full(9999)
- **Shadows**: subtle, card, elevated
- **Animations**: quick, standard, smooth, bouncy
- **Icon Sizes**: sm(16), md(24), lg(32), xl(48), huge(64)

---

## HIGH PRIORITY - Extract to Constants.swift

These are critical business logic values that affect application behavior.

### 1. Timer Configuration (TestTimerManager.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `1800` | Line 11, 22 | `Timing.totalTestTimeSeconds` |
| `300` | Line 25 | `Timing.warningThresholdSeconds` |
| `0.25` | Line 133 | `Timing.timerUpdateInterval` |

**Current Code:**
```swift
// TestTimerManager.swift:11
@Published private(set) var remainingSeconds: Int = 1800

// TestTimerManager.swift:22
static let totalTimeSeconds: Int = 1800

// TestTimerManager.swift:25
static let warningThresholdSeconds: Int = 300

// TestTimerManager.swift:133
timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true)
```

**Rationale:** These define the 30-minute test limit and 5-minute warning - core product behavior.

---

### 2. Analytics Service Configuration (AnalyticsService.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `50` | Line 158 | `Analytics.maxBatchSize` |
| `500` | Line 161 | `Analytics.maxQueueSize` |
| `3` | Line 167 | `Analytics.maxRetries` |
| `30.0` | Line 194, 205 | `Analytics.batchInterval` |
| `30` | Line 579 | `Analytics.requestTimeout` |

**Rationale:** Analytics batching parameters affect data collection reliability and network usage.

---

### 3. API Client Configuration (APIClient.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `30.0` | Line 195 | `Network.requestTimeout` |
| `1` | Line 162 | `Network.maxTokenRefreshRetries` |

**Rationale:** Network timeout and retry behavior directly impacts user experience.

---

### 4. Retry Policy (RetryPolicy.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `3` | Line 12 | `Network.defaultMaxRetryAttempts` |
| `[408, 429, 500, 502, 503, 504]` | Line 13 | `Network.retryableStatusCodes` |

**Rationale:** Retry behavior affects reliability and should be consistently configurable.

---

### 5. Test Configuration (TestTakingViewModel.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `20` | Line 150, 348 | `Test.defaultQuestionCount` |

**Current Code:**
```swift
func startTest(questionCount: Int = 20) async {
func abandonAndStartNew(sessionId: Int, questionCount: Int = 20) async {
```

**Rationale:** Default question count is a core product parameter that may change.

---

### 6. History/Pagination (HistoryViewModel.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `50` | Line 70 | `Pagination.historyPageSize` |

**Rationale:** Page size affects API load and user experience.

---

### 7. Dashboard Cache (DashboardViewModel.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `120` | Line 154 | `Cache.dashboardCacheDuration` |

**Current Code:**
```swift
cacheDuration: 120, // 2 minutes
```

**Rationale:** Cache duration affects data freshness and API calls.

---

### 8. Data Cache (DataCache.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `300` | Line 24 | `Cache.defaultExpiration` |

**Rationale:** Default cache expiration is already documented but should be in Constants.

---

### 9. Validation Rules (Validators.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `8` | Line 55-56 | `Validation.minPasswordLength` |
| `2` | Line 77-78 | `Validation.minNameLength` |

**Rationale:** Validation rules are user-facing and may need adjustment.

---

### 10. Onboarding (OnboardingViewModel.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `4` | Line 18 | `Onboarding.totalPages` |

**Rationale:** Onboarding page count should be configurable if pages are added/removed.

---

### 11. Certificate Pinning (AppDelegate.swift)

| Value | Current Location | Recommended Constant |
|-------|-----------------|----------------------|
| `2` | Line 33, 43-44 | `Security.minRequiredPins` |

**Rationale:** Security configuration should be explicitly documented.

---

## MEDIUM PRIORITY - Consider for Future Extraction

These are UI-related values that could benefit from centralization but have lower impact.

### Animation Delays

| Value | Files Using |
|-------|------------|
| `0.1` | DomainScoresView, TestResultsView, TestDetailView |
| `0.2` | Multiple onboarding pages, WelcomeView, RegistrationView |
| `0.4` | Multiple onboarding pages, WelcomeView, RegistrationView |
| `0.6` | PrivacyConsentView, WelcomeView, RegistrationView |
| `0.8` | WelcomeView, RegistrationView |

**Recommendation:** Add to `DesignSystem.Animation`:
```swift
enum AnimationDelay {
    static let stagger1: Double = 0.1
    static let stagger2: Double = 0.2
    static let stagger3: Double = 0.4
    static let stagger4: Double = 0.6
    static let stagger5: Double = 0.8
}
```

---

### Font Sizes

| Value | Usage Count | Context |
|-------|-------------|---------|
| `8` | 3 | Small labels, legends |
| `10` | 3 | Domain score labels |
| `12` | 3 | Small text |
| `14` | 4 | Secondary text |
| `16` | 8 | Body text, buttons |
| `20` | 5 | Medium headings |
| `24` | 4 | Section headings |
| `32` | 4 | Large numbers |
| `48` | 3 | Icons |
| `50` | 2 | Score displays |
| `72` | 3 | Large score displays |
| `80` | 8 | Hero icons/emojis |
| `100` | 1 | Splash screen |

**Recommendation:** Many of these follow the existing `Typography` patterns. Consider adding:
```swift
enum FontSize {
    static let heroIcon: CGFloat = 80
    static let scoreDisplay: CGFloat = 72
    static let largeNumber: CGFloat = 50
}
```

---

### Common Frame Sizes

| Value | Usage | Context |
|-------|-------|---------|
| `44` | 15+ | Minimum tap target (Apple HIG) |
| `48` | 4 | Icon containers |
| `56` | 2 | Card icon backgrounds |

**Note:** `44` is Apple's Human Interface Guidelines minimum tap target - this is intentional and should remain explicit for accessibility compliance.

---

## LOW PRIORITY - Keep As-Is

These are well-documented domain constants or standard values that don't need extraction.

### IQ Score Ranges (Standard Classification)

```swift
case 0 ..< 70:    // Significantly Below Average
case 70 ..< 85:   // Below Average
case 85 ..< 115:  // Average
case 115 ..< 130: // Above Average
case 130 ..< 145: // Gifted
case 145...:      // Highly Gifted
```

**Rationale:** These are standardized IQ classification ranges used in psychometrics. They should remain as-is for readability.

### Percentile Ranges (Standard Classification)

```swift
case 0 ..< 25:    // Poor
case 25 ..< 50:   // Below Average
case 50 ..< 75:   // Average
case 75 ..< 90:   // Good
case 90...:       // Excellent
```

**Rationale:** Standard percentile classifications.

### HTTP Status Codes

```swift
case 200 ... 299:  // Success
case 400:          // Bad Request
case 401:          // Unauthorized
case 403:          // Forbidden
case 404:          // Not Found
case 408:          // Request Timeout
case 422:          // Unprocessable Entity
case 500 ... 599:  // Server Error
```

**Rationale:** Standard HTTP status codes - extracting these would reduce readability.

### Time Conversions

```swift
60    // seconds per minute
3600  // seconds per hour
86400 // seconds per day
```

**Rationale:** Standard time conversions used in calculations - inline usage is clear.

### Preview/Test Data

All `totalQuestions: 20`, `userId: 1`, `testSessionId: 123`, etc. values in `#Preview` blocks and mock data are appropriate as hardcoded values.

---

## Recommendations for ICG-096

Based on this audit, the recommended implementation order for ICG-096 is:

### Phase 1 - High Impact (Immediate)

1. Extract Timer configuration to `Constants.Timing`
2. Extract Test configuration to `Constants.Test`
3. Extract Network configuration to `Constants.Network`

### Phase 2 - Medium Impact

4. Extract Analytics configuration to `Constants.Analytics`
5. Extract Cache configuration to `Constants.Cache`
6. Extract Validation rules to `Constants.Validation`

### Phase 3 - Optional

7. Add animation delay constants to `DesignSystem.Animation`
8. Add hero font sizes to `DesignSystem.Typography`

---

## Proposed Constants.swift Structure

```swift
enum Constants {
    // MARK: - Timing Constants (existing)
    enum Timing {
        static let criticalThresholdSeconds: Int = 60
        static let autoSaveDelay: TimeInterval = 1.0
        // NEW
        static let totalTestTimeSeconds: Int = 1800
        static let warningThresholdSeconds: Int = 300
        static let timerUpdateInterval: TimeInterval = 0.25
    }

    // MARK: - Network Constants (existing)
    enum Network {
        static let slowRequestThreshold: TimeInterval = 2.0
        // NEW
        static let requestTimeout: TimeInterval = 30.0
        static let maxTokenRefreshRetries: Int = 1
        static let defaultMaxRetryAttempts: Int = 3
        static let retryableStatusCodes: Set<Int> = [408, 429, 500, 502, 503, 504]
    }

    // MARK: - Test Constants (existing)
    enum Test {
        static let progressValidityDuration: TimeInterval = 86400
        // NEW
        static let defaultQuestionCount: Int = 20
    }

    // MARK: - Analytics Constants (NEW)
    enum Analytics {
        static let maxBatchSize: Int = 50
        static let maxQueueSize: Int = 500
        static let maxRetries: Int = 3
        static let batchInterval: TimeInterval = 30.0
        static let requestTimeout: TimeInterval = 30.0
    }

    // MARK: - Cache Constants (NEW)
    enum Cache {
        static let defaultExpiration: TimeInterval = 300
        static let dashboardCacheDuration: TimeInterval = 120
    }

    // MARK: - Validation Constants (NEW)
    enum Validation {
        static let minPasswordLength: Int = 8
        static let minNameLength: Int = 2
    }

    // MARK: - Pagination Constants (NEW)
    enum Pagination {
        static let historyPageSize: Int = 50
    }

    // MARK: - Onboarding Constants (NEW)
    enum Onboarding {
        static let totalPages: Int = 4
    }

    // MARK: - Security Constants (NEW)
    enum Security {
        static let minRequiredPins: Int = 2
    }
}
```

---

## Summary

| Priority | Count | Impact |
|----------|-------|--------|
| High | 21 values | Direct product behavior |
| Medium | ~30 values | UI consistency |
| Low | ~50 values | Keep as-is |

**Total magic numbers identified:** ~100
**Recommended for extraction:** 21 (High Priority) + optional 30 (Medium Priority)
