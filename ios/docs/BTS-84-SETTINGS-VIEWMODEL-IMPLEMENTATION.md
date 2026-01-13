# BTS-84: SettingsViewModel Implementation

## Summary

Created `SettingsViewModel` to move business logic out of `SettingsView` and comply with MVVM architecture patterns. This removes direct access to `AuthManager.shared` from the view layer and improves testability.

## Changes Made

### 1. Created SettingsViewModel.swift

**Location:** `ios/AIQ/ViewModels/SettingsViewModel.swift`

**Key Features:**
- Inherits from `BaseViewModel` for consistent error handling and loading states
- Uses dependency injection via `AuthManagerProtocol`
- Manages all account-related state (logout, delete account)
- Observes `AuthManager.currentUser` changes via Combine publishers
- Follows established patterns from other ViewModels (DashboardViewModel, HistoryViewModel)

**Published Properties:**
- `currentUser: User?` - Current authenticated user
- `showLogoutConfirmation: Bool` - Controls logout confirmation dialog
- `showDeleteAccountConfirmation: Bool` - Controls delete account confirmation dialog
- `deleteAccountError: Error?` - Tracks delete account errors
- `isLoggingOut: Bool` - Loading state for logout operation
- `isDeletingAccount: Bool` - Loading state for delete account operation
- `showOnboarding: Bool` - Controls onboarding flow display

**Public Methods:**
- `logout()` - Performs logout via AuthManager
- `deleteAccount()` - Deletes user account via AuthManager
- `showLogoutDialog()` - Shows logout confirmation
- `showDeleteAccountDialog()` - Shows delete account confirmation
- `showOnboardingFlow()` - Shows onboarding tutorial
- `clearDeleteAccountError()` - Clears delete account error state

### 2. Updated SettingsView.swift

**Changes:**
- Removed `@ObservedObject private var authManager = AuthManager.shared` (violates MVVM)
- Added `@StateObject private var viewModel: SettingsViewModel` (proper ownership)
- Added `init()` that uses `ViewModelFactory.makeSettingsViewModel()` for DI
- Updated all view bindings to use `viewModel` instead of `authManager`
- Moved state management to ViewModel (showLogoutConfirmation, showDeleteAccountConfirmation, etc.)
- All business logic now delegated to ViewModel methods

**Before:**
```swift
@ObservedObject private var authManager = AuthManager.shared
@State private var showLogoutConfirmation = false
@State private var isLoggingOut = false

Button("Logout") {
    Task {
        isLoggingOut = true
        await authManager.logout()
        isLoggingOut = false
    }
}
```

**After:**
```swift
@StateObject private var viewModel: SettingsViewModel

init() {
    let container = ServiceContainer.shared
    _viewModel = StateObject(wrappedValue: ViewModelFactory.makeSettingsViewModel(container: container))
}

Button("Logout") {
    Task {
        await viewModel.logout()
    }
}
```

### 3. Updated ViewModelFactory.swift

Added factory method:
```swift
@MainActor
static func makeSettingsViewModel(container: ServiceContainer) -> SettingsViewModel {
    guard let authManager = container.resolve(AuthManagerProtocol.self) else {
        fatalError("AuthManagerProtocol not registered in ServiceContainer")
    }
    return SettingsViewModel(authManager: authManager)
}
```

### 4. Added to Xcode Project

- Used `/xcode-file-manager` skill to add `SettingsViewModel.swift` to the AIQ target
- File properly integrated into `ViewModels` group

## Architecture Compliance

### ✅ MVVM Compliance
- **Before:** SettingsView directly accessed `AuthManager.shared` (tight coupling)
- **After:** SettingsView uses ViewModel with injected dependencies (loose coupling)

### ✅ Dependency Injection
- Uses `ServiceContainer` for dependency resolution
- ViewModel receives `AuthManagerProtocol` (not concrete class)
- Testable via protocol mocking

### ✅ Coding Standards Adherence

**From `ios/docs/CODING_STANDARDS.md`:**

1. **ViewModels** (lines 116-155):
   - ✅ Inherits from `BaseViewModel`
   - ✅ Marked with `@MainActor`
   - ✅ Contains all business logic and state
   - ✅ Uses `@Published` properties for observable state
   - ✅ Never imports `SwiftUI`

2. **Protocol-Oriented Design** (lines 214-238):
   - ✅ Uses `AuthManagerProtocol` for dependency injection
   - ✅ Allows for mocking in tests

3. **Property Wrappers** (lines 295-323):
   - ✅ Uses `@StateObject` for ViewModel ownership (not `@ObservedObject`)
   - ✅ Initializes ViewModel in `init()` using factory pattern

4. **Memory Management** (lines 509-530):
   - ✅ Uses `[weak self]` in Combine sink closure to avoid retain cycles

5. **Error Handling** (lines 493-549):
   - ✅ Uses `BaseViewModel.handleError()` with retry capability
   - ✅ Uses `[weak self]` in retry closures to prevent retain cycles

## Testing Considerations

The new architecture enables the following tests:

1. **Unit Tests for SettingsViewModel:**
   - Mock `AuthManagerProtocol` to test logout/delete without real auth
   - Test state transitions (isLoggingOut, isDeletingAccount)
   - Test error handling and retry logic
   - Test currentUser observation from AuthManager

2. **View Tests:**
   - Verify view correctly binds to ViewModel published properties
   - Verify view calls correct ViewModel methods on button taps
   - Verify confirmation dialogs appear/disappear based on ViewModel state

## Related Files

- `ios/AIQ/ViewModels/SettingsViewModel.swift` - New ViewModel
- `ios/AIQ/Views/Settings/SettingsView.swift` - Updated view
- `ios/AIQ/Utilities/DI/ViewModelFactory.swift` - Added factory method
- `ios/AIQ/Services/Auth/AuthManagerProtocol.swift` - Dependency protocol
- `ios/docs/CODING_STANDARDS.md` - Architecture guidelines

## Acceptance Criteria

- ✅ SettingsViewModel created following project patterns
- ✅ AuthManager access moved to ViewModel (via protocol)
- ✅ Logout logic moved to ViewModel
- ✅ Delete account logic moved to ViewModel
- ✅ View testability improved (dependency injection enabled)
- ✅ Consistent with other ViewModels in codebase (DashboardViewModel, HistoryViewModel)
- ✅ No direct singleton access in view layer
- ✅ Added to Xcode project in correct target

## Build Status

✅ **Build Succeeded** - The project compiles successfully with all changes.

## Next Steps

1. **Create Unit Tests** (BTS-85 recommended):
   - `SettingsViewModelTests.swift`
   - Test logout flow
   - Test delete account flow
   - Test error handling
   - Test currentUser observation

2. **Run Existing Tests:**
   - Verify no regressions in existing test suite
   - All existing functionality should continue to work

3. **Manual Testing:**
   - Verify logout functionality still works
   - Verify delete account functionality still works
   - Verify onboarding flow still works
   - Verify error states display correctly
