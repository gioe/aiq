# Implementation Plan: iOS Codebase Gaps

**Source:** docs/gaps/IOS-CODEBASE-GAPS.md
**Task Prefix:** ICG
**Generated:** 2025-12-24

## Overview

This plan addresses 32 identified gaps in the AIQ iOS application across architecture, testing, security, and production readiness. The work includes crash reporting integration, deep linking implementation, UI testing infrastructure, privacy compliance, security hardening, and code quality improvements required before App Store submission.

## Tasks

### ICG-001: Fix AppConfig URL Bug
**Status:** [x] Complete
**Files:** `Utilities/Helpers/AppConfig.swift`
**Description:** Remove `/v1` from base URL to prevent double path segments. The API endpoints already include `/v1` in their paths.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Base URL changed from `https://aiq-backend-production.up.railway.app/v1` to `https://aiq-backend-production.up.railway.app`
- [x] All API endpoints tested and working (login, registration, test start, test submit)
- [x] No breaking changes to existing API calls

---

### ICG-002: Integrate Firebase Crashlytics SDK
**Status:** [x] Complete
**Files:** `AIQApp.swift`, `Package.swift`
**Description:** Add Firebase Crashlytics via Swift Package Manager, initialize in app launch, and test crash reporting functionality.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Firebase SDK integrated via Swift Package Manager
- [x] Crashlytics initialized in app launch
- [x] Test crash successfully reported to Firebase console

---

### ICG-003: Create Firebase Project and Configure iOS App
**Status:** [x] Complete
**Files:** `GoogleService-Info.plist` (new)
**Description:** Create Firebase project, download GoogleService-Info.plist, and configure APNs certificates.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Firebase project created with iOS app configuration
- [x] GoogleService-Info.plist added to Xcode project
- [x] Build succeeds with Firebase integration

---

### ICG-004: Update AnalyticsService for Backend Integration
**Status:** [x] Complete
**Files:** `Services/Analytics/AnalyticsService.swift`
**Description:** Update AnalyticsService to send events to backend `/v1/analytics/events` endpoint with retry logic and offline queue.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] AnalyticsService sends events to backend API
- [x] Event payloads match backend schema
- [x] Network errors handled gracefully with retry logic
- [x] Events logged locally if offline (queue for later sync)

---

### ICG-005: Add Crashlytics Logging to ViewModels
**Status:** [x] Complete
**Files:** All ViewModels, `Utilities/Helpers/CrashlyticsErrorRecorder.swift` (new)
**Description:** Replace OSLog with Crashlytics.recordError() in catch blocks across all ViewModel error handlers.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] All ViewModel error handlers record non-fatal errors to Crashlytics
- [x] User-facing errors still logged to OSLog for debugging
- [x] No duplicate error logging

---

### ICG-007: Create AppRouter with NavigationPath
**Status:** [x] Complete
**Files:** `Services/Navigation/AppRouter.swift` (new), `AIQTests/Services/AppRouterTests.swift` (new)
**Description:** Create AppRouter class with NavigationPath-based coordinator pattern for centralized navigation management.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] AppRouter class created with NavigationPath state management
- [x] Router supports push, pop, popToRoot, and direct navigation methods
- [x] Router is observable and injectable via environment
- [x] Unit tests written for all navigation methods

---

### ICG-008: Create DeepLinkHandler
**Status:** [x] Complete
**Files:** `Services/Navigation/DeepLinkHandler.swift` (new), `AIQTests/Services/DeepLinkHandlerTests.swift` (new)
**Description:** Create DeepLinkHandler to parse URL schemes and universal links into structured navigation commands.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] DeepLinkHandler parses URL schemes (aiq://)
- [x] DeepLinkHandler parses universal links (https://aiq.app/...)
- [x] Returns structured DeepLink enum with associated data
- [x] Unit tests for URL scheme parsing
- [x] Unit tests for universal link parsing
- [x] Unit tests for invalid URL handling

---

### ICG-009: Register URL Schemes in Info.plist
**Status:** [x] Complete
**Files:** `Info.plist`
**Description:** Add `aiq://` custom URL scheme to Info.plist.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] `aiq://` URL scheme registered in Info.plist
- [x] App responds to `aiq://` URLs from Safari and other apps

---

### ICG-010: Configure Universal Links
**Status:** [x] Complete
**Files:** `AIQ.entitlements`, Apple Developer Portal
**Description:** Add Associated Domains entitlement for `applinks:aiq.app`.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Associated Domains entitlement added
- [ ] Universal link domain verified in Apple Developer Portal (manual step - see PR description)
- [ ] App responds to `https://aiq.app/...` links (requires handler implementation in ICG-016)

---

### ICG-011: Integrate AppRouter into AIQApp.swift
**Status:** [x] Complete
**Files:** `AIQApp.swift`
**Description:** Replace root view navigation with router-based navigation.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] AppRouter initialized in AIQApp.swift
- [x] Router injected into environment
- [x] Root navigation controlled by router

---

### ICG-012: Migrate DashboardView Navigation
**Status:** [ ] Not Started
**Files:** `Views/Dashboard/DashboardView.swift`
**Description:** Replace sheet/fullScreenCover modifiers with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-013: Migrate TestTakingView Navigation
**Status:** [ ] Not Started
**Files:** `Views/Test/TestTakingView.swift`
**Description:** Replace navigation state management with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-014: Migrate HistoryView Navigation
**Status:** [ ] Not Started
**Files:** `Views/History/HistoryView.swift`
**Description:** Replace navigation state management with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-015: Migrate SettingsView Navigation
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Description:** Replace navigation state management with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-016: Implement Deep Link Handling in AppDelegate
**Status:** [ ] Not Started
**Files:** `AppDelegate.swift`
**Description:** Handle `application(_:open:options:)` callback to process deep links.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] AppDelegate handles URL opening callbacks
- [ ] URLs parsed by DeepLinkHandler
- [ ] Router navigates to correct destination

---

### ICG-017: Add Deep Link Routes
**Status:** [ ] Not Started
**Files:** `Services/Navigation/DeepLinkHandler.swift`
**Description:** Implement routes for `aiq://test/results/{id}`, `aiq://test/resume/{sessionId}`, `aiq://settings`.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All three route types implemented
- [ ] Invalid routes handled gracefully with error state
- [ ] Routes work from cold start and background state
- [ ] Unit tests for all route types

---

### ICG-018: Test Deep Links from Push Notifications
**Status:** [ ] Not Started
**Files:** Test only
**Description:** Verify notification tap navigates correctly to target screens.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Push notification tap opens app to correct screen
- [ ] Notification payload structure tested
- [ ] Works in foreground, background, and terminated states

---

### ICG-019: Create AIQUITests Target
**Status:** [ ] Not Started
**Files:** `AIQUITests/` (new directory)
**Description:** Create UI test target in Xcode with correct configuration, test host, bundle ID, and signing.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] AIQUITests target created with correct configuration
- [ ] Test target builds successfully
- [ ] Can run UI tests from Xcode

---

### ICG-020: Create UI Test Helpers
**Status:** [ ] Not Started
**Files:** `AIQUITests/Helpers/` (new)
**Description:** Create LoginHelper, TestTakingHelper, and NavigationHelper for test code reuse.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] LoginHelper provides authenticated test sessions
- [ ] TestTakingHelper handles test data setup
- [ ] NavigationHelper verifies screen transitions
- [ ] Helpers reduce test boilerplate

---

### ICG-021: Write Registration Flow UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/RegistrationFlowTests.swift` (new)
**Description:** Complete registration from start to dashboard with validation testing.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test completes full registration flow
- [ ] Validates field validation errors
- [ ] Verifies successful registration leads to dashboard
- [ ] Runs reliably without flakiness

---

### ICG-022: Write Login/Logout Flow UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/AuthenticationFlowTests.swift` (new)
**Description:** Test login with valid/invalid credentials and logout flow.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test covers login with valid credentials
- [ ] Test covers login with invalid credentials
- [ ] Test covers logout flow
- [ ] Verifies session persistence

---

### ICG-023: Write Test-Taking Flow UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/TestTakingFlowTests.swift` (new)
**Description:** Start test, answer all questions, submit, and verify results.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test starts a new test session
- [ ] Test answers all questions (mocked question data)
- [ ] Test submits answers and verifies results screen
- [ ] Verifies score display and history update

---

### ICG-024: Write Test Abandonment UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/TestAbandonmentTests.swift` (new)
**Description:** Start test, abandon mid-flow, verify saved progress, and resume.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test starts test and abandons mid-flow
- [ ] Test verifies saved progress
- [ ] Test resumes test and completes
- [ ] Verifies no data loss on abandonment

---

### ICG-025: Write Deep Link Navigation UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/DeepLinkTests.swift` (new)
**Description:** Test all deep link routes from terminated state.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test all deep link routes (results, resume, settings)
- [ ] Test from app terminated state
- [ ] Test from app backgrounded state
- [ ] Verifies correct screen displayed

---

### ICG-026: Write Error State Handling UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/ErrorHandlingTests.swift` (new)
**Description:** Test network errors, invalid responses, and retry logic.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test network error handling with retry
- [ ] Test invalid API response handling
- [ ] Test timeout scenarios
- [ ] Verifies user-facing error messages

---

### ICG-027: Configure UI Tests in CI/CD
**Status:** [ ] Not Started
**Files:** `.github/workflows/ios-tests.yml`
**Description:** Add UI tests to GitHub Actions or Xcode Cloud.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] UI tests run automatically on pull requests
- [ ] Test failures block merge
- [ ] Test reports uploaded as artifacts

---

### ICG-028: Create PrivacyInfo.xcprivacy Manifest
**Status:** [ ] Not Started
**Files:** `PrivacyInfo.xcprivacy` (new)
**Description:** Declare data collection and usage for App Store privacy requirements.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] PrivacyInfo.xcprivacy created with all required fields
- [ ] Declares analytics, crash reporting, authentication data
- [ ] Passes App Store privacy validation

---

### ICG-029: Draft Privacy Policy Document
**Status:** [ ] Not Started
**Files:** External: Privacy policy website/PDF
**Description:** Cover data collection, storage, sharing, and deletion policies.
**Assignee(s):** technical-product-manager
**Acceptance Criteria:**
- [ ] Privacy policy covers all data collected
- [ ] Explains data retention and deletion
- [ ] Complies with GDPR and CCPA requirements
- [ ] Hosted at publicly accessible URL

---

### ICG-030: Draft Terms of Service Document
**Status:** [ ] Not Started
**Files:** External: Terms of service website/PDF
**Description:** Cover user agreements, disclaimers, and liability.
**Assignee(s):** technical-product-manager
**Acceptance Criteria:**
- [ ] Terms of service cover liability disclaimers
- [ ] Addresses intellectual property
- [ ] Hosted at publicly accessible URL
- [ ] Legal review completed

---

### ICG-031: Implement Consent Management Screen
**Status:** [ ] Not Started
**Files:** `Views/Onboarding/PrivacyConsentView.swift` (new)
**Description:** Display privacy policy and require acceptance on first launch.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Privacy consent screen shown on first launch
- [ ] User must accept to continue
- [ ] Consent timestamp stored locally
- [ ] Links to full privacy policy and terms

---

### ICG-032: Add Data Deletion Capability
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`, Backend: `/v1/user/delete-account` (new)
**Description:** Add settings option to delete account and all user data (GDPR right to erasure).
**Assignee(s):** ios-engineer, fastapi-architect
**Acceptance Criteria:**
- [ ] Settings screen includes "Delete Account" option
- [ ] Confirmation dialog warns of irreversible action
- [ ] Backend endpoint deletes all user data (GDPR right to erasure)
- [ ] User logged out and returned to welcome screen

---

### ICG-033: Update App Store Metadata
**Status:** [ ] Not Started
**Files:** App Store Connect
**Description:** Update privacy questions, data usage descriptions, and screenshots.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] App Store Connect metadata updated
- [ ] Privacy questions answered accurately
- [ ] Screenshots show current UI
- [ ] App description mentions privacy compliance

---

### ICG-034: Create Localizable.strings File
**Status:** [ ] Not Started
**Files:** `en.lproj/Localizable.strings` (new)
**Description:** Create base English localization file with all string keys.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Localizable.strings file created in Xcode
- [ ] All strings have unique keys
- [ ] Base localization (English) complete

---

### ICG-035: Create String+Localization Extension
**Status:** [ ] Not Started
**Files:** `Utilities/Extensions/String+Localization.swift`, `AIQTests/Extensions/StringLocalizationTests.swift` (new)
**Description:** Add `.localized` helper for string keys.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] String extension provides `.localized` computed property
- [ ] Extension handles missing keys gracefully
- [ ] Works with string interpolation
- [ ] Unit tests for localized property behavior

---

### ICG-036: Extract Hardcoded Strings from Views
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Replace all hardcoded strings in Views with localization keys.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All user-facing strings in Views use localization keys
- [ ] No hardcoded English strings remain
- [ ] App builds and runs with localized strings

---

### ICG-037: Extract Hardcoded Strings from ViewModels
**Status:** [ ] Not Started
**Files:** All ViewModel files
**Description:** Replace all hardcoded strings in ViewModels with localization keys.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All user-facing strings in ViewModels use localization
- [ ] Validation messages localized
- [ ] Success/error messages localized

---

### ICG-038: Extract Error Messages to Localizable.strings
**Status:** [ ] Not Started
**Files:** All Service files
**Description:** Replace all error message strings with localization keys.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All error messages use localization keys
- [ ] Error codes preserved for debugging
- [ ] User-friendly error messages in all cases

---

### ICG-039: Add RTL Layout Support
**Status:** [ ] Not Started
**Files:** Test only
**Description:** Test with Arabic/Hebrew simulators to verify RTL layout support.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] App layout tested in RTL languages
- [ ] No UI overlaps or truncation
- [ ] Navigation behaves correctly in RTL

---

### ICG-040: Configure Locale-Aware Formatting
**Status:** [ ] Not Started
**Files:** `Utilities/Extensions/Date+Extensions.swift`
**Description:** Ensure all formatters respect user locale for dates and numbers.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] DateFormatter respects user locale
- [ ] Number formatting uses locale-specific separators
- [ ] Currency formatting works for all supported locales

---

### ICG-041: Wrap Sensitive Logging in DEBUG Guards
**Status:** [ ] Not Started
**Files:** `Services/Auth/AuthService.swift` (lines 42-45, 70-73, 99-103)
**Description:** Wrap email, token, and user data logging in `#if DEBUG` blocks.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All email logging wrapped in `#if DEBUG` blocks
- [ ] All token logging wrapped in `#if DEBUG` blocks
- [ ] All user PII logging wrapped in `#if DEBUG` blocks
- [ ] Production builds log no sensitive data

---

### ICG-042: Audit All OSLog Calls for Sensitive Data
**Status:** [ ] Not Started
**Files:** All files with OSLog usage
**Description:** Remove or wrap all sensitive data logging in DEBUG guards.
**Assignee(s):** ios-engineer, code-reviewer
**Acceptance Criteria:**
- [ ] Full codebase audit completed
- [ ] Spreadsheet/report of all logging calls created
- [ ] All sensitive logging wrapped or removed
- [ ] Non-sensitive logging preserved for debugging

---

### ICG-043: Integrate TrustKit for Certificate Pinning
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`, `TrustKit.plist` (new)
**Description:** Add TrustKit via SPM and create configuration file.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] TrustKit integrated via Swift Package Manager
- [ ] TrustKit.plist configuration file created
- [ ] TrustKit initialized in app launch

---

### ICG-044: Configure Production SSL Certificate Pins
**Status:** [ ] Not Started
**Files:** `TrustKit.plist`
**Description:** Extract public key hashes from Railway certificates and configure pins.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Production backend SSL certificate analyzed
- [ ] Public key hashes extracted and configured
- [ ] Backup pins configured for rotation safety
- [ ] Pin expiration dates documented

---

### ICG-045: Test Certificate Pinning
**Status:** [ ] Not Started
**Files:** Test only
**Description:** Verify pinning blocks MITM attacks and allows valid certificates.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Valid certificates accepted (app works normally)
- [ ] Invalid certificates rejected (network calls fail)
- [ ] Self-signed certificates blocked
- [ ] MITM proxy blocked

---

### ICG-046: Add Environment-Specific Pinning Config
**Status:** [ ] Not Started
**Files:** `TrustKit.plist`, `AppConfig.swift`
**Description:** Disable pinning in DEBUG builds to allow development proxies.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] DEBUG builds skip certificate pinning
- [ ] RELEASE builds enforce certificate pinning
- [ ] Staging environment uses separate pin config
- [ ] Environment switching tested

---

### ICG-047: Write AuthService Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/AuthServiceTests.swift` (new)
**Description:** Test login, logout, registration, and token refresh with mocked dependencies. AuthService exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All AuthService methods tested
- [ ] Success and error cases covered
- [ ] Mock APIClient used for isolation
- [ ] Edge cases tested (expired tokens, network errors)

---

### ICG-048: Write NotificationService Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/NotificationServiceTests.swift` (new)
**Description:** Test device registration and preference updates. NotificationService exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All public methods tested
- [ ] Success and error paths covered
- [ ] Dependencies mocked
- [ ] Async operations tested correctly

---

### ICG-049: Write NotificationManager Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/NotificationManagerTests.swift` (new)
**Description:** Test scheduling and permission handling. NotificationManager exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All public methods tested
- [ ] Success and error paths covered
- [ ] Dependencies mocked
- [ ] Async operations tested correctly

---

### ICG-050: Write AnalyticsService Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/AnalyticsServiceTests.swift` (new)
**Description:** Test event tracking, backend sync, retry logic, and offline queue. AnalyticsService exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Unit tests for submitWithRetry exponential backoff logic
- [ ] Tests for offline queue persistence (persistEvents/loadPersistedEvents)
- [ ] Tests for event batch submission success/failure scenarios
- [ ] Tests for network connectivity handling
- [ ] Tests for auth token inclusion (optional)
- [ ] Mock UserDefaults and NetworkMonitor for isolation

---

### ICG-051: Write KeychainStorage Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Storage/KeychainStorageTests.swift` (new)
**Description:** Test token storage, retrieval, and deletion. KeychainStorage exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All storage operations tested
- [ ] Data persistence verified
- [ ] Error handling tested
- [ ] Concurrent access tested

---

### ICG-052: Write LocalAnswerStorage Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Storage/LocalAnswerStorageTests.swift` (new)
**Description:** Test answer persistence and retrieval. LocalAnswerStorage exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All storage operations tested
- [ ] Data persistence verified
- [ ] Error handling tested
- [ ] Concurrent access tested

---

### ICG-053: Write DataCache Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Storage/DataCacheTests.swift` (new)
**Description:** Test cache storage, expiration, and invalidation. DataCache exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All storage operations tested
- [ ] Data persistence verified
- [ ] Error handling tested
- [ ] Concurrent access tested

---

### ICG-054: Write RetryPolicy Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Network/RetryPolicyTests.swift` (new)
**Description:** Test exponential backoff and max retries. RetryPolicy exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All retry logic tested
- [ ] Exponential backoff verified
- [ ] Max retry limit enforced
- [ ] Edge cases covered

---

### ICG-055: Write TokenRefreshInterceptor Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Network/TokenRefreshInterceptorTests.swift` (new)
**Description:** Test concurrent request handling and race conditions. TokenRefreshInterceptor exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All interceptor logic tested
- [ ] Concurrent request handling verified
- [ ] Race conditions prevented
- [ ] Token refresh flow tested

---

### ICG-056: Write NetworkMonitor Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Network/NetworkMonitorTests.swift` (new)
**Description:** Test connection status changes. NetworkMonitor exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All monitor logic tested
- [ ] Connection status changes verified
- [ ] Callbacks fired correctly
- [ ] Edge cases covered

---

### ICG-057: Write User Model Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Models/UserTests.swift` (new)
**Description:** Test validation and serialization. User model exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All model validation tested
- [ ] Serialization/deserialization tested
- [ ] Edge cases covered
- [ ] Invalid data handled

---

### ICG-058: Write Question Model Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Models/QuestionTests.swift` (new)
**Description:** Test validation and answer checking. Question model exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All model validation tested
- [ ] Serialization/deserialization tested
- [ ] Edge cases covered
- [ ] Invalid data handled

---

### ICG-059: Write TestSession Model Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Models/TestSessionTests.swift` (new)
**Description:** Test status transitions and validation. TestSession model exists but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All model validation tested
- [ ] Serialization/deserialization tested
- [ ] Edge cases covered
- [ ] Invalid data handled

---

### ICG-060: Write CrashlyticsErrorRecorder Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Utilities/CrashlyticsErrorRecorderTests.swift` (new)
**Description:** Test error context categorization and error type detection. CrashlyticsErrorRecorder was created in ICG-005 but has no test coverage.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Unit tests for error context categorization
- [ ] Tests for APIError vs ContextualError detection
- [ ] Tests for additionalInfo merging logic
- [ ] Mock Crashlytics for isolation in RELEASE builds

---

### ICG-061: Run Code Coverage Report
**Status:** [ ] Not Started
**Files:** Xcode coverage tool
**Description:** Generate coverage report and identify remaining gaps.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Code coverage report generated
- [ ] Coverage percentage by file documented
- [ ] Gaps identified and prioritized

---

### ICG-062: Write Additional Tests for 80% Coverage
**Status:** [ ] Not Started
**Files:** Various test files
**Description:** Fill coverage gaps to reach 80% target.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Code coverage reaches 80% or higher
- [ ] Critical paths have 100% coverage
- [ ] Remaining gaps documented with justification

---

### ICG-063: Audit All Views with VoiceOver
**Status:** [ ] Not Started
**Files:** Test audit (documentation only)
**Description:** Test every screen with VoiceOver enabled and document issues.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All screens tested with VoiceOver
- [ ] Navigation flow logical and clear
- [ ] All interactive elements reachable
- [ ] Issues documented with severity

---

### ICG-064: Add Accessibility Labels to Interactive Elements
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Add descriptive accessibility labels to all buttons, images, and form fields.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All buttons have descriptive labels
- [ ] All images have alt text
- [ ] Form fields have labels
- [ ] No unlabeled interactive elements

---

### ICG-065: Add Accessibility Hints for Non-Obvious Interactions
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Add hints for gestures and complex interactions.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Non-obvious gestures have hints
- [ ] Complex interactions explained
- [ ] Hints concise and helpful

---

### ICG-066: Verify Color Contrast Meets WCAG AA
**Status:** [ ] Not Started
**Files:** `Utilities/Design/ColorPalette.swift`
**Description:** Use contrast checker tool to verify all color combinations.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All color combinations tested
- [ ] Contrast ratios documented
- [ ] Failing combinations identified

---

### ICG-067: Fix Color Contrast Failures
**Status:** [ ] Not Started
**Files:** `Utilities/Design/ColorPalette.swift`
**Description:** Adjust colors to meet 4.5:1 ratio for normal text.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All color contrast meets 4.5:1 for normal text
- [ ] All color contrast meets 3:1 for large text
- [ ] Visual design preserved where possible

---

### ICG-068: Verify Touch Targets Meet 44x44pt Minimum
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Audit all buttons and interactive elements for minimum touch target size.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All buttons and tap targets measured
- [ ] Undersized targets documented
- [ ] Priority list created

---

### ICG-069: Fix Undersized Touch Targets
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Add padding or minimum frame sizes to undersized targets.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All touch targets 44x44pt or larger
- [ ] No tappable elements too small
- [ ] Visual design preserved

---

### ICG-070: Test Dynamic Type Support
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Verify all text scales correctly at all Dynamic Type sizes.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] App tested at all Dynamic Type sizes (XS to XXXL)
- [ ] Text truncation issues identified
- [ ] Layout issues documented

---

### ICG-071: Fix Dynamic Type Issues
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Use relative spacing and avoid fixed heights for text containers.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All text scales without truncation
- [ ] Layouts adapt to large text
- [ ] Scrollable regions used where needed

---

### ICG-072: Test Reduce Motion Support
**Status:** [ ] Not Started
**Files:** All animated views
**Description:** Verify animations respect accessibility Reduce Motion setting.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All animations tested with Reduce Motion enabled
- [ ] Disorienting animations identified

---

### ICG-073: Add Reduce Motion Alternatives
**Status:** [ ] Not Started
**Files:** All animated views
**Description:** Disable or simplify animations when Reduce Motion is enabled.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Animations disabled or simplified when Reduce Motion enabled
- [ ] Transitions remain functional
- [ ] User experience preserved

---

### ICG-074: Document Accessibility Features in App Store
**Status:** [ ] Not Started
**Files:** App Store Connect
**Description:** List accessibility features in App Store description.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Accessibility features listed in App Store description
- [ ] VoiceOver support highlighted
- [ ] Dynamic Type support mentioned

---

### ICG-075: Design Onboarding Flow
**Status:** [ ] Not Started
**Files:** Design mockups
**Description:** Design 3-4 screens explaining app value and test mechanics.
**Assignee(s):** technical-product-manager
**Acceptance Criteria:**
- [ ] Onboarding flow designed with 3-4 screens
- [ ] Content finalized and approved
- [ ] Illustrations or graphics sourced

---

### ICG-076: Create OnboardingView
**Status:** [ ] Not Started
**Files:** `Views/Onboarding/OnboardingView.swift` (new)
**Description:** Create OnboardingView with page indicators and skip option.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] OnboardingView created with SwiftUI TabView
- [ ] Page indicators show progress
- [ ] Skip button allows bypassing
- [ ] "Get Started" button on final screen
- [ ] Screen 1: App value proposition
- [ ] Screen 2: How tests work
- [ ] Screen 3: Recommended 3-month frequency
- [ ] Screen 4: Privacy and data handling

---

### ICG-077: Integrate Onboarding into First-Launch Flow
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Description:** Show onboarding after registration or on first open.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Onboarding shown on first launch after registration
- [ ] Onboarding shown on first launch for existing users (migration)
- [ ] Flag stored to prevent repeated display

---

### ICG-078: Add View Onboarding Again to Settings
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Description:** Add option to re-view onboarding from Settings.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Settings includes "View Onboarding Again" option
- [ ] Tapping option displays onboarding flow
- [ ] User can skip through quickly

---

### ICG-079: Create FeedbackView
**Status:** [ ] Not Started
**Files:** `Views/Settings/FeedbackView.swift` (new)
**Description:** Create feedback form with name, email, category, and description fields.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Feedback form includes all required fields
- [ ] Form validation prevents empty submissions
- [ ] Category dropdown includes common feedback types

---

### ICG-080: Implement Feedback Submission to Backend
**Status:** [ ] Not Started
**Files:** Backend: `/v1/feedback/submit` (new), `Views/Settings/FeedbackView.swift`
**Description:** Create backend endpoint and connect iOS form submission.
**Assignee(s):** ios-engineer, fastapi-architect
**Acceptance Criteria:**
- [ ] Backend endpoint created and tested
- [ ] Feedback stored in database
- [ ] Email notification sent to admin
- [ ] Success/error handling in iOS app

---

### ICG-081: Add Send Feedback to Settings Menu
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Description:** Add "Send Feedback" option to Settings menu.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Settings menu includes "Send Feedback" option
- [ ] Tapping option navigates to FeedbackView
- [ ] Submission shows success confirmation

---

### ICG-082: Consolidate Email Validation
**Status:** [ ] Not Started
**Files:** `ViewModels/LoginViewModel.swift`, `ViewModels/RegistrationViewModel.swift`
**Description:** Use `String+Extensions.swift` consistently for email validation.
**Assignee(s):** ios-engineer, redundancy-detector
**Acceptance Criteria:**
- [ ] All email validation uses single implementation
- [ ] Validation logic identical across all call sites
- [ ] Unit tests verify validation consistency

---

### ICG-083: Consolidate Password Validation
**Status:** [ ] Not Started
**Files:** `ViewModels/LoginViewModel.swift`, `ViewModels/RegistrationViewModel.swift`
**Description:** Use `Validators.swift` or create shared validator for passwords.
**Assignee(s):** ios-engineer, redundancy-detector
**Acceptance Criteria:**
- [ ] All password validation uses single implementation
- [ ] Validation rules identical across all call sites
- [ ] Password requirements documented

---

### ICG-084: Extract IQ Score Classification to Shared Utility
**Status:** [ ] Not Started
**Files:** `Utilities/Helpers/IQScoreUtility.swift` (new), `Views/Test/TestResultsView.swift`, `Views/History/TestDetailView+Helpers.swift`, `AIQTests/Utilities/IQScoreUtilityTests.swift` (new)
**Description:** Create shared utility for IQ score classification and color mapping, then replace duplicate code.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] IQScoreUtility.swift created with classification method
- [ ] Method accepts IQ score, returns category and color
- [ ] TestResultsView uses IQScoreUtility
- [ ] TestDetailView+Helpers uses IQScoreUtility
- [ ] Duplicate switch statements removed
- [ ] Visual output identical to before
- [ ] Unit tests verify all score ranges

---

### ICG-085: Audit DateFormatter Usage
**Status:** [ ] Not Started
**Files:** Documentation only
**Description:** Identify all instances creating DateFormatters across codebase.
**Assignee(s):** ios-engineer, redundancy-detector
**Acceptance Criteria:**
- [ ] All DateFormatter usage documented
- [ ] Call sites categorized by format type
- [ ] Migration plan created

---

### ICG-086: Migrate to Date+Extensions Helpers
**Status:** [ ] Not Started
**Files:** `ViewModels/DashboardViewModel.swift`, `Views/Test/TestResultsView.swift`, `Views/History/IQTrendChart.swift`, others
**Description:** Replace formatter creation with Date+Extensions methods.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All DateFormatter creation replaced with extensions
- [ ] Date formatting consistent across app
- [ ] Performance improved (fewer formatter allocations)

---

### ICG-087: Create Reusable InfoCard Component
**Status:** [ ] Not Started
**Files:** `Views/Common/InfoCard.swift` (new)
**Description:** Extract common card pattern from WelcomeView and RegistrationView, then replace duplicates.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] InfoCard component supports title, description, icon
- [ ] Component supports customization (colors, sizing)
- [ ] Component previews created
- [ ] WelcomeView uses InfoCard (replaces FeatureCard)
- [ ] RegistrationView uses InfoCard (replaces RegistrationBenefitCard)
- [ ] Visual output identical to before

---

### ICG-088: Fix StateObject Misuse in DashboardView
**Status:** [ ] Not Started
**Files:** `Views/Dashboard/DashboardView.swift`
**Description:** Change @StateObject to @ObservedObject for singleton AuthManager.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] DashboardView uses @ObservedObject instead of @StateObject
- [ ] AuthManager.shared still works correctly
- [ ] No duplicate instances created

---

### ICG-089: Convert TokenRefreshInterceptor to Actor
**Status:** [ ] Not Started
**Files:** `Services/Auth/TokenRefreshInterceptor.swift`, `AIQTests/Network/TokenRefreshInterceptorConcurrencyTests.swift` (new)
**Description:** Eliminate race condition on concurrent requests by using Swift actor and verify thread safety.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] TokenRefreshInterceptor converted to Swift actor
- [ ] All properties accessed via async/await
- [ ] Compilation succeeds
- [ ] Stress test creates 10+ concurrent requests
- [ ] Token refresh only happens once during concurrent requests
- [ ] No race condition errors
- [ ] All requests succeed

---

### ICG-090: Fix Retain Cycle in DashboardViewModel
**Status:** [ ] Not Started
**Files:** `ViewModels/DashboardViewModel.swift`
**Description:** Add [weak self] to retry closure.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Retry closure uses [weak self]
- [ ] Memory leak resolved
- [ ] Functionality unchanged

---

### ICG-091: Audit Timer Closures for Retain Cycles
**Status:** [ ] Not Started
**Files:** Documentation only
**Description:** Search for Timer usage without weak self references.
**Assignee(s):** ios-engineer, code-reviewer
**Acceptance Criteria:**
- [ ] All Timer usage documented
- [ ] Retain cycle risks identified
- [ ] Priority fixes listed

---

### ICG-092: Fix Timer Retain Cycles
**Status:** [ ] Not Started
**Files:** Various ViewModel files
**Description:** Add [weak self] to all timer closures.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All timer closures use [weak self]
- [ ] No compiler warnings
- [ ] Functionality unchanged

---

### ICG-093: Run Memory Leak Detection
**Status:** [ ] Not Started
**Files:** Test only
**Description:** Use Xcode Instruments to verify no memory leaks.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Instruments Leaks tool run on app
- [ ] No memory leaks detected
- [ ] Memory graph verified clean

---

### ICG-094: Create Constants.swift File
**Status:** [ ] Not Started
**Files:** `Utilities/Helpers/Constants.swift` (new)
**Description:** Create constants file and extract magic numbers: timer critical threshold (60s), slow request threshold (2.0s), auto-save delay (1.0s), progress validity (24h).
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Constants.swift file created
- [ ] Organized into nested structs by domain (Timing, Network, Test)
- [ ] Documentation comments explain each constant
- [ ] Timer critical threshold (60s) extracted from TestTimerManager
- [ ] Slow request threshold (2.0s) extracted from APIClient
- [ ] Auto-save delay (1.0s) extracted from TestTakingViewModel
- [ ] Progress validity (24h) extracted from SavedTestProgress
- [ ] All references updated to use constants

---

### ICG-095: Audit Codebase for Additional Magic Numbers
**Status:** [ ] Not Started
**Files:** Documentation only
**Description:** Search for remaining magic numbers and categorize by priority.
**Assignee(s):** ios-engineer, code-reviewer
**Acceptance Criteria:**
- [ ] Full codebase search completed
- [ ] Magic numbers categorized by priority
- [ ] List of remaining numbers documented

---

### ICG-096: Extract Remaining Magic Numbers
**Status:** [ ] Not Started
**Files:** Various files, `Utilities/Helpers/Constants.swift`
**Description:** Extract all high-priority magic numbers to constants.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] All high-priority magic numbers extracted
- [ ] Constants well-named and documented
- [ ] Code maintainability improved

---

### ICG-097: Add Birth Year Validation
**Status:** [ ] Not Started
**Files:** `ViewModels/RegistrationViewModel.swift`
**Description:** Validate birth year is between 1900 and current year.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Birth year validation added to ViewModel
- [ ] Rejects years before 1900
- [ ] Rejects years after current year
- [ ] User-friendly error message displayed

---

### ICG-098: Create ServiceContainer for Dependency Injection
**Status:** [ ] Not Started
**Files:** `Utilities/DI/ServiceContainer.swift` (new), `AIQTests/DI/ServiceContainerTests.swift` (new)
**Description:** Create container for registering and resolving dependencies.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] ServiceContainer class created
- [ ] Supports registration and resolution of dependencies
- [ ] Thread-safe implementation
- [ ] Supports protocol-based injection
- [ ] Environment key created for SwiftUI injection
- [ ] Unit tests for registration and resolution

---

### ICG-099: Migrate ViewModels to Use ServiceContainer
**Status:** [ ] Not Started
**Files:** All ViewModels, `AIQApp.swift`
**Description:** Inject dependencies instead of using singletons directly.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] ServiceContainer initialized in AIQApp.swift
- [ ] All services registered
- [ ] Injected into environment
- [ ] All ViewModels accept dependencies via initializer
- [ ] No direct singleton usage in ViewModels
- [ ] Testability improved
- [ ] App launches successfully

---

### ICG-100: Create Offline Operation Queue
**Status:** [ ] Not Started
**Files:** `Services/Storage/OfflineOperationQueue.swift` (new), `AIQTests/Storage/OfflineOperationQueueTests.swift` (new)
**Description:** Queue profile updates and settings changes when offline with retry logic.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] OfflineOperationQueue created
- [ ] Supports queuing mutations when offline
- [ ] Persists queue to disk
- [ ] Failed operations retry with exponential backoff
- [ ] Max retry limit enforced
- [ ] Permanently failed operations reported to user
- [ ] Queue monitors network status
- [ ] Syncs operations when network returns
- [ ] Handles conflicts gracefully
- [ ] User notified of sync status
- [ ] Unit tests for queue, persist, and retry operations

---

### ICG-101: Create AppStateStorage for UI State Persistence
**Status:** [ ] Not Started
**Files:** `Services/Storage/AppStateStorage.swift` (new), `AIQTests/Storage/AppStateStorageTests.swift` (new)
**Description:** Persist UI state like tab selection and filter preferences.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] AppStateStorage created with UserDefaults backend
- [ ] Supports reading/writing various state types
- [ ] Type-safe API
- [ ] Unit tests for state read/write operations

---

### ICG-102: Persist Tab Selection Across App Launches
**Status:** [ ] Not Started
**Files:** `Views/MainTabView.swift`
**Description:** Save and restore selected tab on app launch.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Selected tab saved on change
- [ ] Restored on app launch
- [ ] Defaults to dashboard if no saved state

---

### ICG-103: Persist Filter Preferences in HistoryView
**Status:** [ ] Not Started
**Files:** `Views/History/HistoryView.swift`
**Description:** Save and restore filter selections.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Filter selections saved on change
- [ ] Restored on view appear
- [ ] Defaults to "All" if no saved state

---

### ICG-104: Persist Scroll Positions in Long Lists
**Status:** [ ] Not Started
**Files:** Various list views
**Description:** Save and restore scroll positions (nice-to-have).
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Scroll position saved for long lists
- [ ] Restored on view appear (if feasible with SwiftUI)
- [ ] Degrades gracefully if not possible

---

### ICG-105: Create BiometricAuthManager
**Status:** [ ] Not Started
**Files:** `Services/Auth/BiometricAuthManager.swift` (new)
**Description:** Add Face ID / Touch ID support with fallback to passcode.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] BiometricAuthManager supports Face ID and Touch ID
- [ ] Handles permission requests
- [ ] Fallback to passcode if biometric fails

---

### ICG-106: Add Biometric Authentication Option to Settings
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Description:** Add toggle for enabling/disabling biometric auth.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Settings toggle for biometric auth
- [ ] Disabled if device doesn't support biometrics
- [ ] Preference saved securely

---

### ICG-107: Implement Biometric Auth on App Launch
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Description:** Prompt for biometric auth when app launches if enabled.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Biometric prompt shown on app launch if enabled
- [ ] Successful auth shows app content
- [ ] Failed auth shows retry or exit options

---

### ICG-108: Create HapticManager
**Status:** [ ] Not Started
**Files:** `Utilities/Helpers/HapticManager.swift` (new)
**Description:** Create simple API for common haptic feedback types.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] HapticManager provides simple API for common feedback types
- [ ] Supports success, error, warning, selection
- [ ] Respects system haptic settings

---

### ICG-109: Add Haptic Feedback to Button Taps
**Status:** [ ] Not Started
**Files:** `Views/Common/PrimaryButton.swift`, others
**Description:** Add tactile feedback to button interactions.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Appropriate haptic feedback added
- [ ] Not overused (only meaningful interactions)
- [ ] Respects accessibility settings

---

### ICG-110: Add Haptic Feedback to Success/Error States
**Status:** [ ] Not Started
**Files:** All ViewModels
**Description:** Add tactile feedback for operation outcomes.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Appropriate haptic feedback added
- [ ] Not overused (only meaningful interactions)
- [ ] Respects accessibility settings

---

### ICG-111: Add Haptic Feedback to Timer Warnings
**Status:** [ ] Not Started
**Files:** `ViewModels/TestTimerManager.swift`
**Description:** Add tactile feedback when timer reaches warning threshold.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Appropriate haptic feedback added
- [ ] Not overused (only meaningful interactions)
- [ ] Respects accessibility settings

---

### ICG-112: Optimize Layouts for iPad
**Status:** [ ] Not Started
**Files:** All View files
**Description:** Create multi-column layouts for larger screens.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Layouts use adaptive sizing
- [ ] Multi-column layouts on larger screens
- [ ] No awkward stretching on iPad

---

### ICG-113: Add Keyboard Shortcuts for iPad
**Status:** [ ] Not Started
**Files:** Various views
**Description:** Add discoverable keyboard shortcuts for common actions.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Common actions have keyboard shortcuts (Cmd+N, Cmd+R, etc.)
- [ ] Shortcuts discoverable
- [ ] Don't conflict with system shortcuts

---

### ICG-114: Add Split View Support for iPad
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Description:** Support iPad multitasking split view mode.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] App supports split view multitasking
- [ ] Layouts adapt to narrow widths
- [ ] No crashes in split view

---

### ICG-115: Create Widget Extension
**Status:** [ ] Not Started
**Files:** Widget extension target (new)
**Description:** Show latest score or next test date on home screen widget.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Widget shows latest IQ score
- [ ] Widget shows days until next test
- [ ] Tapping widget opens app to relevant screen

---

### ICG-116: Add Snapshot Testing
**Status:** [ ] Not Started
**Files:** Snapshot test files (new)
**Description:** Add visual regression testing with swift-snapshot-testing.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Snapshot tests created for key views
- [ ] Tests run in CI/CD
- [ ] Failures detected on UI changes

---

### ICG-117: Add Background Refresh Capability
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`, `AppDelegate.swift`
**Description:** Fetch new data in background and notify user of updates.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Background refresh fetches new data
- [ ] User notified of updates if relevant
- [ ] Battery impact minimized

---

### ICG-118: Create SettingsViewModel for MVVM Compliance
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`, `ViewModels/SettingsViewModel.swift` (new)
**Description:** SettingsView currently violates MVVM architecture by directly accessing AuthManager.shared. Create a SettingsViewModel to handle business logic.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] SettingsViewModel created following project patterns
- [ ] AuthManager access moved to ViewModel
- [ ] Logout logic moved to ViewModel
- [ ] View testability improved
- [ ] Consistent with other ViewModels in codebase

---

### ICG-119: Document Direct Recording vs handleError Usage
**Status:** [ ] Not Started
**Files:** `ViewModels/BaseViewModel.swift`, `Utilities/Helpers/CrashlyticsErrorRecorder.swift`
**Description:** Need documentation clarifying when to use direct CrashlyticsErrorRecorder.recordError() calls vs going through BaseViewModel.handleError().
**Assignee(s):** ios-engineer, comment-analyzer
**Acceptance Criteria:**
- [ ] Add documentation to CrashlyticsErrorRecorder explaining usage patterns
- [ ] Add inline comments in DashboardViewModel explaining intentional silent failures
- [ ] Update BaseViewModel.handleError() documentation

---

### ICG-120: Remove Emojis from CrashlyticsErrorRecorder DEBUG Logging
**Status:** [ ] Not Started
**Files:** `Utilities/Helpers/CrashlyticsErrorRecorder.swift`
**Description:** The DEBUG print statements use emojis which is inconsistent with project conventions (per CLAUDE.md). Remove them for consistency.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Remove emojis from DEBUG print statements in CrashlyticsErrorRecorder
- [ ] Ensure console output remains readable without emojis

---

### ICG-121: Make ErrorContext Parameter Required (Remove Default)
**Status:** [ ] Not Started
**Files:** `ViewModels/BaseViewModel.swift`
**Description:** The default context parameter of .unknown reduces error categorization value. Consider making context required to encourage explicit categorization.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Remove default `.unknown` value from handleError context parameter
- [ ] Update all call sites to provide explicit context
- [ ] Ensure no regressions in error handling

---

### ICG-122: Add User Error Feedback for Deep Links
**Status:** [ ] Not Started
**Source:** PR #384 comment
**Files:** `Services/Navigation/DeepLinkHandler.swift`, `AIQApp.swift` or `AppDelegate.swift`
**Description:** When ICG-016 integrates DeepLinkHandler into AppDelegate, add a mechanism to inform users why a deep link failed (e.g., toast notification or alert).
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Design error feedback mechanism (toast, alert, or inline message)
- [ ] Implement error feedback UI component
- [ ] Connect DeepLinkHandler failures to error feedback display
- [ ] Test with various invalid deep links

---

### ICG-123: Add Warning for Extra Path Components in Deep Links
**Status:** [ ] Not Started
**Source:** PR #384 comment
**Files:** `Services/Navigation/DeepLinkHandler.swift`
**Description:** Currently, extra path components are silently ignored (e.g., aiq://test/results/123/extra parses as test results with ID 123). Consider logging a warning when extra components are present.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add logging warning when extra path components detected
- [ ] Document expected behavior in code comments
- [ ] Consider if strict mode should reject extra components

---

### ICG-124: Add Deep Link Analytics Tracking
**Status:** [ ] Not Started
**Source:** PR #384 comment
**Files:** `Services/Navigation/DeepLinkHandler.swift`, `Services/Analytics/AnalyticsService.swift`
**Description:** Track deep link usage metrics to understand user behavior and detect broken marketing campaign links.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Track successful deep link navigations with destination type
- [ ] Track failed deep link attempts with error type
- [ ] Include source information (push notification, external app, Safari)
- [ ] Analytics events visible in backend dashboard

---

### ICG-125: Add Development Domain for Universal Links Testing
**Status:** [ ] Not Started
**Source:** PR #386 comment
**Files:** `ios/AIQ/AIQ.entitlements`
**Description:** Add `applinks:dev.aiq.app` or similar development domain to enable universal link testing in staging environments without affecting production.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Development domain added to Associated Domains entitlement
- [ ] Corresponding apple-app-site-association file deployed to dev server
- [ ] Universal links testable in staging environment

---

### ICG-126: Document Universal Links Configuration in iOS README
**Status:** [ ] Not Started
**Source:** PR #386 comment
**Files:** `ios/README.md`
**Description:** Add documentation about universal links setup including entitlement configuration, Apple Developer Portal requirements, and server-side apple-app-site-association file.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] README documents Associated Domains entitlement
- [ ] README explains Apple Developer Portal configuration steps
- [ ] README includes server-side configuration requirements
- [ ] README includes troubleshooting tips

---

### ICG-127: Create Universal Links Validation Script
**Status:** [ ] Not Started
**Source:** PR #386 comment
**Files:** `scripts/validate-universal-links.sh` (new)
**Description:** Create a script to validate that the apple-app-site-association file is properly deployed and accessible at https://aiq.app/.well-known/apple-app-site-association.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Script fetches apple-app-site-association from production URL
- [ ] Script validates JSON structure
- [ ] Script verifies appID matches expected Team ID and bundle ID
- [ ] Script provides clear pass/fail output
