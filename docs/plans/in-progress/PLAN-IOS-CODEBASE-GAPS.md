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

## Implementation Plan

### Phase 0: Critical Bug Fixes (Immediate - 0.5 days)

**Goal**: Eliminate production-breaking bugs before any other work
**Duration**: 4 hours

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-001 | Fix AppConfig URL bug - Remove `/v1` from base URL to prevent double path segments | None | Small | `Utilities/Helpers/AppConfig.swift` |

**Acceptance Criteria ICG-001:**
- Base URL changed from `https://aiq-backend-production.up.railway.app/v1` to `https://aiq-backend-production.up.railway.app`
- All API endpoints tested and working (login, registration, test start, test submit)
- No breaking changes to existing API calls

---

### Phase 1: Production Infrastructure (Week 1 - 5 days)

**Goal**: Establish crash reporting and analytics backend integration for production visibility
**Duration**: 5 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-002 | Integrate Firebase Crashlytics SDK - Add SPM dependency, initialize in `AIQApp.swift`, test crash reporting | ICG-001 | Medium | `AIQApp.swift`, `Package.swift` |
| ICG-003 | Create Firebase project and configure iOS app - Download GoogleService-Info.plist, configure APNs certificates | ICG-002 | Small | New: `GoogleService-Info.plist` |
| ICG-004 | Update AnalyticsService to send events to backend `/v1/analytics/events` endpoint | ICG-001 | Medium | `Services/Analytics/AnalyticsService.swift` |
| ICG-005 | Add Crashlytics logging to all ViewModel error handlers - Replace OSLog with Crashlytics.recordError() in catch blocks | ICG-002, ICG-003 | Medium | All ViewModels |
| ICG-006 | Test crash reporting in TestFlight build - Force crash, verify appears in Firebase console | ICG-002, ICG-003, ICG-005 | Small | Test only |

**Acceptance Criteria ICG-002:**
- Firebase SDK integrated via Swift Package Manager
- Crashlytics initialized in app launch
- Test crash successfully reported to Firebase console

**Acceptance Criteria ICG-003:**
- Firebase project created with iOS app configuration
- GoogleService-Info.plist added to Xcode project
- Build succeeds with Firebase integration

**Acceptance Criteria ICG-004:**
- AnalyticsService sends events to backend API
- Event payloads match backend schema
- Network errors handled gracefully with retry logic
- Events logged locally if offline (queue for later sync)

**Acceptance Criteria ICG-005:**
- All ViewModel error handlers record non-fatal errors to Crashlytics
- User-facing errors still logged to OSLog for debugging
- No duplicate error logging

**Acceptance Criteria ICG-006:**
- TestFlight build uploaded with Crashlytics enabled
- Forced crash appears in Firebase console within 5 minutes
- Crash report includes stack trace and device metadata

---

### Phase 2: Deep Linking & Navigation (Week 2 - 5 days)

**Goal**: Implement centralized navigation and deep linking to enable notification-driven user flows
**Duration**: 5 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-007 | Create AppRouter with NavigationPath-based coordinator pattern | None | Large | New: `Services/Navigation/AppRouter.swift` |
| ICG-008 | Create DeepLinkHandler to parse URL schemes and universal links | None | Medium | New: `Services/Navigation/DeepLinkHandler.swift` |
| ICG-009 | Register URL schemes in Info.plist - Add `aiq://` custom scheme | None | Small | `Info.plist` |
| ICG-010 | Configure universal links - Add Associated Domains entitlement for `applinks:aiq.app` | ICG-009 | Small | `AIQ.entitlements`, Apple Developer Portal |
| ICG-011 | Integrate AppRouter into AIQApp.swift - Replace root view navigation with router | ICG-007 | Medium | `AIQApp.swift` |
| ICG-012 | Migrate DashboardView navigation to use AppRouter | ICG-007, ICG-011 | Medium | `Views/Dashboard/DashboardView.swift` |
| ICG-013 | Migrate TestTakingView navigation to use AppRouter | ICG-007, ICG-011 | Medium | `Views/Test/TestTakingView.swift` |
| ICG-014 | Migrate HistoryView navigation to use AppRouter | ICG-007, ICG-011 | Medium | `Views/History/HistoryView.swift` |
| ICG-015 | Migrate SettingsView navigation to use AppRouter | ICG-007, ICG-011 | Medium | `Views/Settings/SettingsView.swift` |
| ICG-016 | Implement deep link handling in AppDelegate - Handle `application(_:open:options:)` | ICG-008, ICG-009, ICG-010 | Medium | `AppDelegate.swift` |
| ICG-017 | Add deep link routes: `aiq://test/results/{id}`, `aiq://test/resume/{sessionId}`, `aiq://settings` | ICG-008, ICG-016 | Medium | `Services/Navigation/DeepLinkHandler.swift` |
| ICG-018 | Test deep links from push notifications - Verify notification tap navigates correctly | ICG-016, ICG-017 | Small | Test only |

**Acceptance Criteria ICG-007:**
- AppRouter class created with NavigationPath state management
- Router supports push, pop, popToRoot, and direct navigation methods
- Router is observable and injectable via environment

**Acceptance Criteria ICG-008:**
- DeepLinkHandler parses URL schemes (aiq://)
- DeepLinkHandler parses universal links (https://aiq.app/...)
- Returns structured DeepLink enum with associated data

**Acceptance Criteria ICG-009:**
- `aiq://` URL scheme registered in Info.plist
- App responds to `aiq://` URLs from Safari and other apps

**Acceptance Criteria ICG-010:**
- Associated Domains entitlement added
- Universal link domain verified in Apple Developer Portal
- App responds to `https://aiq.app/...` links

**Acceptance Criteria ICG-011:**
- AppRouter initialized in AIQApp.swift
- Router injected into environment
- Root navigation controlled by router

**Acceptance Criteria ICG-012-015:**
- All sheet/fullScreenCover modifiers replaced with router calls
- Navigation state removed from ViewModels
- Back navigation works correctly
- Deep state restoration supported

**Acceptance Criteria ICG-016:**
- AppDelegate handles URL opening callbacks
- URLs parsed by DeepLinkHandler
- Router navigates to correct destination

**Acceptance Criteria ICG-017:**
- All three route types implemented and tested
- Invalid routes handled gracefully with error state
- Routes work from cold start and background state

**Acceptance Criteria ICG-018:**
- Push notification tap opens app to correct screen
- Notification payload structure tested
- Works in foreground, background, and terminated states

---

### Phase 3: UI Testing Infrastructure (Week 3 - 5 days)

**Goal**: Create UI test target and cover all critical user flows with automated tests
**Duration**: 5 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-019 | Create AIQUITests target in Xcode - Configure test host, bundle ID, signing | None | Small | New: `AIQUITests/` directory |
| ICG-020 | Create UI test helpers - LoginHelper, TestTakingHelper, NavigationHelper | ICG-019 | Medium | New: `AIQUITests/Helpers/` |
| ICG-021 | Write registration flow UI test - Complete registration from start to dashboard | ICG-019, ICG-020 | Medium | New: `AIQUITests/RegistrationFlowTests.swift` |
| ICG-022 | Write login/logout flow UI test - Login, verify dashboard, logout, verify welcome screen | ICG-019, ICG-020 | Medium | New: `AIQUITests/AuthenticationFlowTests.swift` |
| ICG-023 | Write test-taking flow UI test - Start test, answer all questions, submit, verify results | ICG-019, ICG-020 | Large | New: `AIQUITests/TestTakingFlowTests.swift` |
| ICG-024 | Write test abandonment UI test - Start test, abandon, verify can resume | ICG-019, ICG-020 | Medium | New: `AIQUITests/TestAbandonmentTests.swift` |
| ICG-025 | Write deep link navigation UI test - Test all deep link routes from terminated state | ICG-017, ICG-019, ICG-020 | Medium | New: `AIQUITests/DeepLinkTests.swift` |
| ICG-026 | Write error state handling UI test - Network errors, invalid responses, retry logic | ICG-019, ICG-020 | Medium | New: `AIQUITests/ErrorHandlingTests.swift` |
| ICG-027 | Configure UI tests in CI/CD - Add to GitHub Actions or Xcode Cloud | ICG-019 | Small | `.github/workflows/ios-tests.yml` |

**Acceptance Criteria ICG-019:**
- AIQUITests target created with correct configuration
- Test target builds successfully
- Can run UI tests from Xcode

**Acceptance Criteria ICG-020:**
- LoginHelper provides authenticated test sessions
- TestTakingHelper handles test data setup
- NavigationHelper verifies screen transitions
- Helpers reduce test boilerplate

**Acceptance Criteria ICG-021:**
- Test completes full registration flow
- Validates field validation errors
- Verifies successful registration leads to dashboard
- Runs reliably without flakiness

**Acceptance Criteria ICG-022:**
- Test covers login with valid credentials
- Test covers login with invalid credentials
- Test covers logout flow
- Verifies session persistence

**Acceptance Criteria ICG-023:**
- Test starts a new test session
- Test answers all questions (mocked question data)
- Test submits answers and verifies results screen
- Verifies score display and history update

**Acceptance Criteria ICG-024:**
- Test starts test and abandons mid-flow
- Test verifies saved progress
- Test resumes test and completes
- Verifies no data loss on abandonment

**Acceptance Criteria ICG-025:**
- Test all deep link routes (results, resume, settings)
- Test from app terminated state
- Test from app backgrounded state
- Verifies correct screen displayed

**Acceptance Criteria ICG-026:**
- Test network error handling with retry
- Test invalid API response handling
- Test timeout scenarios
- Verifies user-facing error messages

**Acceptance Criteria ICG-027:**
- UI tests run automatically on pull requests
- Test failures block merge
- Test reports uploaded as artifacts

---

### Phase 4: Privacy & Compliance (Week 4 - 3 days)

**Goal**: Meet App Store privacy and compliance requirements
**Duration**: 3 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-028 | Create PrivacyInfo.xcprivacy manifest - Declare data collection and usage | None | Small | New: `PrivacyInfo.xcprivacy` |
| ICG-029 | Draft privacy policy document - Cover data collection, storage, sharing, deletion | None | Medium | External: Privacy policy website/PDF |
| ICG-030 | Draft terms of service document - User agreements, disclaimers, liability | None | Medium | External: Terms of service website/PDF |
| ICG-031 | Implement consent management screen - Display privacy policy, require acceptance on first launch | ICG-029 | Medium | New: `Views/Onboarding/PrivacyConsentView.swift` |
| ICG-032 | Add data deletion capability - Settings option to delete account and all data | None | Medium | `Views/Settings/SettingsView.swift`, Backend: New endpoint `/v1/user/delete-account` |
| ICG-033 | Update App Store metadata - Privacy questions, data usage descriptions, screenshots | ICG-028, ICG-029, ICG-030 | Small | App Store Connect |

**Acceptance Criteria ICG-028:**
- PrivacyInfo.xcprivacy created with all required fields
- Declares analytics, crash reporting, authentication data
- Passes App Store privacy validation

**Acceptance Criteria ICG-029:**
- Privacy policy covers all data collected
- Explains data retention and deletion
- Complies with GDPR and CCPA requirements
- Hosted at publicly accessible URL

**Acceptance Criteria ICG-030:**
- Terms of service cover liability disclaimers
- Addresses intellectual property
- Hosted at publicly accessible URL
- Legal review completed

**Acceptance Criteria ICG-031:**
- Privacy consent screen shown on first launch
- User must accept to continue
- Consent timestamp stored locally
- Links to full privacy policy and terms

**Acceptance Criteria ICG-032:**
- Settings screen includes "Delete Account" option
- Confirmation dialog warns of irreversible action
- Backend endpoint deletes all user data (GDPR right to erasure)
- User logged out and returned to welcome screen

**Acceptance Criteria ICG-033:**
- App Store Connect metadata updated
- Privacy questions answered accurately
- Screenshots show current UI
- App description mentions privacy compliance

---

### Phase 5: Localization Infrastructure (Week 4-5 - 3 days)

**Goal**: Prepare app for internationalization and localization
**Duration**: 3 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-034 | Create Localizable.strings file for English (base localization) | None | Medium | New: `en.lproj/Localizable.strings` |
| ICG-035 | Create String+Localization extension - Add `.localized` helper for string keys | None | Small | `Utilities/Extensions/String+Localization.swift` |
| ICG-036 | Extract all hardcoded strings from Views to Localizable.strings | ICG-034, ICG-035 | Large | All View files |
| ICG-037 | Extract all hardcoded strings from ViewModels to Localizable.strings | ICG-034, ICG-035 | Medium | All ViewModel files |
| ICG-038 | Extract all error messages to Localizable.strings | ICG-034, ICG-035 | Medium | All Service files |
| ICG-039 | Add RTL (Right-to-Left) layout support - Test with Arabic/Hebrew simulators | ICG-036 | Small | Test only |
| ICG-040 | Configure locale-aware date/number formatting - Ensure all formatters respect user locale | ICG-036 | Small | `Utilities/Extensions/Date+Extensions.swift` |

**Acceptance Criteria ICG-034:**
- Localizable.strings file created in Xcode
- All strings have unique keys
- Base localization (English) complete

**Acceptance Criteria ICG-035:**
- String extension provides `.localized` computed property
- Extension handles missing keys gracefully
- Works with string interpolation

**Acceptance Criteria ICG-036:**
- All user-facing strings in Views use localization keys
- No hardcoded English strings remain
- App builds and runs with localized strings

**Acceptance Criteria ICG-037:**
- All user-facing strings in ViewModels use localization
- Validation messages localized
- Success/error messages localized

**Acceptance Criteria ICG-038:**
- All error messages use localization keys
- Error codes preserved for debugging
- User-friendly error messages in all cases

**Acceptance Criteria ICG-039:**
- App layout tested in RTL languages
- No UI overlaps or truncation
- Navigation behaves correctly in RTL

**Acceptance Criteria ICG-040:**
- DateFormatter respects user locale
- Number formatting uses locale-specific separators
- Currency formatting works for all supported locales

---

### Phase 6: Security Hardening (Week 5 - 3 days)

**Goal**: Eliminate security vulnerabilities before App Store submission
**Duration**: 3 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-041 | Wrap sensitive logging in DEBUG guards - Email, tokens, user data | None | Medium | `Services/Auth/AuthService.swift` (lines 42-45, 70-73, 99-103) |
| ICG-042 | Audit all OSLog calls for sensitive data - Remove or wrap in DEBUG | ICG-041 | Medium | All files with OSLog usage |
| ICG-043 | Integrate TrustKit for certificate pinning | None | Medium | `AIQApp.swift`, New: `TrustKit.plist` |
| ICG-044 | Configure production SSL certificate pins - Extract public key hashes from Railway certificates | ICG-043 | Small | `TrustKit.plist` |
| ICG-045 | Test certificate pinning - Verify blocks MITM attacks, allows valid certificates | ICG-043, ICG-044 | Small | Test with proxy tool (Charles/mitmproxy) |
| ICG-046 | Add environment-specific pinning config - Disable pinning in DEBUG builds | ICG-043, ICG-044 | Small | `TrustKit.plist`, `AppConfig.swift` |

**Acceptance Criteria ICG-041:**
- All email logging wrapped in `#if DEBUG` blocks
- All token logging wrapped in `#if DEBUG` blocks
- All user PII logging wrapped in `#if DEBUG` blocks
- Production builds log no sensitive data

**Acceptance Criteria ICG-042:**
- Full codebase audit completed
- Spreadsheet/report of all logging calls created
- All sensitive logging wrapped or removed
- Non-sensitive logging preserved for debugging

**Acceptance Criteria ICG-043:**
- TrustKit integrated via Swift Package Manager
- TrustKit.plist configuration file created
- TrustKit initialized in app launch

**Acceptance Criteria ICG-044:**
- Production backend SSL certificate analyzed
- Public key hashes extracted and configured
- Backup pins configured for rotation safety
- Pin expiration dates documented

**Acceptance Criteria ICG-045:**
- Valid certificates accepted (app works normally)
- Invalid certificates rejected (network calls fail)
- Self-signed certificates blocked
- MITM proxy blocked

**Acceptance Criteria ICG-046:**
- DEBUG builds skip certificate pinning
- RELEASE builds enforce certificate pinning
- Staging environment uses separate pin config
- Environment switching tested

---

### Phase 7: Test Coverage Expansion (Week 6 - 5 days)

**Goal**: Achieve 80% code coverage with comprehensive unit tests
**Duration**: 5 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-047 | Write unit tests for AuthService - Login, logout, registration, token refresh | None | Medium | New: `AIQTests/Services/AuthServiceTests.swift` |
| ICG-048 | Write unit tests for NotificationService - Device registration, preference updates | None | Medium | New: `AIQTests/Services/NotificationServiceTests.swift` |
| ICG-049 | Write unit tests for NotificationManager - Scheduling, permission handling | None | Medium | New: `AIQTests/Services/NotificationManagerTests.swift` |
| ICG-050 | Write unit tests for AnalyticsService - Event tracking, backend sync | None | Medium | New: `AIQTests/Services/AnalyticsServiceTests.swift` |
| ICG-051 | Write unit tests for KeychainStorage - Token storage, retrieval, deletion | None | Medium | New: `AIQTests/Storage/KeychainStorageTests.swift` |
| ICG-052 | Write unit tests for LocalAnswerStorage - Answer persistence, retrieval | None | Medium | New: `AIQTests/Storage/LocalAnswerStorageTests.swift` |
| ICG-053 | Write unit tests for DataCache - Cache storage, expiration, invalidation | None | Medium | New: `AIQTests/Storage/DataCacheTests.swift` |
| ICG-054 | Write unit tests for RetryPolicy - Exponential backoff, max retries | None | Small | New: `AIQTests/Network/RetryPolicyTests.swift` |
| ICG-055 | Write unit tests for TokenRefreshInterceptor - Concurrent request handling, race conditions | None | Medium | New: `AIQTests/Network/TokenRefreshInterceptorTests.swift` |
| ICG-056 | Write unit tests for NetworkMonitor - Connection status changes | None | Small | New: `AIQTests/Network/NetworkMonitorTests.swift` |
| ICG-057 | Write unit tests for User model - Validation, serialization | None | Small | New: `AIQTests/Models/UserTests.swift` |
| ICG-058 | Write unit tests for Question model - Validation, answer checking | None | Small | New: `AIQTests/Models/QuestionTests.swift` |
| ICG-059 | Write unit tests for TestSession model - Status transitions, validation | None | Small | New: `AIQTests/Models/TestSessionTests.swift` |
| ICG-060 | Run code coverage report and identify remaining gaps | ICG-047 to ICG-059 | Small | Xcode coverage tool |
| ICG-061 | Write additional tests to reach 80% coverage target | ICG-060 | Medium | Various test files |

**Acceptance Criteria ICG-047:**
- All AuthService methods tested
- Success and error cases covered
- Mock APIClient used for isolation
- Edge cases tested (expired tokens, network errors)

**Acceptance Criteria ICG-048-050:**
- All public methods tested
- Success and error paths covered
- Dependencies mocked
- Async operations tested correctly

**Acceptance Criteria ICG-051-053:**
- All storage operations tested
- Data persistence verified
- Error handling tested
- Concurrent access tested

**Acceptance Criteria ICG-054-056:**
- All network layer logic tested
- Edge cases covered
- Threading safety verified
- Mock URLSession used

**Acceptance Criteria ICG-057-059:**
- All model validation tested
- Serialization/deserialization tested
- Edge cases covered
- Invalid data handled

**Acceptance Criteria ICG-060:**
- Code coverage report generated
- Coverage percentage by file documented
- Gaps identified and prioritized

**Acceptance Criteria ICG-061:**
- Code coverage reaches 80% or higher
- Critical paths have 100% coverage
- Remaining gaps documented with justification

---

### Phase 8: Accessibility Audit (Week 7 - 4 days)

**Goal**: Ensure WCAG AA compliance and excellent VoiceOver experience
**Duration**: 4 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-062 | Audit all views with VoiceOver - Test every screen with VoiceOver enabled | None | Large | Test audit (documentation only) |
| ICG-063 | Add accessibility labels to all interactive elements | ICG-062 | Medium | All View files |
| ICG-064 | Add accessibility hints for non-obvious interactions | ICG-062 | Small | All View files |
| ICG-065 | Verify color contrast meets WCAG AA standards - Use contrast checker tool | None | Small | `Utilities/Design/ColorPalette.swift` |
| ICG-066 | Fix any color contrast failures - Adjust colors to meet 4.5:1 ratio | ICG-065 | Small | `Utilities/Design/ColorPalette.swift` |
| ICG-067 | Verify touch targets meet 44x44pt minimum - Audit all buttons and interactive elements | None | Small | All View files |
| ICG-068 | Fix undersized touch targets - Add padding or minimum frame sizes | ICG-067 | Small | All View files |
| ICG-069 | Test Dynamic Type support - Verify all text scales correctly at all sizes | None | Medium | All View files |
| ICG-070 | Fix Dynamic Type issues - Use relative spacing, avoid fixed heights | ICG-069 | Medium | All View files |
| ICG-071 | Test Reduce Motion support - Verify animations respect accessibility settings | None | Small | All animated views |
| ICG-072 | Add Reduce Motion alternatives - Disable or simplify animations when enabled | ICG-071 | Small | All animated views |
| ICG-073 | Document accessibility features in App Store metadata | ICG-062 to ICG-072 | Small | App Store Connect |

**Acceptance Criteria ICG-062:**
- All screens tested with VoiceOver
- Navigation flow logical and clear
- All interactive elements reachable
- Issues documented with severity

**Acceptance Criteria ICG-063:**
- All buttons have descriptive labels
- All images have alt text
- Form fields have labels
- No unlabeled interactive elements

**Acceptance Criteria ICG-064:**
- Non-obvious gestures have hints
- Complex interactions explained
- Hints concise and helpful

**Acceptance Criteria ICG-065:**
- All color combinations tested
- Contrast ratios documented
- Failing combinations identified

**Acceptance Criteria ICG-066:**
- All color contrast meets 4.5:1 for normal text
- All color contrast meets 3:1 for large text
- Visual design preserved where possible

**Acceptance Criteria ICG-067:**
- All buttons and tap targets measured
- Undersized targets documented
- Priority list created

**Acceptance Criteria ICG-068:**
- All touch targets 44x44pt or larger
- No tappable elements too small
- Visual design preserved

**Acceptance Criteria ICG-069:**
- App tested at all Dynamic Type sizes (XS to XXXL)
- Text truncation issues identified
- Layout issues documented

**Acceptance Criteria ICG-070:**
- All text scales without truncation
- Layouts adapt to large text
- Scrollable regions used where needed

**Acceptance Criteria ICG-071:**
- All animations tested with Reduce Motion enabled
- Disorienting animations identified

**Acceptance Criteria ICG-072:**
- Animations disabled or simplified when Reduce Motion enabled
- Transitions remain functional
- User experience preserved

**Acceptance Criteria ICG-073:**
- Accessibility features listed in App Store description
- VoiceOver support highlighted
- Dynamic Type support mentioned

---

### Phase 9: User Experience Enhancements (Week 8 - 3 days)

**Goal**: Improve first-run experience and user feedback mechanisms
**Duration**: 3 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-074 | Design onboarding flow - 3-4 screens explaining app value and test mechanics | None | Small | Design mockups |
| ICG-075 | Create OnboardingView with page indicators and skip option | ICG-074 | Medium | New: `Views/Onboarding/OnboardingView.swift` |
| ICG-076 | Create onboarding content - App value, test mechanics, recommended frequency, privacy | ICG-075 | Small | `Views/Onboarding/OnboardingView.swift` |
| ICG-077 | Integrate onboarding into first-launch flow - Show after registration or on first open | ICG-075, ICG-076 | Small | `AIQApp.swift` |
| ICG-078 | Add "View Onboarding Again" option to Settings | ICG-075 | Small | `Views/Settings/SettingsView.swift` |
| ICG-079 | Create FeedbackView with form fields - Name, email, category, description | None | Medium | New: `Views/Settings/FeedbackView.swift` |
| ICG-080 | Implement feedback submission to backend - New endpoint `/v1/feedback/submit` | ICG-079 | Medium | Backend: New endpoint, iOS: `Views/Settings/FeedbackView.swift` |
| ICG-081 | Add "Send Feedback" option to Settings menu | ICG-079 | Small | `Views/Settings/SettingsView.swift` |

**Acceptance Criteria ICG-074:**
- Onboarding flow designed with 3-4 screens
- Content finalized and approved
- Illustrations or graphics sourced

**Acceptance Criteria ICG-075:**
- OnboardingView created with SwiftUI TabView
- Page indicators show progress
- Skip button allows bypassing
- "Get Started" button on final screen

**Acceptance Criteria ICG-076:**
- Screen 1: App value proposition
- Screen 2: How tests work
- Screen 3: Recommended 3-month frequency
- Screen 4: Privacy and data handling

**Acceptance Criteria ICG-077:**
- Onboarding shown on first launch after registration
- Onboarding shown on first launch for existing users (migration)
- Flag stored to prevent repeated display

**Acceptance Criteria ICG-078:**
- Settings includes "View Onboarding Again" option
- Tapping option displays onboarding flow
- User can skip through quickly

**Acceptance Criteria ICG-079:**
- Feedback form includes all required fields
- Form validation prevents empty submissions
- Category dropdown includes common feedback types

**Acceptance Criteria ICG-080:**
- Backend endpoint created and tested
- Feedback stored in database
- Email notification sent to admin
- Success/error handling in iOS app

**Acceptance Criteria ICG-081:**
- Settings menu includes "Send Feedback" option
- Tapping option navigates to FeedbackView
- Submission shows success confirmation

---

### Phase 10: Code Quality - Redundancy Elimination (Week 9 - 4 days)

**Goal**: Eliminate code duplication and improve maintainability
**Duration**: 4 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-082 | Consolidate email validation - Use `String+Extensions.swift` consistently | None | Small | `ViewModels/LoginViewModel.swift`, `ViewModels/RegistrationViewModel.swift` |
| ICG-083 | Consolidate password validation - Use `Validators.swift` or create shared validator | None | Small | `ViewModels/LoginViewModel.swift`, `ViewModels/RegistrationViewModel.swift` |
| ICG-084 | Extract IQ score classification to shared utility - Create `IQScoreUtility.swift` | None | Small | New: `Utilities/Helpers/IQScoreUtility.swift`, `Views/Test/TestResultsView.swift`, `Views/History/TestDetailView+Helpers.swift` |
| ICG-085 | Remove duplicate IQ classification code from views | ICG-084 | Small | `Views/Test/TestResultsView.swift`, `Views/History/TestDetailView+Helpers.swift` |
| ICG-086 | Audit DateFormatter usage - Identify all instances creating formatters | None | Small | Documentation only |
| ICG-087 | Migrate to Date+Extensions helpers - Replace formatter creation with extension methods | ICG-086 | Medium | `ViewModels/DashboardViewModel.swift`, `Views/Test/TestResultsView.swift`, `Views/History/IQTrendChart.swift`, others |
| ICG-088 | Create reusable InfoCard component - Extract from WelcomeView and RegistrationView | None | Medium | New: `Views/Common/InfoCard.swift` |
| ICG-089 | Replace FeatureCard with InfoCard in WelcomeView | ICG-088 | Small | `Views/Auth/WelcomeView.swift` |
| ICG-090 | Replace RegistrationBenefitCard with InfoCard in RegistrationView | ICG-088 | Small | `Views/Auth/RegistrationView.swift` |

**Acceptance Criteria ICG-082:**
- All email validation uses single implementation
- Validation logic identical across all call sites
- Unit tests verify validation consistency

**Acceptance Criteria ICG-083:**
- All password validation uses single implementation
- Validation rules identical across all call sites
- Password requirements documented

**Acceptance Criteria ICG-084:**
- IQScoreUtility.swift created with classification method
- Method accepts IQ score, returns category and color
- Unit tests verify all score ranges

**Acceptance Criteria ICG-085:**
- TestResultsView uses IQScoreUtility
- TestDetailView+Helpers uses IQScoreUtility
- Duplicate switch statements removed
- Visual output identical to before

**Acceptance Criteria ICG-086:**
- All DateFormatter usage documented
- Call sites categorized by format type
- Migration plan created

**Acceptance Criteria ICG-087:**
- All DateFormatter creation replaced with extensions
- Date formatting consistent across app
- Performance improved (fewer formatter allocations)

**Acceptance Criteria ICG-088:**
- InfoCard component supports title, description, icon
- Component supports customization (colors, sizing)
- Component previews created

**Acceptance Criteria ICG-089-090:**
- WelcomeView uses InfoCard
- RegistrationView uses InfoCard
- Visual output identical to before
- Code duplication eliminated

---

### Phase 11: Code Quality - Architecture Fixes (Week 9-10 - 3 days)

**Goal**: Fix architectural issues (StateObject misuse, race conditions, retain cycles)
**Duration**: 3 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-091 | Fix StateObject misuse in DashboardView - Change to @ObservedObject for singleton | None | Small | `Views/Dashboard/DashboardView.swift` |
| ICG-092 | Convert TokenRefreshInterceptor to actor - Eliminate race condition on concurrent requests | None | Medium | `Services/Auth/TokenRefreshInterceptor.swift` |
| ICG-093 | Test TokenRefreshInterceptor thread safety - Concurrent request stress test | ICG-092 | Small | New: `AIQTests/Network/TokenRefreshInterceptorConcurrencyTests.swift` |
| ICG-094 | Fix retain cycle in DashboardViewModel - Add [weak self] to retry closure | None | Small | `ViewModels/DashboardViewModel.swift` |
| ICG-095 | Audit all timer closures for retain cycles - Search for Timer usage without weak self | None | Small | Documentation only |
| ICG-096 | Fix timer retain cycles - Add [weak self] to all timer closures | ICG-095 | Small | Various ViewModel files |
| ICG-097 | Run memory leak detection - Use Xcode Instruments to verify no leaks | ICG-094, ICG-096 | Small | Test only |

**Acceptance Criteria ICG-091:**
- DashboardView uses @ObservedObject instead of @StateObject
- AuthManager.shared still works correctly
- No duplicate instances created

**Acceptance Criteria ICG-092:**
- TokenRefreshInterceptor converted to Swift actor
- All properties accessed via async/await
- Compilation succeeds

**Acceptance Criteria ICG-093:**
- Stress test creates 10+ concurrent requests
- Token refresh only happens once
- No race condition errors
- All requests succeed

**Acceptance Criteria ICG-094:**
- Retry closure uses [weak self]
- Memory leak resolved
- Functionality unchanged

**Acceptance Criteria ICG-095:**
- All Timer usage documented
- Retain cycle risks identified
- Priority fixes listed

**Acceptance Criteria ICG-096:**
- All timer closures use [weak self]
- No compiler warnings
- Functionality unchanged

**Acceptance Criteria ICG-097:**
- Instruments Leaks tool run on app
- No memory leaks detected
- Memory graph verified clean

---

### Phase 12: Code Quality - Magic Numbers (Week 10 - 2 days)

**Goal**: Extract magic numbers to named constants for maintainability
**Duration**: 2 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-098 | Create Constants.swift file - Organize by domain (Timing, Network, Test) | None | Small | New: `Utilities/Helpers/Constants.swift` |
| ICG-099 | Extract timer critical threshold (60 seconds) to constant | ICG-098 | Small | `ViewModels/TestTimerManager.swift`, `Utilities/Helpers/Constants.swift` |
| ICG-100 | Extract slow request threshold (2.0 seconds) to constant | ICG-098 | Small | `Services/API/APIClient.swift`, `Utilities/Helpers/Constants.swift` |
| ICG-101 | Extract auto-save delay (1.0 seconds) to constant | ICG-098 | Small | `ViewModels/TestTakingViewModel.swift`, `Utilities/Helpers/Constants.swift` |
| ICG-102 | Extract progress validity (24 hours) to constant | ICG-098 | Small | `Models/SavedTestProgress.swift`, `Utilities/Helpers/Constants.swift` |
| ICG-103 | Audit codebase for additional magic numbers | ICG-098 | Small | Documentation only |
| ICG-104 | Extract remaining magic numbers to constants | ICG-103 | Small | Various files |

**Acceptance Criteria ICG-098:**
- Constants.swift file created
- Organized into nested structs by domain
- Documentation comments explain each constant

**Acceptance Criteria ICG-099-102:**
- Magic number replaced with named constant
- Constant value identical to original
- All references updated
- Code more readable

**Acceptance Criteria ICG-103:**
- Full codebase search completed
- Magic numbers categorized by priority
- List of remaining numbers documented

**Acceptance Criteria ICG-104:**
- All high-priority magic numbers extracted
- Constants well-named and documented
- Code maintainability improved

---

### Phase 13: Code Quality - Final Touches (Week 10 - 2 days)

**Goal**: Address remaining code quality issues
**Duration**: 2 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-105 | Add birth year validation to RegistrationViewModel - Validate 1900 <= year <= currentYear | None | Small | `ViewModels/RegistrationViewModel.swift` |
| ICG-106 | Create ServiceContainer for dependency injection | None | Medium | New: `Utilities/DI/ServiceContainer.swift` |
| ICG-107 | Migrate ViewModels to use ServiceContainer - Inject dependencies instead of singletons | ICG-106 | Medium | All ViewModels |
| ICG-108 | Create environment key for ServiceContainer | ICG-106 | Small | `Utilities/DI/ServiceContainer.swift` |
| ICG-109 | Inject ServiceContainer into app environment | ICG-106, ICG-108 | Small | `AIQApp.swift` |

**Acceptance Criteria ICG-105:**
- Birth year validation added to ViewModel
- Rejects years before 1900
- Rejects years after current year
- User-friendly error message displayed

**Acceptance Criteria ICG-106:**
- ServiceContainer class created
- Supports registration and resolution of dependencies
- Thread-safe implementation
- Supports protocol-based injection

**Acceptance Criteria ICG-107:**
- All ViewModels accept dependencies via initializer
- No direct singleton usage in ViewModels
- Testability improved
- Functionality unchanged

**Acceptance Criteria ICG-108:**
- Environment key created for ServiceContainer
- SwiftUI environment integration working

**Acceptance Criteria ICG-109:**
- ServiceContainer initialized in AIQApp.swift
- All services registered
- Injected into environment
- App launches successfully

---

### Phase 14: P2 Enhancements - Offline & State (Week 11 - 3 days)

**Goal**: Improve offline capabilities and state persistence
**Duration**: 3 days

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-110 | Create operation queue for offline mutations - Queue profile updates, settings changes | None | Large | New: `Services/Storage/OfflineOperationQueue.swift` |
| ICG-111 | Implement background sync for offline operations - Sync when network returns | ICG-110 | Medium | `Services/Storage/OfflineOperationQueue.swift` |
| ICG-112 | Add retry logic for failed mutations | ICG-110 | Medium | `Services/Storage/OfflineOperationQueue.swift` |
| ICG-113 | Create AppStateStorage for UI state persistence | None | Medium | New: `Services/Storage/AppStateStorage.swift` |
| ICG-114 | Persist tab selection across app launches | ICG-113 | Small | `Views/MainTabView.swift` |
| ICG-115 | Persist filter preferences in HistoryView | ICG-113 | Small | `Views/History/HistoryView.swift` |
| ICG-116 | Persist scroll positions in long lists (optional, nice-to-have) | ICG-113 | Small | Various list views |

**Acceptance Criteria ICG-110:**
- OfflineOperationQueue created
- Supports queuing mutations when offline
- Persists queue to disk
- Operations have retry logic

**Acceptance Criteria ICG-111:**
- Queue monitors network status
- Syncs operations when network returns
- Handles conflicts gracefully
- User notified of sync status

**Acceptance Criteria ICG-112:**
- Failed operations retry with exponential backoff
- Max retry limit enforced
- Permanently failed operations reported to user

**Acceptance Criteria ICG-113:**
- AppStateStorage created with UserDefaults backend
- Supports reading/writing various state types
- Type-safe API

**Acceptance Criteria ICG-114:**
- Selected tab saved on change
- Restored on app launch
- Defaults to dashboard if no saved state

**Acceptance Criteria ICG-115:**
- Filter selections saved on change
- Restored on view appear
- Defaults to "All" if no saved state

**Acceptance Criteria ICG-116:**
- Scroll position saved for long lists
- Restored on view appear (if feasible with SwiftUI)
- Degrades gracefully if not possible

---

### Phase 15: P3 Enhancements - Nice-to-Have Features (Week 12 - 5 days)

**Goal**: Add polish features for enhanced user experience
**Duration**: 5 days (optional, can be deferred post-launch)

| Task ID | Task | Dependencies | Complexity | Files Affected |
|---------|------|--------------|------------|----------------|
| ICG-117 | Create BiometricAuthManager - Face ID / Touch ID support | None | Medium | New: `Services/Auth/BiometricAuthManager.swift` |
| ICG-118 | Add biometric authentication option to Settings | ICG-117 | Small | `Views/Settings/SettingsView.swift` |
| ICG-119 | Implement biometric auth on app launch | ICG-117, ICG-118 | Medium | `AIQApp.swift` |
| ICG-120 | Create HapticManager for haptic feedback | None | Small | New: `Utilities/Helpers/HapticManager.swift` |
| ICG-121 | Add haptic feedback to button taps | ICG-120 | Small | `Views/Common/PrimaryButton.swift`, others |
| ICG-122 | Add haptic feedback to success/error states | ICG-120 | Small | All ViewModels |
| ICG-123 | Add haptic feedback to timer warnings | ICG-120 | Small | `ViewModels/TestTimerManager.swift` |
| ICG-124 | Optimize layouts for iPad - Multi-column layouts, larger screens | None | Large | All View files |
| ICG-125 | Add keyboard shortcuts for iPad | ICG-124 | Medium | Various views |
| ICG-126 | Add split view support for iPad | ICG-124 | Medium | `AIQApp.swift` |
| ICG-127 | Create widget extension - Show latest score or next test date | None | Large | New: Widget extension target |
| ICG-128 | Add snapshot testing with swift-snapshot-testing | None | Medium | New: Snapshot test files |
| ICG-129 | Add background refresh capability | None | Medium | `AIQApp.swift`, `AppDelegate.swift` |

**Acceptance Criteria ICG-117:**
- BiometricAuthManager supports Face ID and Touch ID
- Handles permission requests
- Fallback to passcode if biometric fails

**Acceptance Criteria ICG-118:**
- Settings toggle for biometric auth
- Disabled if device doesn't support biometrics
- Preference saved securely

**Acceptance Criteria ICG-119:**
- Biometric prompt shown on app launch if enabled
- Successful auth shows app content
- Failed auth shows retry or exit options

**Acceptance Criteria ICG-120:**
- HapticManager provides simple API for common feedback types
- Supports success, error, warning, selection
- Respects system haptic settings

**Acceptance Criteria ICG-121-123:**
- Appropriate haptic feedback added
- Not overused (only meaningful interactions)
- Respects accessibility settings

**Acceptance Criteria ICG-124:**
- Layouts use adaptive sizing
- Multi-column layouts on larger screens
- No awkward stretching on iPad

**Acceptance Criteria ICG-125:**
- Common actions have keyboard shortcuts (Cmd+N, Cmd+R, etc.)
- Shortcuts discoverable
- Don't conflict with system shortcuts

**Acceptance Criteria ICG-126:**
- App supports split view multitasking
- Layouts adapt to narrow widths
- No crashes in split view

**Acceptance Criteria ICG-127:**
- Widget shows latest IQ score
- Widget shows days until next test
- Tapping widget opens app to relevant screen

**Acceptance Criteria ICG-128:**
- Snapshot tests created for key views
- Tests run in CI/CD
- Failures detected on UI changes

**Acceptance Criteria ICG-129:**
- Background refresh fetches new data
- User notified of updates if relevant
- Battery impact minimized

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
- **Duration**: 2 weeks before App Store submission
- **Participants**: 20-50 beta testers
- **Focus**: Real-world usage, crash reporting validation, feedback collection

## Appendix

### Task Complexity Definitions

- **Small**: 1-4 hours, single file change, low risk, no dependencies
- **Medium**: 4-8 hours, multiple files, moderate risk, some dependencies
- **Large**: 1-3 days, significant changes, high risk, complex dependencies

### Estimated Effort Summary

| Priority | Phase | Tasks | Estimated Effort |
|----------|-------|-------|------------------|
| P0 | Phase 0 | 1 | 0.5 days |
| P0 | Phase 1 | 5 | 5 days |
| P0 | Phase 2 | 12 | 5 days |
| P0 | Phase 3 | 9 | 5 days |
| P0 | Phase 4 | 6 | 3 days |
| P0 | Phase 5 | 7 | 3 days |
| P1 | Phase 6 | 6 | 3 days |
| P1 | Phase 7 | 15 | 5 days |
| P1 | Phase 8 | 12 | 4 days |
| P1 | Phase 9 | 8 | 3 days |
| P2 | Phase 10 | 9 | 4 days |
| P2 | Phase 11 | 7 | 3 days |
| P2 | Phase 12 | 7 | 2 days |
| P2 | Phase 13 | 5 | 2 days |
| P2 | Phase 14 | 7 | 3 days |
| P3 | Phase 15 | 13 | 5 days |
| **Total** | **15 Phases** | **129 Tasks** | **55.5 days** |

### Critical Path

The critical path to App Store submission includes only P0 and P1 items:

1. Phase 0: Critical Bug Fixes (0.5 days)
2. Phase 1: Production Infrastructure (5 days)
3. Phase 2: Deep Linking & Navigation (5 days)
4. Phase 3: UI Testing (5 days)
5. Phase 4: Privacy & Compliance (3 days)
6. Phase 5: Localization (3 days)
7. Phase 6: Security (3 days)
8. Phase 7: Test Coverage (5 days)
9. Phase 8: Accessibility (4 days)
10. Phase 9: UX Enhancements (3 days)

**Critical Path Duration**: 36.5 days (~7.5 weeks)

P2 items add 14 days (3 weeks), bringing total to 50.5 days (~10 weeks).
P3 items add 5 days (1 week), bringing total to 55.5 days (~11 weeks).

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

**Document Version:** 1.0
**Created:** 2025-12-23
**Author:** Technical Product Manager
**Status:** Ready for Implementation
**Next Review:** After Phase 0-1 completion
