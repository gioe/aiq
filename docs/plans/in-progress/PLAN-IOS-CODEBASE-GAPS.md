# iOS Codebase Gaps - Implementation Plan

## Overview

This plan addresses 32 identified gaps in the AIQ iOS application across architecture, testing, security, and production readiness. The work is organized into four priority tiers (P0-P3) and sequenced to de-risk critical blockers first while building toward App Store submission readiness.

## Strategic Context

### Problem Statement

The AIQ iOS application has a solid MVVM foundation and protocol-oriented architecture, but lacks critical production infrastructure (crash reporting, deep linking, UI testing), has security vulnerabilities (sensitive data logging, no certificate pinning), and contains code quality issues (redundancy, magic numbers, potential memory leaks) that must be resolved before App Store submission.

### Success Criteria

1. **Production Ready**: Crash reporting active, analytics backend integrated, no critical bugs
2. **Navigable**: Deep links functional for all notification types and user flows
3. **Testable**: 80% code coverage achieved, all critical user flows covered by UI tests
4. **Secure**: Certificate pinning enabled, zero sensitive data logged in production builds
5. **Accessible**: WCAG AA compliant, VoiceOver tested across all core flows
6. **Compliant**: Privacy policy published, privacy manifest included, consent management implemented
7. **Clean**: Code redundancy eliminated, magic numbers extracted to named constants

### Why Now?

App Store submission is blocked until P0 items are complete. The current state exposes security vulnerabilities, provides no visibility into production issues, and delivers a suboptimal user experience due to missing navigation infrastructure and accessibility gaps.

## Technical Approach

### High-Level Architecture Changes

**Navigation Layer:**
- Introduce centralized `AppRouter` using SwiftUI `NavigationPath`
- Implement `DeepLinkHandler` to parse and route URL schemes and universal links
- Migrate scattered `@State` navigation variables to router-based navigation

**Production Infrastructure:**
- Integrate Firebase Crashlytics for crash reporting and error monitoring
- Connect existing `AnalyticsService` to backend analytics endpoint
- Implement certificate pinning using TrustKit for SSL security

**Testing Infrastructure:**
- Create `AIQUITests` target with XCTest framework
- Build test helpers for authentication, navigation, and test-taking flows
- Achieve 80% code coverage through unit and UI tests

**Security Hardening:**
- Wrap all sensitive logging in `#if DEBUG` compiler guards
- Implement SSL certificate pinning with TrustKit
- Add privacy manifest (PrivacyInfo.xcprivacy)

### Key Decisions & Tradeoffs

**Decision 1: Firebase Crashlytics vs Sentry**
- **Choice**: Firebase Crashlytics
- **Rationale**: Better iOS integration, free tier sufficient, easier APNs integration
- **Tradeoff**: Vendor lock-in to Google ecosystem, but migration path exists if needed

**Decision 2: TrustKit for Certificate Pinning**
- **Choice**: TrustKit library
- **Rationale**: Industry-standard, well-maintained, handles pin rotation gracefully
- **Alternative**: Manual pinning rejected due to complexity and error-proneness

**Decision 3: NavigationPath vs Custom Router**
- **Choice**: SwiftUI NavigationPath with coordinator pattern
- **Rationale**: Native SwiftUI approach, less boilerplate, better integration
- **Tradeoff**: Requires iOS 16+ (already our minimum target)

**Decision 4: Phased Code Quality Fixes**
- **Choice**: P2 priority for redundancy elimination
- **Rationale**: Critical bugs and infrastructure take precedence, but code quality must be addressed before launch
- **Sequence**: Fix blockers first, then clean up technical debt

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Deep linking breaks existing navigation | High | Incremental migration, feature flags for rollback |
| Certificate pinning blocks dev/staging | Medium | Environment-specific config, pin only production |
| UI tests flaky on CI/CD | Medium | Implement retry logic, deterministic test data |
| Accessibility audit reveals major issues | High | Early audit in Phase 1, buffer time for fixes |
| Privacy policy delays submission | Critical | Parallel legal review during technical work |

---

## Implementation Plan

---

## Phase 0: Critical Bug Fixes (Immediate)

**Goal**: Eliminate production-breaking bugs before any other work

---

### ICG-001: Fix AppConfig URL Bug
**Status:** [x] Complete
**Files:** `Utilities/Helpers/AppConfig.swift`
**Description:** Remove `/v1` from base URL to prevent double path segments. The API endpoints already include `/v1` in their paths, so having it in the base URL causes double path segments.
**Acceptance Criteria:**
- [x] Base URL changed from `https://aiq-backend-production.up.railway.app/v1` to `https://aiq-backend-production.up.railway.app`
- [x] All API endpoints tested and working (login, registration, test start, test submit)
- [x] No breaking changes to existing API calls

---

## Phase 1: Production Infrastructure

**Goal**: Establish crash reporting and analytics backend integration for production visibility

---

### ICG-002: Integrate Firebase Crashlytics SDK
**Status:** [x] Complete
**Files:** `AIQApp.swift`, `Package.swift`
**Dependencies:** ICG-001
**Description:** Add Firebase Crashlytics via Swift Package Manager, initialize in app launch, and test crash reporting functionality.
**Acceptance Criteria:**
- [x] Firebase SDK integrated via Swift Package Manager
- [x] Crashlytics initialized in app launch
- [x] Test crash successfully reported to Firebase console

---

### ICG-003: Create Firebase Project and Configure iOS App
**Status:** [x] Complete
**Files:** `GoogleService-Info.plist` (new)
**Dependencies:** ICG-002
**Description:** Create Firebase project, download GoogleService-Info.plist, and configure APNs certificates.
**Acceptance Criteria:**
- [x] Firebase project created with iOS app configuration
- [x] GoogleService-Info.plist added to Xcode project
- [x] Build succeeds with Firebase integration

---

### ICG-004: Update AnalyticsService for Backend Integration
**Status:** [x] Complete
**Files:** `Services/Analytics/AnalyticsService.swift`
**Dependencies:** ICG-001
**Description:** Update AnalyticsService to send events to backend `/v1/analytics/events` endpoint.
**Acceptance Criteria:**
- [x] AnalyticsService sends events to backend API
- [x] Event payloads match backend schema
- [x] Network errors handled gracefully with retry logic
- [x] Events logged locally if offline (queue for later sync)

---

### ICG-005: Add Crashlytics Logging to ViewModels
**Status:** [x] Complete
**Files:** All ViewModels, `Utilities/Helpers/CrashlyticsErrorRecorder.swift` (new)
**Dependencies:** ICG-002, ICG-003
**Description:** Replace OSLog with Crashlytics.recordError() in catch blocks across all ViewModel error handlers.
**Acceptance Criteria:**
- [x] All ViewModel error handlers record non-fatal errors to Crashlytics
- [x] User-facing errors still logged to OSLog for debugging
- [x] No duplicate error logging

---

### ICG-006: Test Crash Reporting in TestFlight
**Status:** [ ] Not Started
**Files:** Test only
**Dependencies:** ICG-002, ICG-003, ICG-005
**Description:** Force crash in TestFlight build and verify it appears in Firebase console.
**Acceptance Criteria:**
- [ ] TestFlight build uploaded with Crashlytics enabled
- [ ] Forced crash appears in Firebase console within 5 minutes
- [ ] Crash report includes stack trace and device metadata

---

## Phase 2: Deep Linking & Navigation

**Goal**: Implement centralized navigation and deep linking to enable notification-driven user flows

---

### ICG-007: Create AppRouter with NavigationPath
**Status:** [ ] Not Started
**Files:** `Services/Navigation/AppRouter.swift` (new)
**Dependencies:** None
**Description:** Create AppRouter class with NavigationPath-based coordinator pattern for centralized navigation management.
**Acceptance Criteria:**
- [ ] AppRouter class created with NavigationPath state management
- [ ] Router supports push, pop, popToRoot, and direct navigation methods
- [ ] Router is observable and injectable via environment

---

### ICG-008: Create DeepLinkHandler
**Status:** [ ] Not Started
**Files:** `Services/Navigation/DeepLinkHandler.swift` (new)
**Dependencies:** None
**Description:** Create DeepLinkHandler to parse URL schemes and universal links into structured navigation commands.
**Acceptance Criteria:**
- [ ] DeepLinkHandler parses URL schemes (aiq://)
- [ ] DeepLinkHandler parses universal links (https://aiq.app/...)
- [ ] Returns structured DeepLink enum with associated data

---

### ICG-009: Register URL Schemes in Info.plist
**Status:** [ ] Not Started
**Files:** `Info.plist`
**Dependencies:** None
**Description:** Add `aiq://` custom URL scheme to Info.plist.
**Acceptance Criteria:**
- [ ] `aiq://` URL scheme registered in Info.plist
- [ ] App responds to `aiq://` URLs from Safari and other apps

---

### ICG-010: Configure Universal Links
**Status:** [ ] Not Started
**Files:** `AIQ.entitlements`, Apple Developer Portal
**Dependencies:** ICG-009
**Description:** Add Associated Domains entitlement for `applinks:aiq.app`.
**Acceptance Criteria:**
- [ ] Associated Domains entitlement added
- [ ] Universal link domain verified in Apple Developer Portal
- [ ] App responds to `https://aiq.app/...` links

---

### ICG-011: Integrate AppRouter into AIQApp.swift
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Dependencies:** ICG-007
**Description:** Replace root view navigation with router-based navigation.
**Acceptance Criteria:**
- [ ] AppRouter initialized in AIQApp.swift
- [ ] Router injected into environment
- [ ] Root navigation controlled by router

---

### ICG-012: Migrate DashboardView Navigation
**Status:** [ ] Not Started
**Files:** `Views/Dashboard/DashboardView.swift`
**Dependencies:** ICG-007, ICG-011
**Description:** Replace sheet/fullScreenCover modifiers with AppRouter calls.
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-013: Migrate TestTakingView Navigation
**Status:** [ ] Not Started
**Files:** `Views/Test/TestTakingView.swift`
**Dependencies:** ICG-007, ICG-011
**Description:** Replace navigation state management with AppRouter calls.
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-014: Migrate HistoryView Navigation
**Status:** [ ] Not Started
**Files:** `Views/History/HistoryView.swift`
**Dependencies:** ICG-007, ICG-011
**Description:** Replace navigation state management with AppRouter calls.
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-015: Migrate SettingsView Navigation
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Dependencies:** ICG-007, ICG-011
**Description:** Replace navigation state management with AppRouter calls.
**Acceptance Criteria:**
- [ ] All sheet/fullScreenCover modifiers replaced with router calls
- [ ] Navigation state removed from ViewModel
- [ ] Back navigation works correctly
- [ ] Deep state restoration supported

---

### ICG-016: Implement Deep Link Handling in AppDelegate
**Status:** [ ] Not Started
**Files:** `AppDelegate.swift`
**Dependencies:** ICG-008, ICG-009, ICG-010
**Description:** Handle `application(_:open:options:)` callback to process deep links.
**Acceptance Criteria:**
- [ ] AppDelegate handles URL opening callbacks
- [ ] URLs parsed by DeepLinkHandler
- [ ] Router navigates to correct destination

---

### ICG-017: Add Deep Link Routes
**Status:** [ ] Not Started
**Files:** `Services/Navigation/DeepLinkHandler.swift`
**Dependencies:** ICG-008, ICG-016
**Description:** Implement routes for `aiq://test/results/{id}`, `aiq://test/resume/{sessionId}`, `aiq://settings`.
**Acceptance Criteria:**
- [ ] All three route types implemented and tested
- [ ] Invalid routes handled gracefully with error state
- [ ] Routes work from cold start and background state

---

### ICG-018: Test Deep Links from Push Notifications
**Status:** [ ] Not Started
**Files:** Test only
**Dependencies:** ICG-016, ICG-017
**Description:** Verify notification tap navigates correctly to target screens.
**Acceptance Criteria:**
- [ ] Push notification tap opens app to correct screen
- [ ] Notification payload structure tested
- [ ] Works in foreground, background, and terminated states

---

## Phase 3: UI Testing Infrastructure

**Goal**: Create UI test target and cover all critical user flows with automated tests

---

### ICG-019: Create AIQUITests Target
**Status:** [ ] Not Started
**Files:** `AIQUITests/` (new directory)
**Dependencies:** None
**Description:** Create UI test target in Xcode with correct configuration, test host, bundle ID, and signing.
**Acceptance Criteria:**
- [ ] AIQUITests target created with correct configuration
- [ ] Test target builds successfully
- [ ] Can run UI tests from Xcode

---

### ICG-020: Create UI Test Helpers
**Status:** [ ] Not Started
**Files:** `AIQUITests/Helpers/` (new)
**Dependencies:** ICG-019
**Description:** Create LoginHelper, TestTakingHelper, and NavigationHelper for test code reuse.
**Acceptance Criteria:**
- [ ] LoginHelper provides authenticated test sessions
- [ ] TestTakingHelper handles test data setup
- [ ] NavigationHelper verifies screen transitions
- [ ] Helpers reduce test boilerplate

---

### ICG-021: Write Registration Flow UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/RegistrationFlowTests.swift` (new)
**Dependencies:** ICG-019, ICG-020
**Description:** Complete registration from start to dashboard with validation testing.
**Acceptance Criteria:**
- [ ] Test completes full registration flow
- [ ] Validates field validation errors
- [ ] Verifies successful registration leads to dashboard
- [ ] Runs reliably without flakiness

---

### ICG-022: Write Login/Logout Flow UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/AuthenticationFlowTests.swift` (new)
**Dependencies:** ICG-019, ICG-020
**Description:** Test login with valid/invalid credentials and logout flow.
**Acceptance Criteria:**
- [ ] Test covers login with valid credentials
- [ ] Test covers login with invalid credentials
- [ ] Test covers logout flow
- [ ] Verifies session persistence

---

### ICG-023: Write Test-Taking Flow UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/TestTakingFlowTests.swift` (new)
**Dependencies:** ICG-019, ICG-020
**Description:** Start test, answer all questions, submit, and verify results.
**Acceptance Criteria:**
- [ ] Test starts a new test session
- [ ] Test answers all questions (mocked question data)
- [ ] Test submits answers and verifies results screen
- [ ] Verifies score display and history update

---

### ICG-024: Write Test Abandonment UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/TestAbandonmentTests.swift` (new)
**Dependencies:** ICG-019, ICG-020
**Description:** Start test, abandon mid-flow, verify saved progress, and resume.
**Acceptance Criteria:**
- [ ] Test starts test and abandons mid-flow
- [ ] Test verifies saved progress
- [ ] Test resumes test and completes
- [ ] Verifies no data loss on abandonment

---

### ICG-025: Write Deep Link Navigation UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/DeepLinkTests.swift` (new)
**Dependencies:** ICG-017, ICG-019, ICG-020
**Description:** Test all deep link routes from terminated state.
**Acceptance Criteria:**
- [ ] Test all deep link routes (results, resume, settings)
- [ ] Test from app terminated state
- [ ] Test from app backgrounded state
- [ ] Verifies correct screen displayed

---

### ICG-026: Write Error State Handling UI Test
**Status:** [ ] Not Started
**Files:** `AIQUITests/ErrorHandlingTests.swift` (new)
**Dependencies:** ICG-019, ICG-020
**Description:** Test network errors, invalid responses, and retry logic.
**Acceptance Criteria:**
- [ ] Test network error handling with retry
- [ ] Test invalid API response handling
- [ ] Test timeout scenarios
- [ ] Verifies user-facing error messages

---

### ICG-027: Configure UI Tests in CI/CD
**Status:** [ ] Not Started
**Files:** `.github/workflows/ios-tests.yml`
**Dependencies:** ICG-019
**Description:** Add UI tests to GitHub Actions or Xcode Cloud.
**Acceptance Criteria:**
- [ ] UI tests run automatically on pull requests
- [ ] Test failures block merge
- [ ] Test reports uploaded as artifacts

---

## Phase 4: Privacy & Compliance

**Goal**: Meet App Store privacy and compliance requirements

---

### ICG-028: Create PrivacyInfo.xcprivacy Manifest
**Status:** [ ] Not Started
**Files:** `PrivacyInfo.xcprivacy` (new)
**Dependencies:** None
**Description:** Declare data collection and usage for App Store privacy requirements.
**Acceptance Criteria:**
- [ ] PrivacyInfo.xcprivacy created with all required fields
- [ ] Declares analytics, crash reporting, authentication data
- [ ] Passes App Store privacy validation

---

### ICG-029: Draft Privacy Policy Document
**Status:** [ ] Not Started
**Files:** External: Privacy policy website/PDF
**Dependencies:** None
**Description:** Cover data collection, storage, sharing, and deletion policies.
**Acceptance Criteria:**
- [ ] Privacy policy covers all data collected
- [ ] Explains data retention and deletion
- [ ] Complies with GDPR and CCPA requirements
- [ ] Hosted at publicly accessible URL

---

### ICG-030: Draft Terms of Service Document
**Status:** [ ] Not Started
**Files:** External: Terms of service website/PDF
**Dependencies:** None
**Description:** Cover user agreements, disclaimers, and liability.
**Acceptance Criteria:**
- [ ] Terms of service cover liability disclaimers
- [ ] Addresses intellectual property
- [ ] Hosted at publicly accessible URL
- [ ] Legal review completed

---

### ICG-031: Implement Consent Management Screen
**Status:** [ ] Not Started
**Files:** `Views/Onboarding/PrivacyConsentView.swift` (new)
**Dependencies:** ICG-029
**Description:** Display privacy policy and require acceptance on first launch.
**Acceptance Criteria:**
- [ ] Privacy consent screen shown on first launch
- [ ] User must accept to continue
- [ ] Consent timestamp stored locally
- [ ] Links to full privacy policy and terms

---

### ICG-032: Add Data Deletion Capability
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`, Backend: `/v1/user/delete-account` (new)
**Dependencies:** None
**Description:** Add settings option to delete account and all user data (GDPR right to erasure).
**Acceptance Criteria:**
- [ ] Settings screen includes "Delete Account" option
- [ ] Confirmation dialog warns of irreversible action
- [ ] Backend endpoint deletes all user data (GDPR right to erasure)
- [ ] User logged out and returned to welcome screen

---

### ICG-033: Update App Store Metadata
**Status:** [ ] Not Started
**Files:** App Store Connect
**Dependencies:** ICG-028, ICG-029, ICG-030
**Description:** Update privacy questions, data usage descriptions, and screenshots.
**Acceptance Criteria:**
- [ ] App Store Connect metadata updated
- [ ] Privacy questions answered accurately
- [ ] Screenshots show current UI
- [ ] App description mentions privacy compliance

---

## Phase 5: Localization Infrastructure

**Goal**: Prepare app for internationalization and localization

---

### ICG-034: Create Localizable.strings File
**Status:** [ ] Not Started
**Files:** `en.lproj/Localizable.strings` (new)
**Dependencies:** None
**Description:** Create base English localization file with all string keys.
**Acceptance Criteria:**
- [ ] Localizable.strings file created in Xcode
- [ ] All strings have unique keys
- [ ] Base localization (English) complete

---

### ICG-035: Create String+Localization Extension
**Status:** [ ] Not Started
**Files:** `Utilities/Extensions/String+Localization.swift`
**Dependencies:** None
**Description:** Add `.localized` helper for string keys.
**Acceptance Criteria:**
- [ ] String extension provides `.localized` computed property
- [ ] Extension handles missing keys gracefully
- [ ] Works with string interpolation

---

### ICG-036: Extract Hardcoded Strings from Views
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** ICG-034, ICG-035
**Description:** Replace all hardcoded strings in Views with localization keys.
**Acceptance Criteria:**
- [ ] All user-facing strings in Views use localization keys
- [ ] No hardcoded English strings remain
- [ ] App builds and runs with localized strings

---

### ICG-037: Extract Hardcoded Strings from ViewModels
**Status:** [ ] Not Started
**Files:** All ViewModel files
**Dependencies:** ICG-034, ICG-035
**Description:** Replace all hardcoded strings in ViewModels with localization keys.
**Acceptance Criteria:**
- [ ] All user-facing strings in ViewModels use localization
- [ ] Validation messages localized
- [ ] Success/error messages localized

---

### ICG-038: Extract Error Messages to Localizable.strings
**Status:** [ ] Not Started
**Files:** All Service files
**Dependencies:** ICG-034, ICG-035
**Description:** Replace all error message strings with localization keys.
**Acceptance Criteria:**
- [ ] All error messages use localization keys
- [ ] Error codes preserved for debugging
- [ ] User-friendly error messages in all cases

---

### ICG-039: Add RTL Layout Support
**Status:** [ ] Not Started
**Files:** Test only
**Dependencies:** ICG-036
**Description:** Test with Arabic/Hebrew simulators to verify RTL layout support.
**Acceptance Criteria:**
- [ ] App layout tested in RTL languages
- [ ] No UI overlaps or truncation
- [ ] Navigation behaves correctly in RTL

---

### ICG-040: Configure Locale-Aware Formatting
**Status:** [ ] Not Started
**Files:** `Utilities/Extensions/Date+Extensions.swift`
**Dependencies:** ICG-036
**Description:** Ensure all formatters respect user locale for dates and numbers.
**Acceptance Criteria:**
- [ ] DateFormatter respects user locale
- [ ] Number formatting uses locale-specific separators
- [ ] Currency formatting works for all supported locales

---

## Phase 6: Security Hardening

**Goal**: Eliminate security vulnerabilities before App Store submission

---

### ICG-041: Wrap Sensitive Logging in DEBUG Guards
**Status:** [ ] Not Started
**Files:** `Services/Auth/AuthService.swift` (lines 42-45, 70-73, 99-103)
**Dependencies:** None
**Description:** Wrap email, token, and user data logging in `#if DEBUG` blocks.
**Acceptance Criteria:**
- [ ] All email logging wrapped in `#if DEBUG` blocks
- [ ] All token logging wrapped in `#if DEBUG` blocks
- [ ] All user PII logging wrapped in `#if DEBUG` blocks
- [ ] Production builds log no sensitive data

---

### ICG-042: Audit All OSLog Calls for Sensitive Data
**Status:** [ ] Not Started
**Files:** All files with OSLog usage
**Dependencies:** ICG-041
**Description:** Remove or wrap all sensitive data logging in DEBUG guards.
**Acceptance Criteria:**
- [ ] Full codebase audit completed
- [ ] Spreadsheet/report of all logging calls created
- [ ] All sensitive logging wrapped or removed
- [ ] Non-sensitive logging preserved for debugging

---

### ICG-043: Integrate TrustKit for Certificate Pinning
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`, `TrustKit.plist` (new)
**Dependencies:** None
**Description:** Add TrustKit via SPM and create configuration file.
**Acceptance Criteria:**
- [ ] TrustKit integrated via Swift Package Manager
- [ ] TrustKit.plist configuration file created
- [ ] TrustKit initialized in app launch

---

### ICG-044: Configure Production SSL Certificate Pins
**Status:** [ ] Not Started
**Files:** `TrustKit.plist`
**Dependencies:** ICG-043
**Description:** Extract public key hashes from Railway certificates and configure pins.
**Acceptance Criteria:**
- [ ] Production backend SSL certificate analyzed
- [ ] Public key hashes extracted and configured
- [ ] Backup pins configured for rotation safety
- [ ] Pin expiration dates documented

---

### ICG-045: Test Certificate Pinning
**Status:** [ ] Not Started
**Files:** Test only
**Dependencies:** ICG-043, ICG-044
**Description:** Verify pinning blocks MITM attacks and allows valid certificates.
**Acceptance Criteria:**
- [ ] Valid certificates accepted (app works normally)
- [ ] Invalid certificates rejected (network calls fail)
- [ ] Self-signed certificates blocked
- [ ] MITM proxy blocked

---

### ICG-046: Add Environment-Specific Pinning Config
**Status:** [ ] Not Started
**Files:** `TrustKit.plist`, `AppConfig.swift`
**Dependencies:** ICG-043, ICG-044
**Description:** Disable pinning in DEBUG builds to allow development proxies.
**Acceptance Criteria:**
- [ ] DEBUG builds skip certificate pinning
- [ ] RELEASE builds enforce certificate pinning
- [ ] Staging environment uses separate pin config
- [ ] Environment switching tested

---

## Phase 7: Test Coverage Expansion

**Goal**: Achieve 80% code coverage with comprehensive unit tests

---

### ICG-047: Write AuthService Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/AuthServiceTests.swift` (new)
**Dependencies:** None
**Description:** Test login, logout, registration, and token refresh with mocked dependencies.
**Acceptance Criteria:**
- [ ] All AuthService methods tested
- [ ] Success and error cases covered
- [ ] Mock APIClient used for isolation
- [ ] Edge cases tested (expired tokens, network errors)

---

### ICG-048: Write NotificationService Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/NotificationServiceTests.swift` (new)
**Dependencies:** None
**Description:** Test device registration and preference updates.
**Acceptance Criteria:**
- [ ] All public methods tested
- [ ] Success and error paths covered
- [ ] Dependencies mocked
- [ ] Async operations tested correctly

---

### ICG-049: Write NotificationManager Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/NotificationManagerTests.swift` (new)
**Dependencies:** None
**Description:** Test scheduling and permission handling.
**Acceptance Criteria:**
- [ ] All public methods tested
- [ ] Success and error paths covered
- [ ] Dependencies mocked
- [ ] Async operations tested correctly

---

### ICG-050: Write AnalyticsService Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Services/AnalyticsServiceTests.swift` (new)
**Dependencies:** None
**Description:** Test event tracking and backend sync.
**Acceptance Criteria:**
- [ ] All public methods tested
- [ ] Success and error paths covered
- [ ] Dependencies mocked
- [ ] Async operations tested correctly

---

### ICG-051: Write KeychainStorage Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Storage/KeychainStorageTests.swift` (new)
**Dependencies:** None
**Description:** Test token storage, retrieval, and deletion.
**Acceptance Criteria:**
- [ ] All storage operations tested
- [ ] Data persistence verified
- [ ] Error handling tested
- [ ] Concurrent access tested

---

### ICG-052: Write LocalAnswerStorage Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Storage/LocalAnswerStorageTests.swift` (new)
**Dependencies:** None
**Description:** Test answer persistence and retrieval.
**Acceptance Criteria:**
- [ ] All storage operations tested
- [ ] Data persistence verified
- [ ] Error handling tested
- [ ] Concurrent access tested

---

### ICG-053: Write DataCache Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Storage/DataCacheTests.swift` (new)
**Dependencies:** None
**Description:** Test cache storage, expiration, and invalidation.
**Acceptance Criteria:**
- [ ] All storage operations tested
- [ ] Data persistence verified
- [ ] Error handling tested
- [ ] Concurrent access tested

---

### ICG-054: Write RetryPolicy Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Network/RetryPolicyTests.swift` (new)
**Dependencies:** None
**Description:** Test exponential backoff and max retries.
**Acceptance Criteria:**
- [ ] All retry logic tested
- [ ] Exponential backoff verified
- [ ] Max retry limit enforced
- [ ] Edge cases covered

---

### ICG-055: Write TokenRefreshInterceptor Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Network/TokenRefreshInterceptorTests.swift` (new)
**Dependencies:** None
**Description:** Test concurrent request handling and race conditions.
**Acceptance Criteria:**
- [ ] All interceptor logic tested
- [ ] Concurrent request handling verified
- [ ] Race conditions prevented
- [ ] Token refresh flow tested

---

### ICG-056: Write NetworkMonitor Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Network/NetworkMonitorTests.swift` (new)
**Dependencies:** None
**Description:** Test connection status changes.
**Acceptance Criteria:**
- [ ] All monitor logic tested
- [ ] Connection status changes verified
- [ ] Callbacks fired correctly
- [ ] Edge cases covered

---

### ICG-057: Write User Model Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Models/UserTests.swift` (new)
**Dependencies:** None
**Description:** Test validation and serialization.
**Acceptance Criteria:**
- [ ] All model validation tested
- [ ] Serialization/deserialization tested
- [ ] Edge cases covered
- [ ] Invalid data handled

---

### ICG-058: Write Question Model Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Models/QuestionTests.swift` (new)
**Dependencies:** None
**Description:** Test validation and answer checking.
**Acceptance Criteria:**
- [ ] All model validation tested
- [ ] Serialization/deserialization tested
- [ ] Edge cases covered
- [ ] Invalid data handled

---

### ICG-059: Write TestSession Model Unit Tests
**Status:** [ ] Not Started
**Files:** `AIQTests/Models/TestSessionTests.swift` (new)
**Dependencies:** None
**Description:** Test status transitions and validation.
**Acceptance Criteria:**
- [ ] All model validation tested
- [ ] Serialization/deserialization tested
- [ ] Edge cases covered
- [ ] Invalid data handled

---

### ICG-060: Run Code Coverage Report
**Status:** [ ] Not Started
**Files:** Xcode coverage tool
**Dependencies:** ICG-047 to ICG-059
**Description:** Generate coverage report and identify remaining gaps.
**Acceptance Criteria:**
- [ ] Code coverage report generated
- [ ] Coverage percentage by file documented
- [ ] Gaps identified and prioritized

---

### ICG-061: Write Additional Tests for 80% Coverage
**Status:** [ ] Not Started
**Files:** Various test files
**Dependencies:** ICG-060
**Description:** Fill coverage gaps to reach 80% target.
**Acceptance Criteria:**
- [ ] Code coverage reaches 80% or higher
- [ ] Critical paths have 100% coverage
- [ ] Remaining gaps documented with justification

---

## Phase 8: Accessibility Audit

**Goal**: Ensure WCAG AA compliance and excellent VoiceOver experience

---

### ICG-062: Audit All Views with VoiceOver
**Status:** [ ] Not Started
**Files:** Test audit (documentation only)
**Dependencies:** None
**Description:** Test every screen with VoiceOver enabled and document issues.
**Acceptance Criteria:**
- [ ] All screens tested with VoiceOver
- [ ] Navigation flow logical and clear
- [ ] All interactive elements reachable
- [ ] Issues documented with severity

---

### ICG-063: Add Accessibility Labels to Interactive Elements
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** ICG-062
**Description:** Add descriptive accessibility labels to all buttons, images, and form fields.
**Acceptance Criteria:**
- [ ] All buttons have descriptive labels
- [ ] All images have alt text
- [ ] Form fields have labels
- [ ] No unlabeled interactive elements

---

### ICG-064: Add Accessibility Hints for Non-Obvious Interactions
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** ICG-062
**Description:** Add hints for gestures and complex interactions.
**Acceptance Criteria:**
- [ ] Non-obvious gestures have hints
- [ ] Complex interactions explained
- [ ] Hints concise and helpful

---

### ICG-065: Verify Color Contrast Meets WCAG AA
**Status:** [ ] Not Started
**Files:** `Utilities/Design/ColorPalette.swift`
**Dependencies:** None
**Description:** Use contrast checker tool to verify all color combinations.
**Acceptance Criteria:**
- [ ] All color combinations tested
- [ ] Contrast ratios documented
- [ ] Failing combinations identified

---

### ICG-066: Fix Color Contrast Failures
**Status:** [ ] Not Started
**Files:** `Utilities/Design/ColorPalette.swift`
**Dependencies:** ICG-065
**Description:** Adjust colors to meet 4.5:1 ratio for normal text.
**Acceptance Criteria:**
- [ ] All color contrast meets 4.5:1 for normal text
- [ ] All color contrast meets 3:1 for large text
- [ ] Visual design preserved where possible

---

### ICG-067: Verify Touch Targets Meet 44x44pt Minimum
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** None
**Description:** Audit all buttons and interactive elements for minimum touch target size.
**Acceptance Criteria:**
- [ ] All buttons and tap targets measured
- [ ] Undersized targets documented
- [ ] Priority list created

---

### ICG-068: Fix Undersized Touch Targets
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** ICG-067
**Description:** Add padding or minimum frame sizes to undersized targets.
**Acceptance Criteria:**
- [ ] All touch targets 44x44pt or larger
- [ ] No tappable elements too small
- [ ] Visual design preserved

---

### ICG-069: Test Dynamic Type Support
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** None
**Description:** Verify all text scales correctly at all Dynamic Type sizes.
**Acceptance Criteria:**
- [ ] App tested at all Dynamic Type sizes (XS to XXXL)
- [ ] Text truncation issues identified
- [ ] Layout issues documented

---

### ICG-070: Fix Dynamic Type Issues
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** ICG-069
**Description:** Use relative spacing and avoid fixed heights for text containers.
**Acceptance Criteria:**
- [ ] All text scales without truncation
- [ ] Layouts adapt to large text
- [ ] Scrollable regions used where needed

---

### ICG-071: Test Reduce Motion Support
**Status:** [ ] Not Started
**Files:** All animated views
**Dependencies:** None
**Description:** Verify animations respect accessibility Reduce Motion setting.
**Acceptance Criteria:**
- [ ] All animations tested with Reduce Motion enabled
- [ ] Disorienting animations identified

---

### ICG-072: Add Reduce Motion Alternatives
**Status:** [ ] Not Started
**Files:** All animated views
**Dependencies:** ICG-071
**Description:** Disable or simplify animations when Reduce Motion is enabled.
**Acceptance Criteria:**
- [ ] Animations disabled or simplified when Reduce Motion enabled
- [ ] Transitions remain functional
- [ ] User experience preserved

---

### ICG-073: Document Accessibility Features in App Store
**Status:** [ ] Not Started
**Files:** App Store Connect
**Dependencies:** ICG-062 to ICG-072
**Description:** List accessibility features in App Store description.
**Acceptance Criteria:**
- [ ] Accessibility features listed in App Store description
- [ ] VoiceOver support highlighted
- [ ] Dynamic Type support mentioned

---

## Phase 9: User Experience Enhancements

**Goal**: Improve first-run experience and user feedback mechanisms

---

### ICG-074: Design Onboarding Flow
**Status:** [ ] Not Started
**Files:** Design mockups
**Dependencies:** None
**Description:** Design 3-4 screens explaining app value and test mechanics.
**Acceptance Criteria:**
- [ ] Onboarding flow designed with 3-4 screens
- [ ] Content finalized and approved
- [ ] Illustrations or graphics sourced

---

### ICG-075: Create OnboardingView
**Status:** [ ] Not Started
**Files:** `Views/Onboarding/OnboardingView.swift` (new)
**Dependencies:** ICG-074
**Description:** Create OnboardingView with page indicators and skip option.
**Acceptance Criteria:**
- [ ] OnboardingView created with SwiftUI TabView
- [ ] Page indicators show progress
- [ ] Skip button allows bypassing
- [ ] "Get Started" button on final screen

---

### ICG-076: Create Onboarding Content
**Status:** [ ] Not Started
**Files:** `Views/Onboarding/OnboardingView.swift`
**Dependencies:** ICG-075
**Description:** Add content for app value, test mechanics, recommended frequency, and privacy.
**Acceptance Criteria:**
- [ ] Screen 1: App value proposition
- [ ] Screen 2: How tests work
- [ ] Screen 3: Recommended 3-month frequency
- [ ] Screen 4: Privacy and data handling

---

### ICG-077: Integrate Onboarding into First-Launch Flow
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Dependencies:** ICG-075, ICG-076
**Description:** Show onboarding after registration or on first open.
**Acceptance Criteria:**
- [ ] Onboarding shown on first launch after registration
- [ ] Onboarding shown on first launch for existing users (migration)
- [ ] Flag stored to prevent repeated display

---

### ICG-078: Add View Onboarding Again to Settings
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Dependencies:** ICG-075
**Description:** Add option to re-view onboarding from Settings.
**Acceptance Criteria:**
- [ ] Settings includes "View Onboarding Again" option
- [ ] Tapping option displays onboarding flow
- [ ] User can skip through quickly

---

### ICG-079: Create FeedbackView
**Status:** [ ] Not Started
**Files:** `Views/Settings/FeedbackView.swift` (new)
**Dependencies:** None
**Description:** Create feedback form with name, email, category, and description fields.
**Acceptance Criteria:**
- [ ] Feedback form includes all required fields
- [ ] Form validation prevents empty submissions
- [ ] Category dropdown includes common feedback types

---

### ICG-080: Implement Feedback Submission to Backend
**Status:** [ ] Not Started
**Files:** Backend: `/v1/feedback/submit` (new), `Views/Settings/FeedbackView.swift`
**Dependencies:** ICG-079
**Description:** Create backend endpoint and connect iOS form submission.
**Acceptance Criteria:**
- [ ] Backend endpoint created and tested
- [ ] Feedback stored in database
- [ ] Email notification sent to admin
- [ ] Success/error handling in iOS app

---

### ICG-081: Add Send Feedback to Settings Menu
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Dependencies:** ICG-079
**Description:** Add "Send Feedback" option to Settings menu.
**Acceptance Criteria:**
- [ ] Settings menu includes "Send Feedback" option
- [ ] Tapping option navigates to FeedbackView
- [ ] Submission shows success confirmation

---

## Phase 10: Code Quality - Redundancy Elimination

**Goal**: Eliminate code duplication and improve maintainability

---

### ICG-082: Consolidate Email Validation
**Status:** [ ] Not Started
**Files:** `ViewModels/LoginViewModel.swift`, `ViewModels/RegistrationViewModel.swift`
**Dependencies:** None
**Description:** Use `String+Extensions.swift` consistently for email validation.
**Acceptance Criteria:**
- [ ] All email validation uses single implementation
- [ ] Validation logic identical across all call sites
- [ ] Unit tests verify validation consistency

---

### ICG-083: Consolidate Password Validation
**Status:** [ ] Not Started
**Files:** `ViewModels/LoginViewModel.swift`, `ViewModels/RegistrationViewModel.swift`
**Dependencies:** None
**Description:** Use `Validators.swift` or create shared validator for passwords.
**Acceptance Criteria:**
- [ ] All password validation uses single implementation
- [ ] Validation rules identical across all call sites
- [ ] Password requirements documented

---

### ICG-084: Extract IQ Score Classification to Shared Utility
**Status:** [ ] Not Started
**Files:** `Utilities/Helpers/IQScoreUtility.swift` (new), `Views/Test/TestResultsView.swift`, `Views/History/TestDetailView+Helpers.swift`
**Dependencies:** None
**Description:** Create shared utility for IQ score classification and color mapping.
**Acceptance Criteria:**
- [ ] IQScoreUtility.swift created with classification method
- [ ] Method accepts IQ score, returns category and color
- [ ] Unit tests verify all score ranges

---

### ICG-085: Remove Duplicate IQ Classification Code
**Status:** [ ] Not Started
**Files:** `Views/Test/TestResultsView.swift`, `Views/History/TestDetailView+Helpers.swift`
**Dependencies:** ICG-084
**Description:** Replace duplicate switch statements with IQScoreUtility calls.
**Acceptance Criteria:**
- [ ] TestResultsView uses IQScoreUtility
- [ ] TestDetailView+Helpers uses IQScoreUtility
- [ ] Duplicate switch statements removed
- [ ] Visual output identical to before

---

### ICG-086: Audit DateFormatter Usage
**Status:** [ ] Not Started
**Files:** Documentation only
**Dependencies:** None
**Description:** Identify all instances creating DateFormatters across codebase.
**Acceptance Criteria:**
- [ ] All DateFormatter usage documented
- [ ] Call sites categorized by format type
- [ ] Migration plan created

---

### ICG-087: Migrate to Date+Extensions Helpers
**Status:** [ ] Not Started
**Files:** `ViewModels/DashboardViewModel.swift`, `Views/Test/TestResultsView.swift`, `Views/History/IQTrendChart.swift`, others
**Dependencies:** ICG-086
**Description:** Replace formatter creation with Date+Extensions methods.
**Acceptance Criteria:**
- [ ] All DateFormatter creation replaced with extensions
- [ ] Date formatting consistent across app
- [ ] Performance improved (fewer formatter allocations)

---

### ICG-088: Create Reusable InfoCard Component
**Status:** [ ] Not Started
**Files:** `Views/Common/InfoCard.swift` (new)
**Dependencies:** None
**Description:** Extract common card pattern from WelcomeView and RegistrationView.
**Acceptance Criteria:**
- [ ] InfoCard component supports title, description, icon
- [ ] Component supports customization (colors, sizing)
- [ ] Component previews created

---

### ICG-089: Replace FeatureCard with InfoCard in WelcomeView
**Status:** [ ] Not Started
**Files:** `Views/Auth/WelcomeView.swift`
**Dependencies:** ICG-088
**Description:** Use new InfoCard component instead of custom FeatureCard.
**Acceptance Criteria:**
- [ ] WelcomeView uses InfoCard
- [ ] Visual output identical to before
- [ ] Code duplication eliminated

---

### ICG-090: Replace RegistrationBenefitCard with InfoCard
**Status:** [ ] Not Started
**Files:** `Views/Auth/RegistrationView.swift`
**Dependencies:** ICG-088
**Description:** Use new InfoCard component instead of custom RegistrationBenefitCard.
**Acceptance Criteria:**
- [ ] RegistrationView uses InfoCard
- [ ] Visual output identical to before
- [ ] Code duplication eliminated

---

## Phase 11: Code Quality - Architecture Fixes

**Goal**: Fix architectural issues (StateObject misuse, race conditions, retain cycles)

---

### ICG-091: Fix StateObject Misuse in DashboardView
**Status:** [ ] Not Started
**Files:** `Views/Dashboard/DashboardView.swift`
**Dependencies:** None
**Description:** Change @StateObject to @ObservedObject for singleton AuthManager.
**Acceptance Criteria:**
- [ ] DashboardView uses @ObservedObject instead of @StateObject
- [ ] AuthManager.shared still works correctly
- [ ] No duplicate instances created

---

### ICG-092: Convert TokenRefreshInterceptor to Actor
**Status:** [ ] Not Started
**Files:** `Services/Auth/TokenRefreshInterceptor.swift`
**Dependencies:** None
**Description:** Eliminate race condition on concurrent requests by using Swift actor.
**Acceptance Criteria:**
- [ ] TokenRefreshInterceptor converted to Swift actor
- [ ] All properties accessed via async/await
- [ ] Compilation succeeds

---

### ICG-093: Test TokenRefreshInterceptor Thread Safety
**Status:** [ ] Not Started
**Files:** `AIQTests/Network/TokenRefreshInterceptorConcurrencyTests.swift` (new)
**Dependencies:** ICG-092
**Description:** Create stress test with concurrent requests to verify thread safety.
**Acceptance Criteria:**
- [ ] Stress test creates 10+ concurrent requests
- [ ] Token refresh only happens once
- [ ] No race condition errors
- [ ] All requests succeed

---

### ICG-094: Fix Retain Cycle in DashboardViewModel
**Status:** [ ] Not Started
**Files:** `ViewModels/DashboardViewModel.swift`
**Dependencies:** None
**Description:** Add [weak self] to retry closure.
**Acceptance Criteria:**
- [ ] Retry closure uses [weak self]
- [ ] Memory leak resolved
- [ ] Functionality unchanged

---

### ICG-095: Audit Timer Closures for Retain Cycles
**Status:** [ ] Not Started
**Files:** Documentation only
**Dependencies:** None
**Description:** Search for Timer usage without weak self references.
**Acceptance Criteria:**
- [ ] All Timer usage documented
- [ ] Retain cycle risks identified
- [ ] Priority fixes listed

---

### ICG-096: Fix Timer Retain Cycles
**Status:** [ ] Not Started
**Files:** Various ViewModel files
**Dependencies:** ICG-095
**Description:** Add [weak self] to all timer closures.
**Acceptance Criteria:**
- [ ] All timer closures use [weak self]
- [ ] No compiler warnings
- [ ] Functionality unchanged

---

### ICG-097: Run Memory Leak Detection
**Status:** [ ] Not Started
**Files:** Test only
**Dependencies:** ICG-094, ICG-096
**Description:** Use Xcode Instruments to verify no memory leaks.
**Acceptance Criteria:**
- [ ] Instruments Leaks tool run on app
- [ ] No memory leaks detected
- [ ] Memory graph verified clean

---

## Phase 12: Code Quality - Magic Numbers

**Goal**: Extract magic numbers to named constants for maintainability

---

### ICG-098: Create Constants.swift File
**Status:** [ ] Not Started
**Files:** `Utilities/Helpers/Constants.swift` (new)
**Dependencies:** None
**Description:** Organize constants by domain (Timing, Network, Test).
**Acceptance Criteria:**
- [ ] Constants.swift file created
- [ ] Organized into nested structs by domain
- [ ] Documentation comments explain each constant

---

### ICG-099: Extract Timer Critical Threshold
**Status:** [ ] Not Started
**Files:** `ViewModels/TestTimerManager.swift`, `Utilities/Helpers/Constants.swift`
**Dependencies:** ICG-098
**Description:** Extract 60 seconds threshold to named constant.
**Acceptance Criteria:**
- [ ] Magic number replaced with named constant
- [ ] Constant value identical to original
- [ ] All references updated
- [ ] Code more readable

---

### ICG-100: Extract Slow Request Threshold
**Status:** [ ] Not Started
**Files:** `Services/API/APIClient.swift`, `Utilities/Helpers/Constants.swift`
**Dependencies:** ICG-098
**Description:** Extract 2.0 seconds threshold to named constant.
**Acceptance Criteria:**
- [ ] Magic number replaced with named constant
- [ ] Constant value identical to original
- [ ] All references updated
- [ ] Code more readable

---

### ICG-101: Extract Auto-Save Delay
**Status:** [ ] Not Started
**Files:** `ViewModels/TestTakingViewModel.swift`, `Utilities/Helpers/Constants.swift`
**Dependencies:** ICG-098
**Description:** Extract 1.0 seconds delay to named constant.
**Acceptance Criteria:**
- [ ] Magic number replaced with named constant
- [ ] Constant value identical to original
- [ ] All references updated
- [ ] Code more readable

---

### ICG-102: Extract Progress Validity Duration
**Status:** [ ] Not Started
**Files:** `Models/SavedTestProgress.swift`, `Utilities/Helpers/Constants.swift`
**Dependencies:** ICG-098
**Description:** Extract 24 hours validity to named constant.
**Acceptance Criteria:**
- [ ] Magic number replaced with named constant
- [ ] Constant value identical to original
- [ ] All references updated
- [ ] Code more readable

---

### ICG-103: Audit Codebase for Additional Magic Numbers
**Status:** [ ] Not Started
**Files:** Documentation only
**Dependencies:** ICG-098
**Description:** Search for remaining magic numbers and categorize by priority.
**Acceptance Criteria:**
- [ ] Full codebase search completed
- [ ] Magic numbers categorized by priority
- [ ] List of remaining numbers documented

---

### ICG-104: Extract Remaining Magic Numbers
**Status:** [ ] Not Started
**Files:** Various files
**Dependencies:** ICG-103
**Description:** Extract all high-priority magic numbers to constants.
**Acceptance Criteria:**
- [ ] All high-priority magic numbers extracted
- [ ] Constants well-named and documented
- [ ] Code maintainability improved

---

## Phase 13: Code Quality - Final Touches

**Goal**: Address remaining code quality issues

---

### ICG-105: Add Birth Year Validation
**Status:** [ ] Not Started
**Files:** `ViewModels/RegistrationViewModel.swift`
**Dependencies:** None
**Description:** Validate birth year is between 1900 and current year.
**Acceptance Criteria:**
- [ ] Birth year validation added to ViewModel
- [ ] Rejects years before 1900
- [ ] Rejects years after current year
- [ ] User-friendly error message displayed

---

### ICG-106: Create ServiceContainer for Dependency Injection
**Status:** [ ] Not Started
**Files:** `Utilities/DI/ServiceContainer.swift` (new)
**Dependencies:** None
**Description:** Create container for registering and resolving dependencies.
**Acceptance Criteria:**
- [ ] ServiceContainer class created
- [ ] Supports registration and resolution of dependencies
- [ ] Thread-safe implementation
- [ ] Supports protocol-based injection

---

### ICG-107: Migrate ViewModels to Use ServiceContainer
**Status:** [ ] Not Started
**Files:** All ViewModels
**Dependencies:** ICG-106
**Description:** Inject dependencies instead of using singletons directly.
**Acceptance Criteria:**
- [ ] All ViewModels accept dependencies via initializer
- [ ] No direct singleton usage in ViewModels
- [ ] Testability improved
- [ ] Functionality unchanged

---

### ICG-108: Create Environment Key for ServiceContainer
**Status:** [ ] Not Started
**Files:** `Utilities/DI/ServiceContainer.swift`
**Dependencies:** ICG-106
**Description:** Create SwiftUI environment key for container injection.
**Acceptance Criteria:**
- [ ] Environment key created for ServiceContainer
- [ ] SwiftUI environment integration working

---

### ICG-109: Inject ServiceContainer into App Environment
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Dependencies:** ICG-106, ICG-108
**Description:** Initialize and inject ServiceContainer at app launch.
**Acceptance Criteria:**
- [ ] ServiceContainer initialized in AIQApp.swift
- [ ] All services registered
- [ ] Injected into environment
- [ ] App launches successfully

---

## Phase 14: P2 Enhancements - Offline & State

**Goal**: Improve offline capabilities and state persistence

---

### ICG-110: Create Offline Operation Queue
**Status:** [ ] Not Started
**Files:** `Services/Storage/OfflineOperationQueue.swift` (new)
**Dependencies:** None
**Description:** Queue profile updates and settings changes when offline.
**Acceptance Criteria:**
- [ ] OfflineOperationQueue created
- [ ] Supports queuing mutations when offline
- [ ] Persists queue to disk
- [ ] Operations have retry logic

---

### ICG-111: Implement Background Sync for Offline Operations
**Status:** [ ] Not Started
**Files:** `Services/Storage/OfflineOperationQueue.swift`
**Dependencies:** ICG-110
**Description:** Sync queued operations when network returns.
**Acceptance Criteria:**
- [ ] Queue monitors network status
- [ ] Syncs operations when network returns
- [ ] Handles conflicts gracefully
- [ ] User notified of sync status

---

### ICG-112: Add Retry Logic for Failed Mutations
**Status:** [ ] Not Started
**Files:** `Services/Storage/OfflineOperationQueue.swift`
**Dependencies:** ICG-110
**Description:** Implement exponential backoff and max retry limits.
**Acceptance Criteria:**
- [ ] Failed operations retry with exponential backoff
- [ ] Max retry limit enforced
- [ ] Permanently failed operations reported to user

---

### ICG-113: Create AppStateStorage for UI State Persistence
**Status:** [ ] Not Started
**Files:** `Services/Storage/AppStateStorage.swift` (new)
**Dependencies:** None
**Description:** Persist UI state like tab selection and filter preferences.
**Acceptance Criteria:**
- [ ] AppStateStorage created with UserDefaults backend
- [ ] Supports reading/writing various state types
- [ ] Type-safe API

---

### ICG-114: Persist Tab Selection Across App Launches
**Status:** [ ] Not Started
**Files:** `Views/MainTabView.swift`
**Dependencies:** ICG-113
**Description:** Save and restore selected tab on app launch.
**Acceptance Criteria:**
- [ ] Selected tab saved on change
- [ ] Restored on app launch
- [ ] Defaults to dashboard if no saved state

---

### ICG-115: Persist Filter Preferences in HistoryView
**Status:** [ ] Not Started
**Files:** `Views/History/HistoryView.swift`
**Dependencies:** ICG-113
**Description:** Save and restore filter selections.
**Acceptance Criteria:**
- [ ] Filter selections saved on change
- [ ] Restored on view appear
- [ ] Defaults to "All" if no saved state

---

### ICG-116: Persist Scroll Positions in Long Lists
**Status:** [ ] Not Started
**Files:** Various list views
**Dependencies:** ICG-113
**Description:** Save and restore scroll positions (nice-to-have).
**Acceptance Criteria:**
- [ ] Scroll position saved for long lists
- [ ] Restored on view appear (if feasible with SwiftUI)
- [ ] Degrades gracefully if not possible

---

## Phase 15: P3 Enhancements - Nice-to-Have Features

**Goal**: Add polish features for enhanced user experience (can be deferred post-launch)

---

### ICG-117: Create BiometricAuthManager
**Status:** [ ] Not Started
**Files:** `Services/Auth/BiometricAuthManager.swift` (new)
**Dependencies:** None
**Description:** Add Face ID / Touch ID support with fallback to passcode.
**Acceptance Criteria:**
- [ ] BiometricAuthManager supports Face ID and Touch ID
- [ ] Handles permission requests
- [ ] Fallback to passcode if biometric fails

---

### ICG-118: Add Biometric Authentication Option to Settings
**Status:** [ ] Not Started
**Files:** `Views/Settings/SettingsView.swift`
**Dependencies:** ICG-117
**Description:** Add toggle for enabling/disabling biometric auth.
**Acceptance Criteria:**
- [ ] Settings toggle for biometric auth
- [ ] Disabled if device doesn't support biometrics
- [ ] Preference saved securely

---

### ICG-119: Implement Biometric Auth on App Launch
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Dependencies:** ICG-117, ICG-118
**Description:** Prompt for biometric auth when app launches if enabled.
**Acceptance Criteria:**
- [ ] Biometric prompt shown on app launch if enabled
- [ ] Successful auth shows app content
- [ ] Failed auth shows retry or exit options

---

### ICG-120: Create HapticManager
**Status:** [ ] Not Started
**Files:** `Utilities/Helpers/HapticManager.swift` (new)
**Dependencies:** None
**Description:** Create simple API for common haptic feedback types.
**Acceptance Criteria:**
- [ ] HapticManager provides simple API for common feedback types
- [ ] Supports success, error, warning, selection
- [ ] Respects system haptic settings

---

### ICG-121: Add Haptic Feedback to Button Taps
**Status:** [ ] Not Started
**Files:** `Views/Common/PrimaryButton.swift`, others
**Dependencies:** ICG-120
**Description:** Add tactile feedback to button interactions.
**Acceptance Criteria:**
- [ ] Appropriate haptic feedback added
- [ ] Not overused (only meaningful interactions)
- [ ] Respects accessibility settings

---

### ICG-122: Add Haptic Feedback to Success/Error States
**Status:** [ ] Not Started
**Files:** All ViewModels
**Dependencies:** ICG-120
**Description:** Add tactile feedback for operation outcomes.
**Acceptance Criteria:**
- [ ] Appropriate haptic feedback added
- [ ] Not overused (only meaningful interactions)
- [ ] Respects accessibility settings

---

### ICG-123: Add Haptic Feedback to Timer Warnings
**Status:** [ ] Not Started
**Files:** `ViewModels/TestTimerManager.swift`
**Dependencies:** ICG-120
**Description:** Add tactile feedback when timer reaches warning threshold.
**Acceptance Criteria:**
- [ ] Appropriate haptic feedback added
- [ ] Not overused (only meaningful interactions)
- [ ] Respects accessibility settings

---

### ICG-124: Optimize Layouts for iPad
**Status:** [ ] Not Started
**Files:** All View files
**Dependencies:** None
**Description:** Create multi-column layouts for larger screens.
**Acceptance Criteria:**
- [ ] Layouts use adaptive sizing
- [ ] Multi-column layouts on larger screens
- [ ] No awkward stretching on iPad

---

### ICG-125: Add Keyboard Shortcuts for iPad
**Status:** [ ] Not Started
**Files:** Various views
**Dependencies:** ICG-124
**Description:** Add discoverable keyboard shortcuts for common actions.
**Acceptance Criteria:**
- [ ] Common actions have keyboard shortcuts (Cmd+N, Cmd+R, etc.)
- [ ] Shortcuts discoverable
- [ ] Don't conflict with system shortcuts

---

### ICG-126: Add Split View Support for iPad
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`
**Dependencies:** ICG-124
**Description:** Support iPad multitasking split view mode.
**Acceptance Criteria:**
- [ ] App supports split view multitasking
- [ ] Layouts adapt to narrow widths
- [ ] No crashes in split view

---

### ICG-127: Create Widget Extension
**Status:** [ ] Not Started
**Files:** Widget extension target (new)
**Dependencies:** None
**Description:** Show latest score or next test date on home screen widget.
**Acceptance Criteria:**
- [ ] Widget shows latest IQ score
- [ ] Widget shows days until next test
- [ ] Tapping widget opens app to relevant screen

---

### ICG-128: Add Snapshot Testing
**Status:** [ ] Not Started
**Files:** Snapshot test files (new)
**Dependencies:** None
**Description:** Add visual regression testing with swift-snapshot-testing.
**Acceptance Criteria:**
- [ ] Snapshot tests created for key views
- [ ] Tests run in CI/CD
- [ ] Failures detected on UI changes

---

### ICG-129: Add Background Refresh Capability
**Status:** [ ] Not Started
**Files:** `AIQApp.swift`, `AppDelegate.swift`
**Dependencies:** None
**Description:** Fetch new data in background and notify user of updates.
**Acceptance Criteria:**
- [ ] Background refresh fetches new data
- [ ] User notified of updates if relevant
- [ ] Battery impact minimized

---

## Deferred Items

### ICG-131: Add Unit Tests for AnalyticsService
**Status:** [ ] Not Started
**Source:** PR #381 review comment
**Files:** `ios/AIQTests/Services/AnalyticsServiceTests.swift` (new)
**Description:** The AnalyticsService implementation in PR #381 has no test coverage. Tests are needed for retry logic, offline queue persistence, optional auth handling, and error scenarios.
**Original Comment:** "This PR includes ZERO tests for retry logic, offline queue, optional auth, or persistence. This is high-risk given the complexity."
**Acceptance Criteria:**
- [ ] Unit tests for submitWithRetry exponential backoff logic
- [ ] Tests for offline queue persistence (persistEvents/loadPersistedEvents)
- [ ] Tests for event batch submission success/failure scenarios
- [ ] Tests for network connectivity handling
- [ ] Tests for auth token inclusion (optional)
- [ ] Mock UserDefaults and NetworkMonitor for isolation

---

### ICG-130: Create SettingsViewModel for MVVM Compliance
**Status:** [ ] Not Started
**Source:** PR #380 review comment
**Files:** `Views/Settings/SettingsView.swift`, `ViewModels/SettingsViewModel.swift` (new)
**Description:** SettingsView currently violates MVVM architecture by directly accessing `AuthManager.shared` and executing logout logic in the View layer. Create a SettingsViewModel to handle business logic (similar to LoginViewModel, DashboardViewModel, etc.).
**Original Comment:** "According to ios/docs/ARCHITECTURE.md, Views should not contain business logic. Currently, SettingsView directly accesses AuthManager.shared and executes logout logic in the View layer."
**Acceptance Criteria:**
- [ ] SettingsViewModel created following project patterns
- [ ] AuthManager access moved to ViewModel
- [ ] Logout logic moved to ViewModel
- [ ] View testability improved
- [ ] Consistent with other ViewModels in codebase

---

## Open Questions

1. **Privacy Policy Hosting**: Where will the privacy policy and terms of service be hosted? Do we need to set up a website or can we use a third-party service?
   - **Recommendation**: Use simple static site (GitHub Pages) or include in App Store metadata

2. **Analytics Backend Endpoint**: Does the backend have a `/v1/analytics/events` endpoint already, or does it need to be created?
   - **Action Required**: Verify with backend architect, create endpoint if needed

3. **Firebase vs Sentry**: Is there a preference between Firebase Crashlytics and Sentry? Any existing Firebase setup?
   - **Action Required**: Confirm decision with team

4. **Certificate Pinning Scope**: Should we pin all backend domains or just production? What about third-party APIs (Firebase, etc.)?
   - **Recommendation**: Pin only production backend, exclude third-party services

5. **Localization Strategy**: Which languages should we support at launch? Just English, or should we prepare for immediate internationalization?
   - **Recommendation**: Launch with English only, infrastructure ready for adding languages

6. **Onboarding Content**: Who will write and approve onboarding content? Do we need legal review?
   - **Action Required**: Assign content owner, schedule legal review

7. **Feedback Endpoint Backend**: Does the backend need a new `/v1/feedback/submit` endpoint, or does this exist?
   - **Action Required**: Coordinate with backend team

8. **P3 Feature Priority**: Are any P3 features required for initial launch, or can all be deferred?
   - **Recommendation**: Defer all P3 features to post-launch (focus on P0-P2)

---

## Testing Strategy

### Unit Testing
- **Target**: 80% code coverage
- **Focus Areas**: Services, Storage, Network layer, Models, ViewModels
- **Tools**: XCTest, Mocking frameworks
- **CI Integration**: Run on every pull request

### UI Testing
- **Target**: All critical flows covered
- **Focus Areas**: Registration, Login, Test-taking, Results, Deep linking
- **Tools**: XCTest UI Testing
- **CI Integration**: Run on every pull request, may be slower

### Integration Testing
- **Focus Areas**: Token refresh under load, Offline/online transitions, Background/foreground transitions
- **Tools**: XCTest with real network mocking

### Manual Testing
- **Accessibility**: VoiceOver walkthrough of all screens
- **Visual QA**: All screens at all device sizes
- **Performance**: Memory leaks, battery usage, network efficiency
- **Edge Cases**: Low connectivity, expired tokens, concurrent sessions

### TestFlight Beta Testing
- **Participants**: 20-50 beta testers
- **Focus**: Real-world usage, crash reporting validation, feedback collection

---

## Appendix

### Task Complexity Definitions

- **Small**: 1-4 hours, single file change, low risk, no dependencies
- **Medium**: 4-8 hours, multiple files, moderate risk, some dependencies
- **Large**: 1-3 days, significant changes, high risk, complex dependencies

### Dependencies on Other Teams

**Backend Team:**
- ICG-004: Analytics events endpoint (`/v1/analytics/events`)
- ICG-032: Account deletion endpoint (`/v1/user/delete-account`)
- ICG-080: Feedback submission endpoint (`/v1/feedback/submit`)

**Legal/Compliance:**
- ICG-029: Privacy policy review and approval
- ICG-030: Terms of service review and approval
- ICG-076: Onboarding content review

**Design/Marketing:**
- ICG-074: Onboarding screen designs
- ICG-076: Onboarding content copywriting
- ICG-033: App Store screenshots and metadata

### Success Metrics

**Code Quality:**
- Code coverage: 80%+
- SwiftLint warnings: 0
- Memory leaks: 0
- Crashlytics crash-free rate: 99%+

**Accessibility:**
- VoiceOver navigation: 100% of screens accessible
- Color contrast: 100% WCAG AA compliant
- Touch targets: 100% meet 44x44pt minimum

**Performance:**
- App launch time: < 2 seconds
- Network request timeout: < 10 seconds
- Test-taking flow completion rate: > 90%

**User Experience:**
- Onboarding completion rate: > 80%
- Test completion rate: > 85%
- Push notification opt-in rate: > 60%

---

**Document Version:** 1.1
**Created:** 2025-12-23
**Author:** Technical Product Manager
**Status:** Ready for Implementation
**Next Review:** After Phase 0-1 completion
