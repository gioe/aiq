# BTS-239: Notification Permission Recovery Banner - Test Implementation

## Overview

Comprehensive unit tests for the notification permission recovery banner feature that guides users to Settings when notification permission is denied at the OS level.

## Test Files

### 1. NotificationSettingsViewModelTests.swift

**Location**: `/Users/mattgioe/aiq/ios/AIQTests/ViewModels/NotificationSettingsViewModelTests.swift`

**New Tests Added** (6 tests):

#### `showPermissionRecoveryBanner` Computed Property Tests

1. **testShowPermissionRecoveryBanner_WhenDenied_ReturnsTrue**
   - Verifies banner shows when authorization status is `.denied`
   - Expected: `showPermissionRecoveryBanner` returns `true`

2. **testShowPermissionRecoveryBanner_WhenNotDetermined_ReturnsFalse**
   - Verifies banner is hidden when permission not yet requested
   - Expected: `showPermissionRecoveryBanner` returns `false`

3. **testShowPermissionRecoveryBanner_WhenAuthorized_ReturnsFalse**
   - Verifies banner is hidden when permission is granted
   - Expected: `showPermissionRecoveryBanner` returns `false`

4. **testShowPermissionRecoveryBanner_WhenProvisional_ReturnsFalse**
   - Verifies banner is hidden with provisional authorization
   - Expected: `showPermissionRecoveryBanner` returns `false`

5. **testShowPermissionRecoveryBanner_WhenEphemeral_ReturnsFalse**
   - Verifies banner is hidden with ephemeral authorization (App Clips)
   - Expected: `showPermissionRecoveryBanner` returns `false`

6. **testShowPermissionRecoveryBanner_ReactsToStatusChanges**
   - Integration test verifying banner reactivity to permission changes
   - Tests the flow: notDetermined → denied (banner appears) → authorized (banner disappears)

### 2. NotificationPermissionBannerTests.swift (NEW FILE)

**Location**: `/Users/mattgioe/aiq/ios/AIQTests/Views/NotificationPermissionBannerTests.swift`

**Total Tests**: 11 tests

#### Initialization Tests (1 test)

1. **testViewCanBeInitialized**
   - Verifies view initializes without errors
   - Ensures callback is not invoked during initialization

#### Callback Tests (2 tests)

2. **testOpenSettingsCallback_IsCalled**
   - Verifies `onOpenSettings` callback is invoked when button is tapped
   - Uses reflection to access and test the closure

3. **testOpenSettingsCallback_CanBeCalledMultipleTimes**
   - Verifies callback can be invoked multiple times
   - Ensures view doesn't debounce (caller's responsibility)

#### Accessibility Tests (4 tests)

4. **testView_HasAccessibilityIdentifier**
   - Verifies accessibility identifier: `"notificationPermissionBanner"`

5. **testView_HasButtonAccessibilityTrait**
   - Verifies view has `.isButton` trait for VoiceOver

6. **testView_HasAccessibilityLabel**
   - Verifies localized accessibility label exists

7. **testView_HasAccessibilityHint**
   - Verifies localized accessibility hint exists

#### Integration Tests (2 tests)

8. **testView_MultipleInstances_HaveIndependentCallbacks**
   - Verifies multiple banner instances have independent callbacks
   - Ensures no shared state between instances

9. **testView_CallbackPersistsAcrossMultipleAccesses**
   - Verifies callback closure is stable across multiple accesses

#### Edge Case Tests (2 tests)

10. **testView_WithEmptyCallback_DoesNotCrash**
    - Verifies empty callback doesn't cause crashes

11. **testView_CallbackWithAsyncWork_CanBeExecuted**
    - Verifies callback supports async operations (Task)
    - Uses XCTestExpectation to verify async completion

## Test Results

### All Tests Passed ✅

```
NotificationPermissionBannerTests: 11/11 tests passed (0.192 seconds)
NotificationSettingsViewModelTests: 38/38 tests passed (including 6 new tests)
```

### Specific BTS-239 Tests

- **ViewModel tests**: 6 new tests for `showPermissionRecoveryBanner`
- **View tests**: 11 new tests for `NotificationPermissionBanner`
- **Total new tests**: 17

## Test Coverage

### ViewModel Coverage

The `showPermissionRecoveryBanner` computed property is tested for:
- All 5 possible `UNAuthorizationStatus` values
- Reactivity to status changes
- Integration with `NotificationManager`

### View Coverage

The `NotificationPermissionBanner` is tested for:
- Initialization
- Callback invocation
- Accessibility compliance (identifiers, labels, hints, traits)
- Multiple instance isolation
- Edge cases (empty callbacks, async work)

## Testing Approach

### ViewModel Testing Pattern

Following the existing test pattern in `NotificationSettingsViewModelTests.swift`:
- Uses `MockNotificationManager` to simulate authorization states
- Tests computed properties directly
- Includes integration tests for state changes
- Uses descriptive test names following Given-When-Then pattern

### View Testing Pattern

Following the pattern from `NotificationSoftPromptViewTests.swift`:
- Uses reflection to access and test closures
- Tests view initialization without side effects
- Verifies callback independence across instances
- Uses `XCTestExpectation` for async callback testing
- Includes accessibility verification (with ViewInspector helper)

### Mock Objects Used

- **MockNotificationManager**: Simulates `NotificationManagerProtocol`
  - Controls `authorizationStatus` for testing different states
  - Tracks method calls for verification
  - Supports setting authorization status via `setAuthorizationStatus()`

## Files Modified

1. `/Users/mattgioe/aiq/ios/AIQTests/ViewModels/NotificationSettingsViewModelTests.swift`
   - Added 6 new test methods for `showPermissionRecoveryBanner`
   - Lines 604-679

## Files Created

1. `/Users/mattgioe/aiq/ios/AIQTests/Views/NotificationPermissionBannerTests.swift`
   - New test file with 11 comprehensive tests
   - Added to Xcode project (AIQTests target)

## Running the Tests

### Run all BTS-239 tests
```bash
/run-ios-test NotificationSettingsViewModelTests NotificationPermissionBannerTests
```

### Run specific test class
```bash
/run-ios-test NotificationPermissionBannerTests
```

### Run specific test method
```bash
/run-ios-test NotificationSettingsViewModelTests/testShowPermissionRecoveryBanner_WhenDenied_ReturnsTrue
```

## Next Steps

- ✅ All tests passing
- ✅ View added to Xcode project
- ✅ Comprehensive test coverage
- Ready for code review and merge

## Related Documentation

- Feature Implementation: BTS-238 (post-test notification permission flow)
- Related: NotificationSoftPromptView (BTS-237)
- ViewModel: `/Users/mattgioe/aiq/ios/AIQ/ViewModels/NotificationSettingsViewModel.swift`
- View: `/Users/mattgioe/aiq/ios/AIQ/Views/Common/NotificationPermissionBanner.swift`
