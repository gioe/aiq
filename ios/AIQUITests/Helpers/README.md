# AIQUITests Helpers

This directory contains helper classes and extensions that reduce boilerplate in UI tests and provide a consistent, reusable infrastructure for testing the AIQ iOS app.

## Overview

The UI test helpers follow a modular design pattern where each helper focuses on a specific aspect of the app:

- **BaseUITest**: Base class for all UI tests with common setup and utilities
- **LoginHelper**: Handle authentication flows (login, logout, form validation)
- **NavigationHelper**: Verify screen presence and navigate between tabs/screens
- **TestTakingHelper**: Interact with the test-taking flow (start, answer, submit)
- **XCUIElement+Extensions**: Convenient extensions for common element operations

## Quick Start

### 1. Create a new UI test

All UI tests should inherit from `BaseUITest`:

```swift
import XCTest

final class MyFeatureUITest: BaseUITest {
    func testMyFeature() {
        // Your test code here
        // app is already available from BaseUITest
    }
}
```

### 2. Use helpers in your tests

```swift
func testLoginAndNavigate() {
    // Create helpers
    let loginHelper = LoginHelper(app: app)
    let navHelper = NavigationHelper(app: app)

    // Perform login
    loginHelper.login(email: "test@example.com", password: "password123")

    // Verify navigation
    XCTAssertTrue(navHelper.verifyOnScreen(.dashboard))

    // Navigate to history
    navHelper.navigateToTab(.history)
}
```

## Detailed Documentation

### BaseUITest

Base class providing:
- Automatic app launch and termination
- Standard timeout constants (`standardTimeout`, `extendedTimeout`, `quickTimeout`, `networkTimeout`)
- Wait helpers (`wait(for:timeout:)`, `waitForHittable(_:timeout:)`, `waitForDisappearance(of:timeout:)`)
- Screenshot utilities (`takeScreenshot(named:)`)
- Assertion helpers (`assertExists(_:_:screenshot:)`, `assertHittable(_:_:screenshot:)`)

**Usage:**
```swift
final class MyTest: BaseUITest {
    func testSomething() {
        let button = app.buttons["My Button"]
        wait(for: button) // Uses standardTimeout by default
        assertExists(button, "Button should exist")
    }
}
```

### LoginHelper

Handles authentication flows and form validation.

**Key Methods:**
- `login(email:password:waitForDashboard:)` - Perform login
- `logout()` - Sign out from settings
- `waitForDashboard(timeout:)` - Wait for dashboard after login

**Properties:**
- `emailTextField`, `passwordTextField`, `signInButton` - Form elements
- `isLoggedIn`, `isOnWelcomeScreen` - State checks
- `hasError`, `errorMessage` - Error state

**Usage:**
```swift
let loginHelper = LoginHelper(app: app)

// Basic login
loginHelper.login(email: "user@example.com", password: "pass123")

// Check state
if loginHelper.isLoggedIn {
    // User is authenticated
}

// Handle errors
if loginHelper.hasError {
    print("Error: \(loginHelper.errorMessage ?? "Unknown")")
}
```

**Note:** Currently uses accessibility labels to find elements. Accessibility identifiers are available in `AccessibilityIdentifiers.swift` - migration to identifier-based queries is recommended for more reliable element lookup.

### NavigationHelper

Verify screen presence and navigate between tabs.

**Key Methods:**
- `verifyOnScreen(_:timeout:)` - Check if on a specific screen
- `navigateToTab(_:waitForScreen:)` - Switch to a tab
- `navigateBack()` - Use navigation back button
- `verifyNavigationToRoute(_:timeout:)` - Verify route-based navigation

**Screen Types:**
```swift
enum Screen {
    case welcome, dashboard, history, settings
    case testTaking, testResults
    case notificationSettings, help
}
```

**Tab Types:**
```swift
enum Tab {
    case dashboard, history, settings
}
```

**Usage:**
```swift
let navHelper = NavigationHelper(app: app)

// Verify current screen
XCTAssertTrue(navHelper.verifyOnScreen(.dashboard))

// Navigate to tab
navHelper.navigateToTab(.history)

// Check current tab
if navHelper.currentTab == .settings {
    // On settings tab
}

// Navigate back
navHelper.navigateBack()
```

### TestTakingHelper

Interact with the test-taking flow.

**Key Methods:**
- `startNewTest(waitForFirstQuestion:)` - Start a new test
- `resumeTest(waitForCurrentQuestion:)` - Resume in-progress test
- `answerCurrentQuestion(optionIndex:tapNext:)` - Select answer by index
- `answerCurrentQuestion(withText:tapNext:)` - Select answer by text
- `submitTest(shouldWaitForResults:)` - Submit completed test
- `completeTestWithAnswer(optionIndex:questionCount:)` - Quick complete with same answer

**State Properties:**
- `currentQuestionNumber`, `totalQuestionCount` - Progress tracking
- `isOnLastQuestion` - Check if on final question
- `isOnTestScreen`, `isOnResultsScreen` - State checks

**Usage:**
```swift
let testHelper = TestTakingHelper(app: app)

// Start test
testHelper.startNewTest()

// Answer first question
testHelper.answerCurrentQuestion(optionIndex: 0)

// Check progress
if let current = testHelper.currentQuestionNumber {
    print("On question \(current)")
}

// Quick complete for testing
testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: 30)

// Abandon test
testHelper.abandonTest()
```

### XCUIElement+Extensions

Convenient extensions for common element operations.

**Key Methods:**
- `tapWhenHittable(timeout:)` - Tap when element becomes hittable
- `forceTap()` - Tap at element's center coordinate
- `clearAndTypeText(_:)` - Clear existing text and type new
- `scrollToVisible(in:maxSwipes:)` - Scroll to make element visible
- `button(withLabel:)`, `textField(withLabel:)` - Find child elements

**Properties:**
- `existsAndIsHittable` - Combined existence and hittability check
- `text` - Get element's label or value as text

**Usage:**
```swift
let textField = app.textFields["Email"]

// Clear and enter text
textField.clearAndTypeText("new@email.com")

// Tap when ready
let button = app.buttons["Submit"]
button.tapWhenHittable(timeout: 5.0)

// Get text value
let label = app.staticTexts.firstMatch
print("Label text: \(label.text)")

// Scroll to element
let hiddenElement = app.buttons["Hidden Button"]
hiddenElement.scrollToVisible(in: app)
```

## Important Notes

### Accessibility Identifiers

**Status (Updated 2026-01-13):** The app has accessibility identifiers implemented in `AccessibilityIdentifiers.swift` with 92 identifiers covering all major views.

| View | Identifiers | Helper Status |
|------|-------------|---------------|
| WelcomeView | ✅ Implemented | Uses labels (migration needed) |
| RegistrationView | ✅ Implemented | ✅ Uses identifiers |
| DashboardView | ✅ Implemented | Uses labels (migration needed) |
| TestTakingView | ✅ Implemented | Uses labels (migration needed) |
| TestResultsView | ✅ Implemented | Uses labels (migration needed) |
| SettingsView | ✅ Implemented | Uses labels (migration needed) |
| HistoryView | ✅ Implemented | Uses labels (migration needed) |
| NavigationHelper | ✅ TabBar identifiers | Uses labels (migration needed) |

**Migration Status:** Most helpers still use accessibility labels for backward compatibility. When updating helpers to use identifiers:
1. Import `AccessibilityIdentifiers` enum from the main app target
2. Replace label-based queries with identifier-based queries
3. Example: `app.buttons["Sign In"]` → `app.buttons[AccessibilityIdentifiers.WelcomeView.signInButton]`

See `AccessibilityIdentifiers.swift` in `AIQ/Utilities/Helpers/` for the complete list of available identifiers.

### Test Data

The helpers assume test credentials and data are available. For actual tests:
- Use environment variables or test configuration for credentials
- Set up test data before running UI tests
- Clean up test data after tests complete

### Timeout Usage Guidelines

BaseUITest defines four timeout constants for consistent timing across all UI tests:

| Constant | Duration | Use Case |
|----------|----------|----------|
| `quickTimeout` | 2 seconds | Elements that should appear immediately (already loaded views) |
| `standardTimeout` | 5 seconds | Most UI operations (taps, navigation, animations) |
| `extendedTimeout` | 10 seconds | Slow animations or complex screen transitions |
| `networkTimeout` | 10 seconds | Operations involving API calls (login, logout, data fetching) |

**When to use each timeout:**

1. **`quickTimeout`** - Use for elements that are already on screen or should appear instantly:
   ```swift
   confirmButton.waitForExistence(timeout: quickTimeout)
   ```

2. **`standardTimeout`** - Default for most UI operations:
   ```swift
   wait(for: button) // Uses standardTimeout by default
   ```

3. **`extendedTimeout`** - Use for complex UI transitions that don't involve network:
   ```swift
   wait(for: complexAnimation, timeout: extendedTimeout)
   ```

4. **`networkTimeout`** - Use for any operation that involves an API call:
   - Login/logout (authentication APIs)
   - Registration (account creation APIs)
   - Test submission (scoring APIs)
   - Data fetching (history, dashboard refresh)
   - Deep link navigation (may require data loading)

**Helper classes** accept `networkTimeout` as an initialization parameter, defaulting to appropriate values:
- `LoginHelper`: 10 seconds (standard network operations)
- `NavigationHelper`: 10 seconds (deep link handling)
- `TestTakingHelper`: 10 seconds (test submission)
- `RegistrationHelper`: 15 seconds (account creation is slower)

### Async Operations

Some operations (login, test submission) involve network calls:
- Use `networkTimeout` for network-dependent operations
- Helpers automatically wait for expected results using `networkTimeout`
- Consider adding retry logic for flaky network conditions

## Examples

See `ExampleUITest.swift` for complete examples of using the helpers.

## Contributing

When adding new helpers or extending existing ones:

1. **Follow the existing patterns** - Use similar structure and naming
2. **Add comprehensive documentation** - Include usage examples
3. **Use accessibility identifiers** from `AccessibilityIdentifiers.swift` for new code
4. **Add timeout parameters** - Allow callers to override default timeouts
5. **Return Bool for verification** - Indicate success/failure
6. **Use XCTFail for debugging** - Provide helpful failure messages
7. **Update this README** - Document new functionality

## Future Improvements

- [x] Add accessibility identifiers to app *(completed - see `AccessibilityIdentifiers.swift`)*
- [ ] Migrate remaining helpers to use accessibility identifiers
- [ ] Add screenshot comparison helpers
- [ ] Add performance measurement helpers
- [ ] Add deep link testing helpers
- [ ] Add push notification testing helpers
- [ ] Add network stubbing/mocking support
- [ ] Add test data management utilities
