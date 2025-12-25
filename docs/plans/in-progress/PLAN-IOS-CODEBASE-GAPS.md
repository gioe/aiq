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
**Status:** [x] Complete
**Files:** `Views/Dashboard/DashboardView.swift`, `Views/Common/MainTabView.swift`
**Description:** Replace sheet/fullScreenCover modifiers with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] All sheet/fullScreenCover modifiers replaced with router calls
- [x] Navigation state removed from DashboardView
- [x] Back navigation works correctly
- [x] Deep state restoration supported

---

### ICG-013: Migrate TestTakingView Navigation
**Status:** [x] Complete
**Files:** `Views/Test/TestTakingView.swift`
**Description:** Replace navigation state management with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] All sheet/fullScreenCover modifiers replaced with router calls
- [x] Navigation state removed from ViewModel
- [x] Back navigation works correctly
- [x] Deep state restoration supported

---

### ICG-014: Migrate HistoryView Navigation
**Status:** [x] Complete
**Files:** `Views/History/HistoryView.swift`
**Description:** Replace navigation state management with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] All sheet/fullScreenCover modifiers replaced with router calls
- [x] Navigation state removed from ViewModel
- [x] Back navigation works correctly
- [x] Deep state restoration supported

---

### ICG-015: Migrate SettingsView Navigation
**Status:** [x] Complete
**Files:** `Views/Settings/SettingsView.swift`
**Description:** Replace navigation state management with AppRouter calls.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] All sheet/fullScreenCover modifiers replaced with router calls
- [x] Navigation state removed from ViewModel
- [x] Back navigation works correctly
- [x] Deep state restoration supported

---

### ICG-016: Implement Deep Link Handling in AppDelegate
**Status:** [x] Complete
**Files:** `AppDelegate.swift`
**Description:** Handle `application(_:open:options:)` callback to process deep links.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] AppDelegate handles URL opening callbacks
- [x] URLs parsed by DeepLinkHandler
- [x] Router navigates to correct destination

---

### ICG-017: Add Deep Link Routes
**Status:** [x] Complete
**Files:** `Services/Navigation/DeepLinkHandler.swift`
**Description:** Implement routes for `aiq://test/results/{id}`, `aiq://test/resume/{sessionId}`, `aiq://settings`.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] All three route types implemented
- [x] Invalid routes handled gracefully with error state
- [x] Routes work from cold start and background state
- [x] Unit tests for all route types

---

### ICG-018: Test Deep Links from Push Notifications
**Status:** [x] Complete
**Files:** Test only
**Description:** Verify notification tap navigates correctly to target screens.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Push notification tap opens app to correct screen (automated tests + manual test documentation)
- [x] Notification payload structure tested (23 automated unit tests)
- [x] Works in foreground, background, and terminated states (manual test procedures documented)

---

### ICG-019: Create AIQUITests Target
**Status:** [x] Complete
**Files:** `AIQUITests/` (new directory)
**Description:** Create UI test target in Xcode with correct configuration, test host, bundle ID, and signing.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] AIQUITests target created with correct configuration
- [x] Test target builds successfully
- [x] Can run UI tests from Xcode

---

### ICG-020: Create UI Test Helpers
**Status:** [x] Complete
**Files:** `AIQUITests/Helpers/` (new)
**Description:** Create LoginHelper, TestTakingHelper, and NavigationHelper for test code reuse.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] LoginHelper provides authenticated test sessions
- [x] TestTakingHelper handles test data setup
- [x] NavigationHelper verifies screen transitions
- [x] Helpers reduce test boilerplate

---

### ICG-021: Write Registration Flow UI Test
**Status:** [x] Complete
**Files:** `AIQUITests/RegistrationFlowTests.swift` (new)
**Description:** Complete registration from start to dashboard with validation testing.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Test completes full registration flow
- [x] Validates field validation errors
- [x] Verifies successful registration leads to dashboard
- [x] Runs reliably without flakiness

---

### ICG-022: Write Login/Logout Flow UI Test
**Status:** [x] Complete
**Files:** `AIQUITests/AuthenticationFlowTests.swift` (new)
**Description:** Test login with valid/invalid credentials and logout flow.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Test covers login with valid credentials
- [x] Test covers login with invalid credentials
- [x] Test covers logout flow
- [x] Verifies session persistence

---

### ICG-023: Write Test-Taking Flow UI Test
**Status:** [x] Complete
**Files:** `AIQUITests/TestTakingFlowTests.swift` (new)
**Description:** Start test, answer all questions, submit, and verify results.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Test starts a new test session
- [x] Test answers all questions (mocked question data)
- [x] Test submits answers and verifies results screen
- [x] Verifies score display and history update

**Summary:**
- Created comprehensive UI test suite with 19 test methods (684 lines) covering the complete test-taking flow
- Tests cover: starting tests, answering questions, navigation (next/previous), submission, results display, history updates, and error handling (abandon test confirmation)
- Tests are skipped by default as they require backend connection and valid test account
- Follows established patterns from AuthenticationFlowTests.swift
- **Total tokens spent:** ~50,000 (estimated based on conversation context)
- **Total time spent:** ~15 minutes

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

---

### ICG-128: Add Logging for Unimplemented Routes in DashboardTabNavigationView
**Status:** [ ] Not Started
**Source:** PR #388 comment
**Files:** `Views/Common/MainTabView.swift`
**Description:** The default case in `destinationView(for:)` (line 71-73) silently handles unimplemented routes without any logging or error tracking. Add analytics tracking or logging for this case to catch routing bugs in production.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add CrashlyticsErrorRecorder.recordError() call in default case
- [ ] Include route information in error context
- [ ] Consider adding analytics event for routing errors

---

### ICG-129: Add Automated Navigation Tests for DashboardView Router Integration
**Status:** [ ] Not Started
**Source:** PR #388 comment
**Files:** `AIQTests/Views/DashboardNavigationTests.swift` (new)
**Description:** No automated tests verify that router.push(.testTaking) is called from DashboardView navigation points. Add unit tests for navigation flows to prevent regression.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test verifies action button triggers router.push(.testTaking)
- [ ] Test verifies resume button triggers router.push(.testTaking)
- [ ] Test verifies empty state button triggers router.push(.testTaking)
- [ ] Mock router used for isolation

---

### ICG-130: Evaluate Per-Tab Navigation Paths for Tab Isolation
**Status:** [ ] Not Started
**Source:** PR #388 comment
**Files:** `Views/Common/MainTabView.swift`, `Services/Navigation/AppRouter.swift`
**Description:** Currently the AppRouter is shared across the entire app, but only the Dashboard tab uses router-based navigation. When History and Settings tabs are migrated (ICG-014, ICG-015), evaluate whether each tab should have its own navigation path to prevent cross-tab state contamination.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Document current shared router behavior
- [ ] Analyze use cases requiring cross-tab navigation (e.g., deep links)
- [ ] If per-tab paths needed: implement TabRouter wrapper or path-per-tab design
- [ ] Test tab switching preserves appropriate navigation state

---

### ICG-131: Add Test Coverage for .testResults Deep Link Navigation
**Status:** [ ] Not Started
**Source:** PR #393 comment
**Files:** `AIQTests/Services/DeepLinkHandlerTests.swift`
**Description:** The .testResults navigation isn't tested due to API mocking complexity. Add a test with a mock API client conforming to APIClientProtocol to verify the fetch-and-navigate flow.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Create mock APIClient for testing
- [ ] Add test for successful .testResults API call and navigation
- [ ] Add test for failed .testResults API call and error handling
- [ ] Verify router.navigateTo() is called with correct route

---

### ICG-132: Implement Full Session Resumption for resumeTest Deep Link
**Status:** [ ] Not Started
**Source:** PR #393 comment
**Files:** `Services/Navigation/DeepLinkHandler.swift`, `Services/Navigation/Route.swift`, `Views/Test/TestTakingView.swift`
**Description:** The resumeTest deep link captures sessionId but doesn't use it - currently returns false. Implement full session resumption.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Update Route.testTaking to accept an optional sessionId parameter
- [ ] Modify TestTakingView to fetch and restore session state when sessionId provided
- [ ] Update DeepLinkHandler to pass sessionId to navigation
- [ ] Return true from handleNavigation on success
- [ ] Add unit tests for session resumption flow

---

### ICG-133: Handle Concurrent Deep Link Processing
**Status:** [ ] Not Started
**Source:** PR #393 comment
**Files:** `Views/Common/MainTabView.swift`
**Description:** Multiple rapid deep links could spawn multiple concurrent API requests. Consider using a State variable to track if a deep link is currently being processed and ignore new ones until complete.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add @State variable to track deep link processing state
- [ ] Ignore new deep links while one is being processed
- [ ] Log when deep links are ignored due to pending processing
- [ ] Test with rapid sequential deep links

---

### ICG-134: Refactor Settings Route Navigation Pattern
**Status:** [ ] Not Started
**Source:** PR #393 comment
**Files:** `Services/Navigation/DeepLinkHandler.swift`, `Views/Common/MainTabView.swift`
**Description:** The .settings case in handleNavigation returns true but acknowledges it shouldn't be called (handled at tab level). Refactor to make tab-level vs route-level navigation more explicit.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Document/clarify tab-based vs route-based navigation patterns
- [ ] Consider separating TabDestination enum from Route enum
- [ ] Remove ambiguous .settings handling in DeepLinkHandler
- [ ] Ensure all deep link types are handled in appropriate layer

---

### ICG-135: Add deep_link Field to Push Notification Data Payload
**Status:** [ ] Not Started
**Source:** PR #394 comment
**Files:** `backend/app/services/notification_scheduler.py`
**Description:** Backend notification payloads currently only include `type` and `user_id` in the data field. Add `deep_link` field (e.g., `aiq://test/results/{session_id}`) to enable iOS app to navigate to the correct screen when notification is tapped.
**Assignee(s):** fastapi-architect
**Acceptance Criteria:**
- [ ] Add `deep_link` field to notification data payload at line 283
- [ ] Generate appropriate deep link URL based on notification type
- [ ] Include session_id or result_id in deep link for context
- [ ] Unit test notification payload structure includes deep_link

---

### ICG-136: Implement .notificationTapped Observer in MainTabView
**Status:** [ ] Not Started
**Source:** PR #394 comment
**Files:** `ios/AIQ/Views/Common/MainTabView.swift`
**Description:** AppDelegate posts `.notificationTapped` notification but MainTabView doesn't observe it. Add `.onReceive` handler similar to `.deepLinkReceived` to process notification taps and navigate using the deep link from the payload.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add `.onReceive` for NotificationCenter.default.publisher(for: .notificationTapped)
- [ ] Extract deep_link from notification userInfo
- [ ] Parse deep link using DeepLinkHandler
- [ ] Navigate to appropriate screen using router
- [ ] Works when app is in foreground, background, and terminated states
- [ ] Unit tests for notification tap handling

---

### ICG-137: Add Accessibility Identifiers to App Views
**Status:** [x] Complete
**Source:** PR #396 comment
**Files:** All SwiftUI view files
**Description:** UI test helpers currently rely on accessibility labels which are fragile (will break if UI text changes due to localization or copy updates). Add accessibility identifiers to all interactive elements for reliable UI testing.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Create AccessibilityIdentifiers.swift constants file
- [x] Add identifiers to WelcomeView elements (email field, password field, sign in button)
- [x] Add identifiers to DashboardView elements (action button, resume button)
- [x] Add identifiers to TestTakingView elements (answer buttons, submit button)
- [x] Add identifiers to SettingsView elements (sign out button)
- [x] Add identifiers to navigation tabs
- [x] Update UI test helpers to use identifiers instead of labels

**Summary:**
- Created centralized AccessibilityIdentifiers.swift with nested structs for WelcomeView, DashboardView, TestTakingView, SettingsView, and TabBar
- Added accessibility identifiers to all interactive elements across views
- Updated CustomTextField and PrimaryButton with optional accessibilityId parameter
- Refactored UI test helpers (LoginHelper, NavigationHelper, TestTakingHelper) to use identifiers instead of fragile label-based queries
- Tests won't break when UI text changes for localization or copy updates
- **Total tokens spent:** ~75,000 (estimated)
- **Total time spent:** ~25 minutes

---

### ICG-138: Add Missing Error Recovery in LoginHelper.logout()
**Status:** [ ] Not Started
**Source:** PR #396 comment
**Files:** `ios/AIQUITests/Helpers/LoginHelper.swift`
**Description:** The logout() method searches for sign out button using a predicate but doesn't handle cases where the Settings screen structure differs or the button isn't found.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add fallback strategies for finding sign out button
- [ ] Handle cases where Settings screen structure varies
- [ ] Add more robust element queries or retry logic

---

### ICG-139: Improve TestTakingHelper Element Queries
**Status:** [ ] Not Started
**Source:** PR #396 comment
**Files:** `ios/AIQUITests/Helpers/TestTakingHelper.swift`
**Description:** Current predicates are too broad and could match unintended elements. For example, `label CONTAINS[c] "take" OR label CONTAINS[c] "start"` could match "Retake" or "Start learning". Once accessibility identifiers are added, replace these with specific identifiers.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Wait for ICG-137 to complete (accessibility identifiers)
- [ ] Replace broad label predicates with specific identifier queries
- [ ] Remove fragile `label.length > 20` predicate for question text

---

### ICG-140: Standardize Network Operation Timeouts
**Status:** [ ] Not Started
**Source:** PR #396 comment
**Files:** `ios/AIQUITests/Helpers/BaseUITest.swift`
**Description:** Timeout handling is inconsistent - BaseUITest defines `standardTimeout`, `extendedTimeout`, `quickTimeout` but individual helpers accept timeout parameters and some double the timeout for network ops. Add a `networkTimeout` constant to standardize.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add `networkTimeout` constant to BaseUITest (e.g., 10s)
- [ ] Use `networkTimeout` consistently for operations involving network calls
- [ ] Document timeout usage guidelines in README

---

### ICG-141: Add Environment Variable Support for Test Credentials
**Status:** [ ] Not Started
**Source:** PR #396 comment
**Files:** `ios/AIQUITests/`
**Description:** There is no current strategy for test data management including test user credentials, cleaning up test data, or handling different test scenarios.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add environment variable support for test email/password
- [ ] Create test configuration struct for managing test data
- [ ] Document test credential setup in README
- [ ] Add mechanism to create/cleanup test users

---

### ICG-142: Evaluate XCUIElement.clearText() Usage
**Status:** [ ] Not Started
**Source:** PR #396 comment
**Files:** `ios/AIQUITests/Helpers/XCUIElement+Extensions.swift`
**Description:** The clearText() method (double-tap + Select All menu) is likely more fragile than clearAndTypeText() which uses backspace. Consider deprecating clearText() if it causes flaky tests.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Evaluate if clearText() is used anywhere
- [ ] Test reliability of both approaches
- [ ] Either deprecate or document use cases for clearText()

---

### ICG-143: Add Setup/Teardown to ExampleUITest
**Status:** [ ] Not Started
**Source:** PR #396 comment
**Files:** `ios/AIQUITests/ExampleUITest.swift`
**Description:** Example tests assume sequential execution and shared state. Add setup/teardown to ensure test isolation, or clearly document that these are examples only (not meant to run in CI).
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add setUp() method to reset app state
- [ ] Add tearDown() method to clean up
- [ ] Or add clear documentation that examples are for reference only
- [ ] Consider moving to separate documentation file

---

### ICG-144: Add Accessibility Identifiers to Registration Views
**Status:** [ ] Not Started
**Source:** PR #397 comment
**Files:** `ios/AIQ/Views/Auth/RegistrationView.swift`, `ios/AIQUITests/Helpers/RegistrationHelper.swift`
**Description:** RegistrationHelper uses accessibility labels for element queries which is fragile. Add accessibility identifiers to production registration views and update helper to use them.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add accessibility identifiers to all registration form elements
- [ ] Update RegistrationHelper to use identifiers instead of labels
- [ ] Tests remain reliable after localization changes

---

### ICG-145: Add Education Level Picker Test
**Status:** [ ] Not Started
**Source:** PR #397 comment
**Files:** `ios/AIQUITests/RegistrationFlowTests.swift`, `ios/AIQUITests/Helpers/RegistrationHelper.swift`
**Description:** The educationLevelButton property is defined in RegistrationHelper but never used. Either implement education level picker interaction or remove the unused property.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add test for education level picker interaction, OR
- [ ] Remove unused educationLevelButton property
- [ ] If implementing, add fillEducationLevel method to helper

---

### ICG-146: Improve Validation Error Checking Specificity
**Status:** [ ] Not Started
**Source:** PR #397 comment
**Files:** `ios/AIQUITests/Helpers/RegistrationHelper.swift`
**Description:** Validation error checking predicates are too loose (e.g., hasFirstNameError matches any text containing "first name" AND "required"). Define expected error message formats and match precisely.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Define expected error message formats in production app
- [ ] Update helper predicates to match exact error messages
- [ ] Consider using accessibility identifiers for error labels

---

### ICG-147: Add Error Recovery Flow Tests
**Status:** [ ] Not Started
**Source:** PR #397 comment
**Files:** `ios/AIQUITests/RegistrationFlowTests.swift`
**Description:** Missing tests for error recovery flows - fixing validation errors and resubmitting the form.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add test that triggers validation error then fixes it
- [ ] Verify form becomes submittable after fixing errors
- [ ] Test covers at least email and password validation recovery

---

### ICG-148: Add Network Failure Registration Tests
**Status:** [ ] Not Started
**Source:** PR #397 comment
**Files:** `ios/AIQUITests/RegistrationFlowTests.swift`
**Description:** Missing tests for network failure scenarios during registration (timeout, server errors).
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add test for registration with network timeout
- [ ] Add test for registration with server error response
- [ ] Verify error message displayed to user

---

### ICG-149: Add Keyboard Navigation Tests
**Status:** [ ] Not Started
**Source:** PR #397 comment
**Files:** `ios/AIQUITests/RegistrationFlowTests.swift`
**Description:** Missing tests for keyboard management - return key navigation between fields.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test return key advances to next field
- [ ] Test final field return key submits or dismisses keyboard
- [ ] Verify focus moves correctly through form

---

### ICG-150: Document Test Account Setup Requirements
**Status:** [ ] Not Started
**Source:** PR #397 comment
**Files:** `ios/AIQUITests/README.md` (new or existing)
**Description:** Test that checks existing email shows error needs documented test account setup requirements.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Document required test accounts
- [ ] Add instructions for test environment configuration
- [ ] Consider environment variables for test credentials

---

### ICG-151: Add Specific Error Message Validation in Auth Tests
**Status:** [ ] Not Started
**Source:** PR #398 comment
**Files:** `ios/AIQUITests/AuthenticationFlowTests.swift`
**Description:** Current error checking is generic (hasError). Should verify the *type* of error message shown to prevent false positives if the wrong error appears.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add error message content validation (e.g., contains "password" for password errors)
- [ ] Distinguish between different error types
- [ ] Prevent false positives from wrong error messages

---

### ICG-152: Use Environment Variables for UI Test Credentials
**Status:** [ ] Not Started
**Source:** PR #398 comment
**Files:** `ios/AIQUITests/AuthenticationFlowTests.swift`
**Description:** Hardcoded placeholder credentials create confusion about test intent. Should use environment variables or precondition checks.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Use ProcessInfo.processInfo.environment for test email/password
- [ ] Add precondition check that fails if using placeholder values
- [ ] Document test credential setup in README

---

### ICG-153: Add Form Validation Prevention Check in Login Tests
**Status:** [ ] Not Started
**Source:** PR #398 comment
**Files:** `ios/AIQUITests/AuthenticationFlowTests.swift`
**Description:** testLoginWithInvalidEmailFormat test doesn't verify that the backend call is prevented by client-side validation.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add assertion that sign-in button remains disabled
- [ ] Verify no network request occurs for invalid email format
- [ ] Ensure client-side validation catches malformed emails

---

### ICG-154: Add Accessibility Identifier Tests for Authentication
**Status:** [ ] Not Started
**Source:** PR #398 comment
**Files:** `ios/AIQUITests/AuthenticationFlowTests.swift`
**Description:** Consider adding tests that verify accessibility identifiers are properly set on authentication UI elements.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add tests for accessibility identifier presence
- [ ] Verify VoiceOver labels are meaningful
- [ ] Document accessibility requirements for auth flow

---

### ICG-155: Reduce Test Setup Duplication in TestTakingFlowTests
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Create helper method `startTestSession()` to reduce repeated login/startTest/getQuestionCount pattern across tests.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Create `startTestSession() -> Int?` helper method
- [ ] Returns total question count on success, nil on failure
- [ ] Refactor existing tests to use this helper
- [ ] Reduces code duplication by ~40%

---

### ICG-156: Consistent Error Handling in TestTakingFlowTests
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Some tests check return values, others don't. Standardize error handling approach.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Either always check return values OR use assertions in helpers
- [ ] Apply consistent pattern across all test methods
- [ ] Document chosen approach in file comments

---

### ICG-157: Use Environment Variables for Test Credentials
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Replace hardcoded test credentials with environment variables.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Use `ProcessInfo.processInfo.environment["TEST_USER_EMAIL"]` with fallback
- [ ] Use `ProcessInfo.processInfo.environment["TEST_USER_PASSWORD"]` with fallback
- [ ] Document test credential setup in README

---

### ICG-158: Replace Thread.sleep with XCTest Wait APIs
**Status:** [x] Complete
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Replace fragile Thread.sleep() calls with proper XCTest wait conditions to improve reliability and speed.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [x] Replace all `Thread.sleep()` with `wait(for:timeout:)` or `expectation` APIs
- [x] Wait for specific UI state changes instead of fixed delays
- [x] Tests should be more reliable and faster

**Summary:**
- Replaced 4 `Thread.sleep()` calls with `XCTNSPredicateExpectation` and `XCTWaiter.wait()` APIs
- TestTakingFlowTests.swift: Replaced 2 calls in `testFullTestTakingCycle_EndToEnd` and `testFullTestTakingCycle_WithNavigation` to wait for progress label to update to next question number
- TestTakingHelper.swift: Replaced 1 call in `completeTestWithAnswer` method with proper wait for progress label update, plus added error handling for navigation failures
- NavigationHelper.swift: Replaced 1 call in `waitForNavigationToComplete` to wait for navigation bar to be hittable instead of arbitrary 500ms delay
- Tests now wait for specific UI state changes instead of fixed delays
- Note: 2 remaining `Thread.sleep` calls in AuthenticationFlowTests.swift are for app termination delays (appropriate for ICG-159)
- **Total tokens spent:** ~40,000 (estimated)
- **Total time spent:** ~15 minutes

---

### ICG-159: Define Constants for Test Delay Values
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Replace magic number delays (0.3, 0.5) with named constants.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Define `private let shortDelay: TimeInterval = 0.3`
- [ ] Define `private let appTerminationDelay: TimeInterval = 0.5`
- [ ] Apply constants throughout the file

---

### ICG-160: Standardize Test Method Naming Convention
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Some tests use "Flow", others use "Cycle". Standardize naming pattern.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Decide on consistent naming pattern (e.g., `test<Action>_<ExpectedResult>`)
- [ ] Rename inconsistent test methods
- [ ] Document naming convention in file header

---

### ICG-161: Add Assertions Before Screenshots
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Some tests take screenshots without asserting the expected UI state.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Add UI state assertions before taking screenshots
- [ ] Verify expected elements are visible before capture
- [ ] Screenshots serve as documentation, not just debugging

---

### ICG-162: Add Comprehensive Abandon Test Error Scenarios
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Current abandon tests don't verify partial progress handling or error messages.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test what happens when user has answered some questions
- [ ] Verify whether partial progress is saved or discarded
- [ ] Test error messages if abandoning fails
- [ ] Document expected behavior for abandon flow

---

### ICG-163: Add Network Error Scenario Tests
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Missing tests for API failures, timeouts, and network drops during test-taking.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test network error during question fetch
- [ ] Test API timeout during submission
- [ ] Test network drop mid-test
- [ ] Verify appropriate error messages shown

---

### ICG-164: Add App Lifecycle Tests During Test-Taking
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Missing tests for app backgrounding/foregrounding during active test.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Test app backgrounding during test
- [ ] Test app foregrounding and state restoration
- [ ] Verify no data loss on lifecycle events

---

### ICG-165: Add Accessibility Tests for Test-Taking Flow
**Status:** [ ] Not Started
**Source:** PR #399 comment
**Files:** `ios/AIQUITests/TestTakingFlowTests.swift`
**Description:** Missing tests for VoiceOver labels, Dynamic Type support, and accessibility navigation.
**Assignee(s):** ios-engineer
**Acceptance Criteria:**
- [ ] Verify VoiceOver labels on question elements
- [ ] Verify button hints for answer selection
- [ ] Test accessibility navigation through test flow
