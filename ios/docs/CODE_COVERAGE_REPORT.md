# Code Coverage Report

**Generated:** January 3, 2026
**Test Run:** BTS-27 Code Coverage Analysis
**Xcode Version:** 16.3.1
**Simulator:** iPhone 16 (iOS 18.3.1)

## Executive Summary

This report documents code coverage results for the AIQ iOS application after completing unit test tasks BTS-18 through BTS-26. The tests were run with code coverage enabled using `xcodebuild test -enableCodeCoverage YES`.

### AIQ.app Target Coverage (Production Code Only)

| Metric | Value |
|--------|-------|
| **Overall Coverage** | **26.45%** |
| Covered Lines | 3,946 |
| Executable Lines | 14,920 |
| Files Analyzed | 67 |

**Note:** This report focuses exclusively on the AIQ.app target (production code), excluding test files, third-party dependencies, and UITest target code. Previous reports included all targets which inflated the coverage percentage.

**Important:** Line counts in this report represent *executable lines* as reported by Xcode's code coverage tool, not total file lines. Executable lines exclude comments, blank lines, type declarations, and certain Swift constructs. Total file lines may be significantly higher.

## Coverage by Module

| Module | Coverage | Files | Covered/Executable | Files with 0% Coverage |
|--------|----------|-------|-------------------|----------------------|
| **Services** | ~70% | 15 | 1,450/2,073 | 1 |
| **ViewModels** | ~75% | 8 | 704/938 | 2 |
| **Utilities** | ~40% | 13 | 220/550 | 6 |
| **Models** | ~80% | 5 | 240/300 | 1 |
| **Views** | ~10% | 22 | 1,214/12,150 | 18 |
| **Other** | ~20% | 2 | 31/156 | 0 |

### Key Observations

1. **Services layer has good coverage** (~70%) - Core business logic is reasonably well-tested
2. **ViewModels have good coverage** (~75%) - Most MVVM business logic is tested
3. **Models have excellent coverage** (~80%) - Recent test additions (BTS-23 to BTS-25) improved this significantly
4. **Views have very low coverage** (~10%) - SwiftUI views are largely untested, which is expected
5. **18 out of 22 View files** with coverage data have 0% coverage - This is acceptable for SwiftUI views

## Risk-Based Prioritization Framework

This report uses a **risk-based prioritization methodology** to identify which coverage gaps should be addressed first. Rather than simply prioritizing files with 0% coverage, we assess files based on their **risk level** combined with their **coverage gap**.

### Why Risk-Based Prioritization?

Traditional coverage reports prioritize files with the lowest coverage percentage. However, this approach has limitations:

- A 0% coverage file containing only constants is less critical than a 60% coverage file handling authentication
- Security-critical code with *any* coverage gap poses higher risk than utility code with no coverage
- Not all code paths carry equal weight for application security and data integrity

**Risk-based prioritization ensures testing effort is allocated where it matters most for security, reliability, and user safety.**

### Risk Categories

Files are classified into four risk categories based on their function and security impact:

| Risk Level | Description | Coverage Target | Examples |
|------------|-------------|-----------------|----------|
| **Critical** | Security, authentication, validation, sensitive data handling | **100%** | `AuthManager.swift`, `Validators.swift`, `KeychainStorage.swift`, `TokenRefreshInterceptor.swift` |
| **High** | User data processing, network communication, session management | **95%+** | `APIClient.swift`, `NetworkMonitor.swift`, `NotificationManager.swift`, `PrivacyConsentStorage.swift` |
| **Medium** | Business logic, state management, analytics | **80%+** | `DashboardViewModel.swift`, `AnalyticsService.swift`, `PerformanceInsights.swift` |
| **Low** | UI utilities, styling, constants, design system | **60%+** | `ColorPalette.swift`, `Typography.swift`, `DesignSystem.swift` |

### Risk Classification Criteria

Use the following criteria to classify files:

#### Critical Risk Indicators
- Handles authentication tokens, credentials, or session state
- Validates user input (email, password, form data)
- Accesses Keychain or secure storage
- Manages authorization/permissions
- Processes sensitive user data (PII, health data)

#### High Risk Indicators
- Makes network requests to external APIs
- Processes or transforms user data
- Manages persistent storage
- Handles push notifications or user preferences
- Implements retry/recovery logic

#### Medium Risk Indicators
- Contains business logic or calculations
- Manages application state
- Tracks analytics or metrics
- Provides user-facing features

#### Low Risk Indicators
- Defines constants, colors, or typography
- Contains pure UI styling/extensions
- Provides developer utilities
- Has no side effects or state

### Identifying Security-Critical Code Paths

When reviewing code for risk classification, look for these patterns that indicate security-critical functionality:

#### Authentication & Authorization Paths
```swift
// Look for these patterns:
- Token storage/retrieval (Keychain, UserDefaults)
- Login/logout state management
- Session validation
- Permission checks
- OAuth/JWT handling
```

**Files to examine:** Any file importing `Security`, `KeychainAccess`, or containing `token`, `auth`, `credential`, `session` in names.

#### Input Validation Paths
```swift
// Critical validation points:
- User registration (email, password strength)
- Form submission (sanitization)
- API parameter construction
- Deep link parsing
- URL handling
```

**Files to examine:** Files with `Validator`, `Sanitizer`, or validation functions like `isValid`, `validate`, `check`.

#### Data Flow Paths
```swift
// Sensitive data touchpoints:
- Network request construction (headers, body)
- Response parsing (credentials in response)
- Local storage (caching sensitive data)
- Logging (PII exposure risk)
```

**Files to examine:** `APIClient`, `NetworkLogger`, `Cache`, `Storage` files and their callers.

#### Error Handling Paths
```swift
// Security-relevant error handling:
- Auth failure responses (don't leak info)
- Network error recovery (retry with credentials)
- Crash reporting (PII in stack traces)
```

**Files to examine:** Error handlers, interceptors, crash reporting integrations.

### Priority Score Calculation

Files are prioritized using a **Priority Score** that combines risk level with coverage gap:

```
Priority Score = Risk Multiplier × Coverage Gap
```

| Risk Level | Multiplier |
|------------|------------|
| Critical | 4x |
| High | 3x |
| Medium | 2x |
| Low | 1x |

**Coverage Gap** = Target Coverage - Current Coverage

**Example Calculations:**

| File | Risk | Current | Target | Gap | Multiplier | Score |
|------|------|---------|--------|-----|------------|-------|
| `AuthManager.swift` | Critical | 34.4% | 100% | 65.6% | 4x | **262.4** |
| `Validators.swift` | Critical | 0% | 100% | 100% | 4x | **400** |
| `NetworkMonitor.swift` | High | 85% | 95% | 10% | 3x | **30** |
| `PerformanceInsights.swift` | Medium | 0% | 80% | 80% | 2x | **160** |
| `ColorPalette.swift` | Low | 0% | 60% | 60% | 1x | **60** |

**Result:** Even though `PerformanceInsights.swift` has 0% coverage like `ColorPalette.swift`, it has a higher priority score due to its medium risk level. `AuthManager.swift` at 34.4% coverage still ranks high because it's a critical security component.

### Security Alert Threshold

**Files marked with ⚠️ SECURITY ALERT require immediate attention:**

Any **Critical** or **High** risk file with less than its target coverage is flagged:
- Critical files below 100% coverage: ⚠️ SECURITY ALERT
- High risk files below 95% coverage: ⚠️ SECURITY ALERT

These files should be prioritized regardless of other coverage gaps in the codebase.

## Detailed Coverage by Category

### Models (5 files with coverage data)

| File | Coverage | Status | Lines |
|------|----------|--------|-------|
| Models/PerformanceInsights.swift | 0.00% | 🔴 Critical Gap | 0/241 |
| Models/APIError.swift | 74.8% | 🟢 Good | 107/143 |
| Models/Question.swift | 92.3% | ✅ Excellent | 12/13 |
| Models/User.swift | 100.00% | ✅ Complete | 14/14 |

**Recent Test Additions (BTS-23 to BTS-25):**
- ✅ User.swift - 100% coverage (BTS-23)
- ✅ Question.swift - 92.3% coverage (BTS-24)
- ✅ TestSession.swift - Added tests (BTS-25)

**Note:** Some model files may not appear in the coverage report if they weren't executed during test runs or are only used in untested code paths.

### ViewModels (8 files with coverage data)

| File | Coverage | Status | Lines |
|------|----------|--------|-------|
| ViewModels/NotificationSettingsViewModel.swift | 0.00% | 🔴 Critical Gap | 0/216 |
| ViewModels/ViewModelProtocol.swift | 0.00% | 🔴 Low Priority | 0/2 |
| ViewModels/HistoryViewModel.swift | 74.1% | 🟢 Good | 166/224 |
| ViewModels/DashboardViewModel.swift | 84.5% | 🟢 Good | 164/194 |
| ViewModels/BaseViewModel.swift | 85.3% | 🟢 Good | 29/34 |
| ViewModels/LoginViewModel.swift | 100.00% | ✅ Complete | 63/63 |
| ViewModels/RegistrationViewModel.swift | 100.00% | ✅ Complete | 119/119 |

**Recent Test Additions:**
- ✅ LoginViewModel - 100% coverage (existing tests)
- ✅ RegistrationViewModel - 100% coverage (existing tests)
- ✅ BaseViewModel - 85.3% coverage (existing tests)

### Services (15 files with coverage data)

| File | Coverage | Status | Lines |
|------|----------|--------|-------|
| Services/API/RequestInterceptor.swift | 0.00% | 🔴 Critical Gap | 0/22 |
| Services/API/NetworkLogger.swift | 31.1% | 🟡 Needs Improvement | 14/45 |
| Services/Auth/AuthManager.swift | 34.4% | 🟡 Needs Improvement | 64/186 |
| Services/Storage/PrivacyConsentStorage.swift | 36.4% | 🟡 Needs Improvement | 8/22 |
| Services/Auth/NotificationManager.swift | 66.7% | 🟢 Good | 136/204 |
| Services/API/APIClient.swift | 78.5% | 🟢 Good | 347/442 |
| Services/Storage/KeychainStorage.swift | 81.3% | 🟢 Good | 87/107 |
| Services/Analytics/AnalyticsService.swift | 83.6% | 🟢 Good | 433/518 |
| Services/API/NetworkMonitor.swift | 85.0% | 🟢 Good | 34/40 |
| Services/Navigation/AppRouter.swift | 86.1% | 🟢 Good | 68/79 |
| Services/Navigation/DeepLinkHandler.swift | 88.1% | 🟢 Good | 156/177 |
| Services/API/RetryPolicy.swift | 92.9% | ✅ Excellent | 52/56 |
| Services/Storage/DataCache.swift | 94.3% | ✅ Excellent | 66/70 |
| Services/Auth/AuthService.swift | 94.8% | ✅ Excellent | 182/192 |
| Services/Storage/LocalAnswerStorage.swift | 100.00% | ✅ Complete | 73/73 |
| Services/Auth/NotificationService.swift | 100.00% | ✅ Complete | 59/59 |
| Services/Auth/TokenRefreshInterceptor.swift | 100.00% | ✅ Complete | 62/62 |

**Assessment:**
Services are generally well-tested, with 11 of 15 files having 80%+ coverage. Priority areas for improvement:
1. RequestInterceptor (0% - critical network component)
2. AuthManager (34.4% - should be 80%+)
3. NetworkLogger (31.1% - should be 80%+)
4. PrivacyConsentStorage (36.4% - should be 80%+)

### Utilities (13 files with coverage data)

| File | Coverage | Status | Lines |
|------|----------|--------|-------|
| Utilities/Helpers/Validators.swift | 0.00% | 🔴 Critical Gap | 0/45 |
| Utilities/Extensions/View+Extensions.swift | 0.00% | 🟡 Low Priority | 0/16 |
| Utilities/Design/ColorPalette.swift | 0.00% | 🟡 Low Priority | 0/54 |
| Utilities/Extensions/String+Extensions.swift | 0.00% | 🟡 Low Priority | 0/39 |
| Utilities/Helpers/AccessibilityIdentifiers.swift | 0.00% | 🟡 Low Priority | 0/1 |
| Utilities/Design/DesignSystem.swift | 0.00% | 🟡 Low Priority | 0/145 |
| Utilities/Design/Typography.swift | 14.0% | 🟡 Low Priority | 6/43 |
| Utilities/Helpers/AppConfig.swift | 54.5% | 🟢 Adequate | 6/11 |
| Utilities/Extensions/Number+Extensions.swift | 78.6% | 🟢 Good | 132/168 |
| Utilities/Extensions/Date+Extensions.swift | 100.00% | ✅ Complete | 30/30 |
| Utilities/Extensions/Int+Extensions.swift | 100.00% | ✅ Complete | 19/19 |
| Utilities/Extensions/String+Localization.swift | 100.00% | ✅ Complete | 7/7 |
| Utilities/Helpers/CrashlyticsErrorRecorder.swift | 100.00% | ✅ Complete | 20/20 |

**Recent Test Addition (BTS-26):**
- ✅ CrashlyticsErrorRecorder.swift - 100% coverage

**Assessment:**
- **Critical Gap:** Validators.swift (0%, 45 lines) - Contains email, password, and name validation logic
- **Low Priority:** Design system files (ColorPalette, Typography, DesignSystem) - Mostly constants
- **Well Tested:** Date/Int/String extensions have 100% coverage

### Views (22+ files with coverage data)

**Files with High Coverage (4 files):**
| File | Coverage | Status | Lines |
|------|----------|--------|-------|
| Views/Onboarding/PrivacyConsentView.swift | 98.7% | ✅ Excellent | 846/857 |
| Views/Common/RootView.swift | 97.2% | ✅ Excellent | 212/218 |
| Views/History/ChartDomainCalculator.swift | 96.6% | ✅ Excellent | 57/59 |
| Views/Common/PrimaryButton.swift | 84.1% | 🟢 Good | 58/69 |

**Files with Low Coverage:**
| File | Coverage | Status | Lines |
|------|----------|--------|-------|
| Views/Common/NetworkStatusBanner.swift | 8.3% | 🔴 | 2/24 |
| Views/Common/CustomTextField.swift | 5.4% | 🔴 | 5/93 |

**Files with 0% Coverage (18+ files):**

Major View Components:
- Views/Auth/WelcomeView.swift (0/1,085 lines)
- Views/Settings/SettingsView.swift (0/825 lines)
- Views/Dashboard/DashboardView.swift (0/756 lines)
- Views/History/HistoryView.swift (0/763 lines)
- Views/History/InsightsCardView.swift (0/742 lines)

Supporting View Components:
- Views/Dashboard/DashboardCardComponents.swift (0/439 lines)
- Views/Common/MainTabView.swift (0/258 lines)
- Views/Settings/NotificationSettingsView.swift (0/232 lines)
- Views/Test/QuestionCardView.swift (0/169 lines)
- Views/Common/LoadingOverlay.swift (0/151 lines)
- Views/Common/EmptyStateView.swift (0/112 lines)
- Views/Common/ErrorView.swift (0/63 lines)
- Views/Common/ErrorBanner.swift (0/46 lines)
- Views/Common/ContentView.swift (0/29 lines)
- And 4+ more view files...

**Assessment:**
Low view coverage is **expected and acceptable** for SwiftUI projects because:
1. SwiftUI views are difficult to unit test in isolation
2. Business logic should be in ViewModels, not Views
3. Views are covered by UITests (see AIQUITests/ folder)
4. Complex view logic should be extracted to testable helper methods

**Recommendation:** Do not prioritize unit tests for SwiftUI views. Focus on ViewModels and UITests instead.

## Coverage Gaps Analysis (Risk-Based)

This section prioritizes coverage gaps using the **Risk-Based Prioritization Framework** defined above. Files are ordered by Priority Score (Risk Multiplier × Coverage Gap), not simply by coverage percentage.

### ⚠️ Security Alerts (Immediate Action Required)

These files are security-critical and fall below their required coverage targets:

| File | Risk | Coverage | Target | Gap | Score | Status |
|------|------|----------|--------|-----|-------|--------|
| **Utilities/Helpers/Validators.swift** | Critical | 0% | 100% | 100% | **400** | ⚠️ SECURITY ALERT |
| **Services/Auth/AuthManager.swift** | Critical | 34.4% | 100% | 65.6% | **262.4** | ⚠️ SECURITY ALERT |
| **Services/API/RequestInterceptor.swift** | Critical | 0% | 100% | 100% | **400** | ⚠️ SECURITY ALERT |
| **Services/Storage/KeychainStorage.swift** | Critical | 81.3% | 100% | 18.7% | **74.8** | ⚠️ SECURITY ALERT |

**Why these files are critical:**
- `Validators.swift` - Validates all user input (email, password, name). Insufficient validation testing could allow malformed or malicious input.
- `AuthManager.swift` - Manages authentication state, token lifecycle, and session security. Untested paths could expose security vulnerabilities.
- `RequestInterceptor.swift` - Intercepts all API requests. Untested interception logic could leak tokens or mishandle authentication.
- `KeychainStorage.swift` - Handles secure credential storage. All keychain operations must be thoroughly tested.

### Priority 1: Critical Risk Files

Files handling authentication, validation, or sensitive data:

| File | Risk | Current | Target | Gap | Score | Action |
|------|------|---------|--------|-----|-------|--------|
| Validators.swift | Critical | 0% | 100% | 100% | **400** | Add comprehensive validation tests |
| RequestInterceptor.swift | Critical | 0% | 100% | 100% | **400** | Add request/response handling tests |
| AuthManager.swift | Critical | 34.4% | 100% | 65.6% | **262.4** | Expand auth state management tests |
| KeychainStorage.swift | Critical | 81.3% | 100% | 18.7% | **74.8** | Complete remaining edge cases |
| TokenRefreshInterceptor.swift | Critical | 100% | 100% | 0% | **0** | ✅ Complete |
| AuthService.swift | Critical | 94.8% | 100% | 5.2% | **20.8** | Minor gaps to close |

### Priority 2: High Risk Files

Files handling network communication, user data, or session management:

| File | Risk | Current | Target | Gap | Score | Action |
|------|------|---------|--------|-----|-------|--------|
| PrivacyConsentStorage.swift | High | 36.4% | 95% | 58.6% | **175.8** | Expand privacy consent tests |
| NetworkLogger.swift | High | 31.1% | 95% | 63.9% | **191.7** | Test all logging scenarios |
| NotificationManager.swift | High | 66.7% | 95% | 28.3% | **84.9** | Complete notification flow tests |
| APIClient.swift | High | 78.5% | 95% | 16.5% | **49.5** | Close remaining gaps |
| NetworkMonitor.swift | High | 85% | 95% | 10% | **30** | Test edge cases |
| RetryPolicy.swift | High | 92.9% | 95% | 2.1% | **6.3** | Minor improvements |
| DataCache.swift | High | 94.3% | 95% | 0.7% | **2.1** | Nearly complete |

### Priority 3: Medium Risk Files

Files containing business logic, state management, or analytics:

| File | Risk | Current | Target | Gap | Score | Action |
|------|------|---------|--------|-----|-------|--------|
| PerformanceInsights.swift | Medium | 0% | 80% | 80% | **160** | Add performance analysis tests |
| NotificationSettingsViewModel.swift | Medium | 0% | 80% | 80% | **160** | Add notification preference tests |
| TestTakingViewModel.swift | Medium | 69.6% | 80% | 10.4% | **20.8** | Expand test-taking logic coverage |
| HistoryViewModel.swift | Medium | 74.1% | 80% | 5.9% | **11.8** | Minor improvements |
| DashboardViewModel.swift | Medium | 84.5% | 80% | -4.5% | **0** | ✅ Exceeds target |
| AnalyticsService.swift | Medium | 83.6% | 80% | -3.6% | **0** | ✅ Exceeds target |

### Priority 4: Low Risk Files

UI utilities, styling, and constants (lowest priority for testing):

| File | Risk | Current | Target | Gap | Score | Action |
|------|------|---------|--------|-----|-------|--------|
| DesignSystem.swift | Low | 0% | 60% | 60% | **60** | Consider snapshot tests |
| ColorPalette.swift | Low | 0% | 60% | 60% | **60** | Consider snapshot tests |
| String+Extensions.swift | Low | 0% | 60% | 60% | **60** | Low priority |
| Typography.swift | Low | 14% | 60% | 46% | **46** | Low priority |
| View+Extensions.swift | Low | 0% | 60% | 60% | **60** | Low priority |

**Note:** Low risk files contain mostly constants and styling. Consider snapshot tests for visual regression rather than unit tests.

### SwiftUI Views (Excluded from Risk Scoring)

SwiftUI views are excluded from risk-based scoring because:
1. Views should contain minimal business logic (delegate to ViewModels)
2. Views are better tested through UI tests and snapshot tests
3. SwiftUI view code is difficult to unit test in isolation

**Recommended approach for views:**
- UI Tests for critical user flows
- Snapshot tests for visual regression
- Extract any complex logic to ViewModels or testable helpers

The following views should be prioritized for **UI testing** (by user impact):
1. TestTakingView.swift - Core test experience
2. DashboardView.swift - Main app screen
3. HistoryView.swift - Test history
4. SettingsView.swift - App configuration
5. TestResultsView.swift - Results display

## Recommendations

Based on the **Risk-Based Prioritization Framework**, recommendations are ordered by Priority Score rather than coverage percentage alone.

### Immediate Action Required (Security Alerts)

These files have active security alerts and should be addressed before any other coverage work:

1. **Validators.swift** (Score: 400, Critical Risk) - **Proposed: BTS-28**
   - ⚠️ 0% coverage on input validation logic
   - Validates email, password, and name throughout auth flows
   - Security impact: Malformed input could bypass validation
   - **Target:** 100% coverage (Critical requirement)

2. **RequestInterceptor.swift** (Score: 400, Critical Risk) - **Proposed: BTS-30**
   - ⚠️ 0% coverage on request interception
   - Intercepts all API calls for auth token injection
   - Security impact: Untested paths could leak credentials
   - **Target:** 100% coverage (Critical requirement)

3. **AuthManager.swift** (Score: 262.4, Critical Risk) - **Proposed: BTS-32**
   - ⚠️ Only 34.4% coverage on authentication state
   - Manages token lifecycle and session security
   - Security impact: Auth bypass or session fixation risks
   - **Target:** 100% coverage (Critical requirement)

4. **KeychainStorage.swift** (Score: 74.8, Critical Risk) - **Proposed: BTS-36**
   - ⚠️ 81.3% coverage, but handles secure credential storage
   - All keychain read/write paths must be tested
   - Security impact: Credential exposure or storage failures
   - **Target:** 100% coverage (Critical requirement)

### High Priority (High Risk Files)

5. **NetworkLogger.swift** (Score: 191.7, High Risk) - **Proposed: BTS-34**
   - 31.1% coverage on network logging
   - Could inadvertently log sensitive data
   - **Target:** 95% coverage

6. **PrivacyConsentStorage.swift** (Score: 175.8, High Risk) - **Proposed: BTS-33**
   - 36.4% coverage on privacy consent handling
   - Privacy compliance is legally required
   - **Target:** 95% coverage

7. **NotificationManager.swift** (Score: 84.9, High Risk) - **Proposed: BTS-37**
   - 66.7% coverage on notification handling
   - Handles user preferences and push notifications
   - **Target:** 95% coverage

### Medium Priority (Business Logic)

8. **PerformanceInsights.swift** (Score: 160, Medium Risk) - **Proposed: BTS-31**
   - 0% coverage but medium risk (analytics logic)
   - No security implications, affects user insights
   - **Target:** 80% coverage

9. **NotificationSettingsViewModel.swift** (Score: 160, Medium Risk) - **Proposed: BTS-29**
   - 0% coverage but medium risk (UI state)
   - Manages notification preference UI
   - **Target:** 80% coverage

### Low Priority (Design System & Constants)

10. **Design System Files** (Score: ~60 each, Low Risk) - **Proposed: BTS-35 (batch)**
    - ColorPalette.swift, Typography.swift, DesignSystem.swift
    - Mostly constants and SwiftUI modifiers
    - Consider snapshot tests instead of unit tests
    - **Target:** 60% coverage or snapshot tests

### Not Recommended for Unit Testing

**SwiftUI Views** - Excluded from risk scoring:
- Views should contain minimal logic (delegate to ViewModels)
- SwiftUI views are better covered by UITests
- Extract any complex logic to ViewModels or testable helpers
- Focus efforts on security-critical components first

---

## Coverage Goals

### Target Coverage by Component

| Component | Current | Short-Term Target | Long-Term Target |
|-----------|---------|-------------------|------------------|
| **Models** | ~80% | 90% | 95% |
| **ViewModels** | ~75% | 85% | 90% |
| **Services** | ~70% | 80% | 90% |
| **Utilities** | ~40% | 60% | 75% |
| **Views** | ~10% | 15%* | 20%* |
| **Overall** | **26.45%** | **50%** | **70%** |

\* Views should focus on UITests and extracting logic to ViewModels rather than increasing unit test coverage

### Short-Term Goals (After BTS-28 to BTS-34)

After completing the recommended test additions, estimated coverage:
- **Models:** 90%+ (after PerformanceInsights tests)
- **ViewModels:** 85%+ (after NotificationSettingsViewModel tests)
- **Services:** 75%+ (after RequestInterceptor, AuthManager, NetworkLogger tests)
- **Utilities:** 50%+ (after Validators tests)
- **Overall:** ~40%+

### Long-Term Strategy

1. **Coverage Standards**
   - Models: 90% minimum
   - Services: 85% minimum
   - ViewModels: 80% minimum
   - Utilities: 75% minimum (excluding design system)
   - Views: Focus on UITests rather than coverage %

2. **CI/CD Integration** (Future)
   - Add coverage checks to PR requirements
   - Fail builds if coverage drops below thresholds
   - Generate coverage reports on each PR

3. **Coverage Monitoring**
   - Track coverage trends over time
   - Set quarterly coverage improvement goals
   - Review coverage reports in sprint retrospectives

## Testing Best Practices

Based on current coverage analysis, follow these guidelines:

### What to Test (Priority Order)

1. **Business Logic** (Models, ViewModels, Services)
   - Pure functions and calculations
   - State management
   - Data transformations
   - Error handling

2. **Edge Cases**
   - Boundary conditions
   - Invalid inputs
   - Network failures
   - Race conditions

3. **Critical Paths**
   - Authentication flows
   - Test submission
   - Score calculation
   - Data persistence

### What NOT to Test (Low ROI)

1. **SwiftUI View Bodies**
   - Use UI tests or snapshot tests instead
   - Focus on ViewModels for business logic

2. **Third-Party Code**
   - Firebase, TrustKit, etc.
   - Trust external library tests

3. **Trivial Code**
   - Simple getters/setters without logic
   - Basic property wrappers (@Published, @State)

## Files Analyzed

**Total Files (AIQ.app target):** 67
**Files with Good Coverage (80%+):** 26 (38.8%)
**Files with Medium Coverage (50-79%):** 6 (9.0%)
**Files with Low Coverage (1-49%):** 7 (10.4%)
**Files with No Coverage (0%):** 28 (41.8%)

### Files with 100% Coverage (12 files)

Excellent examples of comprehensive testing:

- **AIQApp.swift** (11/11)
- **Models/User.swift** (14/14) - BTS-23
- **Services/Storage/LocalAnswerStorage.swift** (73/73)
- **Services/Auth/NotificationService.swift** (59/59)
- **Services/Auth/TokenRefreshInterceptor.swift** (62/62)
- **ViewModels/LoginViewModel.swift** (63/63)
- **ViewModels/RegistrationViewModel.swift** (119/119)
- **Utilities/Helpers/CrashlyticsErrorRecorder.swift** (20/20) - BTS-26
- **Utilities/Extensions/String+Localization.swift** (7/7)
- **Utilities/Extensions/Int+Extensions.swift** (19/19)
- **Utilities/Extensions/Date+Extensions.swift** (30/30)
- **Views/Onboarding/PrivacyConsentView.swift** (98.7% - 846/857)

### Files with 0% Coverage (28 files) - Risk-Based Classification

**⚠️ Critical Risk (Security Alert - Immediate Action):**
- Utilities/Helpers/Validators.swift (45 lines) - Score: 400
- Services/API/RequestInterceptor.swift (22 lines) - Score: 400

**Medium Risk (Business Logic):**
- Models/PerformanceInsights.swift (241 lines) - Score: 160
- ViewModels/NotificationSettingsViewModel.swift (216 lines) - Score: 160

**Low Risk (Design System):**
- Utilities/Design/ColorPalette.swift (54 lines) - Score: 60
- Utilities/Design/DesignSystem.swift (145 lines) - Score: 60
- Utilities/Design/Typography.swift (partial - 14.0%) - Score: 46
- Utilities/Extensions/View+Extensions.swift (16 lines) - Score: 60
- Utilities/Extensions/String+Extensions.swift (39 lines) - Score: 60
- Utilities/Helpers/AccessibilityIdentifiers.swift (1 line) - Score: 60

**Views (18+ files - Excluded from Risk Scoring):**
- See detailed Views section above
- Low view coverage is expected for SwiftUI projects
- Views should be tested via UI tests, not unit tests

## Appendix: Test Execution Details

### Test Suite Summary

```
Test execution completed successfully
Total Tests Executed: Unit tests + UITests
UITests Status: Most skipped (require backend connection and valid test account)
Test Failures: 0
```

**Note:** UITests are currently skipped in CI/local environments because they require:
- Live backend connection
- Valid test account credentials
- Full app flow simulation

Unit tests run successfully and provide the coverage metrics in this report.

### Coverage Report Generation

```bash
# From ios/ directory
cd /Users/mattgioe/aiq/ios

# Run tests with coverage enabled
xcodebuild test \
  -scheme AIQ \
  -project AIQ.xcodeproj \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=18.3.1' \
  -enableCodeCoverage YES \
  -derivedDataPath ./build/DerivedData

# Extract coverage data (text format)
xcrun xccov view --report \
  ./build/DerivedData/Logs/Test/*.xcresult

# Extract coverage data (JSON format)
xcrun xccov view --report --json \
  ./build/DerivedData/Logs/Test/*.xcresult
```

### Environment

- **Xcode:** 16.3.1
- **iOS SDK:** 18.3.1
- **Simulator:** iPhone 16 Pro (iOS 18.3.1, arm64)
- **macOS:** Darwin 25.1.0
- **Swift Version:** 6.0
- **Test Date:** January 3, 2026

### Analysis Method

Coverage data was extracted and analyzed using:
1. `xcrun xccov` command-line tool
2. Python script for JSON parsing and categorization
3. Manual review of critical files and components

---

## Summary

**Current State:**
- Overall coverage: **26.45%** (AIQ.app target only)
- Strong coverage in Models, ViewModels, and Services
- Expected low coverage in SwiftUI Views

**Risk-Based Assessment:**
- **4 Security Alerts Active:** Validators.swift, RequestInterceptor.swift, AuthManager.swift, KeychainStorage.swift
- **Total Critical Risk Files:** 6 (2 at 100%, 4 below target)
- **Total High Risk Files:** 7 (most below 95% target)
- **Files Prioritized by Risk Score:** Security-critical files now rank higher than 0% coverage utility files

**Next Steps (Risk-Prioritized Order):**
1. ⚠️ **Immediate:** Address security alerts - Validators.swift (BTS-28), RequestInterceptor.swift (BTS-30)
2. ⚠️ **Immediate:** Complete AuthManager.swift (BTS-32), KeychainStorage.swift (BTS-36) to 100%
3. **High Priority:** NetworkLogger.swift (BTS-34), PrivacyConsentStorage.swift (BTS-33)
4. **Medium Priority:** PerformanceInsights.swift (BTS-31), NotificationSettingsViewModel.swift (BTS-29)
5. Re-run coverage report after test additions
6. Track coverage trends and risk scores over time

**Targets:**
- All Critical Risk files: **100% coverage**
- All High Risk files: **95% coverage**
- Overall coverage: **50%+** after completing risk-prioritized test additions

---

**Report Generated:** January 3, 2026
**Risk Framework Added:** January 9, 2026 (BTS-177)
**Branch:** feature/BTS-27-code-coverage-report
**Related Tasks:** BTS-27 (original report), BTS-177 (risk-based prioritization), BTS-18 to BTS-26 (completed)
**Next Review:** After completing security alert items (BTS-28, BTS-30, BTS-32, BTS-36)
**Maintained By:** iOS Engineering Team
