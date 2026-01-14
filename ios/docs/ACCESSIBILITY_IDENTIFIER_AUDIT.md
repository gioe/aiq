# Accessibility Identifier Audit

**Generated:** January 14, 2026
**Task:** TASK-123 [ICG-169]

This document compares defined accessibility identifiers in `AccessibilityIdentifiers.swift` against their actual usage in the iOS codebase.

## Summary

| Category | Count |
|----------|-------|
| Total Defined Identifiers | 87 |
| Identifiers Applied | 57 |
| Identifiers Not Applied (Unused) | 30 |
| Hardcoded Identifiers (Not centralized) | 4 |

## Unused Defined Identifiers

These identifiers are defined in `AccessibilityIdentifiers.swift` but are not currently applied to any views:

### TestTakingView (5 unused)
| Identifier | Notes |
|------------|-------|
| `progressLabel` | Consider applying to progress indicator label |
| `timerLabel` | Consider applying to countdown timer |
| `timeWarningBanner` | Consider applying to time warning UI |
| `questionNavigationGrid` | Consider applying to question navigation grid |
| `questionNavigationButton(at:)` | Consider applying to navigation buttons |

### TestResultsView (2 unused)
| Identifier | Notes |
|------------|-------|
| `domainScoresSection` | Consider applying to domain scores container |
| `shareButton` | Consider applying if share functionality exists |

### TestDetailView (5 unused)
| Identifier | Notes |
|------------|-------|
| `container` | Consider applying to main container |
| `scoreLabel` | Consider applying to IQ score display |
| `dateLabel` | Consider applying to test date display |
| `domainScoresSection` | Consider applying to domain scores if present |
| `backButton` | Back button is system-provided, may not need ID |

### DashboardView (1 unused)
| Identifier | Notes |
|------------|-------|
| `scrollView` | Consider applying to main ScrollView |

### HistoryView (4 unused)
| Identifier | Notes |
|------------|-------|
| `scrollView` | Consider applying to main ScrollView |
| `emptyStateView` | Consider applying to empty state container |
| `chartView` | Consider applying to IQTrendChart |
| `testRow(at:)` | Consider applying to ForEach items |

### Common (3 unused)
| Identifier | Notes |
|------------|-------|
| `loadingView` | Consider applying to LoadingView container |
| `primaryButton` | Generic, may need context-specific IDs instead |
| `secondaryButton` | Generic, may need context-specific IDs instead |

### NotificationSettings (3 unused)
| Identifier | Notes |
|------------|-------|
| `enableNotificationsToggle` | Consider applying to notifications Toggle |
| `permissionButton` | Consider applying to settings redirect button |
| `statusLabel` | Consider applying to status message |

### HelpView (3 unused)
| Identifier | Notes |
|------------|-------|
| `scrollView` | HelpView uses List, may not need scrollView ID |
| `contactSupportButton` | No contact support button exists currently |
| `faqSection` | Consider applying to FAQ sections |

## Hardcoded Identifiers

These identifiers are hardcoded as strings instead of using the centralized `AccessibilityIdentifiers` enum:

| File | Line | Hardcoded Value | Recommended Change |
|------|------|-----------------|-------------------|
| `NotificationSoftPromptView.swift` | 100 | `"notNowButton"` | Add to AccessibilityIdentifiers |
| `ErrorBanner.swift` | 26 | `"errorBanner.dismissButton"` | Add to AccessibilityIdentifiers |
| `NotificationPermissionBanner.swift` | 51 | `"notificationPermissionBanner"` | Add to AccessibilityIdentifiers |

## Duplicate Definitions

The `TabDestination` enum in `AppRouter.swift` (lines 24-28) contains duplicate identifier definitions:

```swift
var accessibilityIdentifier: String {
    switch self {
    case .dashboard: "tabBar.dashboardTab"
    case .history: "tabBar.historyTab"
    case .settings: "tabBar.settingsTab"
    }
}
```

These duplicate the values in `AccessibilityIdentifiers.TabBar`. Consider refactoring to use the centralized enum:

```swift
var accessibilityIdentifier: String {
    switch self {
    case .dashboard: AccessibilityIdentifiers.TabBar.dashboardTab
    case .history: AccessibilityIdentifiers.TabBar.historyTab
    case .settings: AccessibilityIdentifiers.TabBar.settingsTab
    }
}
```

## Properly Applied Identifiers

The following identifiers are correctly defined and applied:

### OnboardingView (8/8 applied)
- `containerView`, `page1`, `page2`, `page3`, `page4`, `continueButton`, `skipButton`, `getStartedButton`, `privacyPolicyLink`

### PrivacyConsentView (4/4 applied)
- `privacyIcon`, `privacyPolicyLink`, `termsOfServiceLink`, `acceptButton`

### WelcomeView (6/6 applied)
- `emailTextField`, `passwordTextField`, `signInButton`, `createAccountButton`, `brainIcon`, `errorBanner`

### RegistrationView (8/8 applied)
- `firstNameTextField`, `lastNameTextField`, `emailTextField`, `passwordTextField`, `confirmPasswordTextField`, `educationLevelButton`, `createAccountButton`, `signInLink`

### DashboardView (7/8 applied)
- `testsTakenStat`, `averageIQStat`, `latestTestCard`, `actionButton`, `resumeButton`, `inProgressTestCard`, `abandonTestButton`, `emptyStateView`
- Missing: `scrollView`

### TestTakingView (7/12 applied)
- `questionCard`, `questionText`, `progressBar`, `answerTextField`, `answerButton(at:)`, `previousButton`, `nextButton`, `submitButton`, `exitButton`
- Missing: `progressLabel`, `timerLabel`, `timeWarningBanner`, `questionNavigationGrid`, `questionNavigationButton(at:)`

### TestResultsView (3/5 applied)
- `scoreLabel`, `performanceLabel`, `doneButton`
- Missing: `domainScoresSection`, `shareButton`

### SettingsView (10/10 applied)
- `accountSection`, `notificationsSection`, `helpButton`, `viewOnboardingButton`, `feedbackButton`, `logoutButton`, `deleteAccountButton`, `appVersionLabel`, `debugSection`, `testCrashButton`

### FeedbackView (5/5 applied)
- `nameTextField`, `emailTextField`, `categoryMenu`, `descriptionTextField`, `submitButton`

### Common (2/5 applied)
- `errorView`, `retryButton`
- Missing: `loadingView`, `primaryButton`, `secondaryButton`

## Recommendations

1. **High Priority:** Apply unused identifiers to views where UI tests would benefit from stable element references.

2. **Medium Priority:** Consolidate hardcoded identifiers into `AccessibilityIdentifiers.swift` to maintain a single source of truth.

3. **Low Priority:** Refactor `TabDestination.accessibilityIdentifier` to use the centralized enum.

4. **Consider Removing:** Identifiers that don't correspond to testable UI elements (e.g., `backButton` which is system-provided).

## Related Tasks

- [ICG-167] Apply LoadingView and ErrorView Accessibility Identifiers (Task 125)
- [ICG-166] Add UI Tests Verifying Accessibility Identifiers Exist (Task 126)
