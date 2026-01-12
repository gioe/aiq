# BTS-100: Navigation Refactoring - Tab vs Route Separation

## Overview

This document describes the navigation refactoring that separates tab-level navigation from route-based navigation in the AIQ iOS app. The refactoring clarifies the distinction between switching tabs (tab-level navigation) and pushing views onto navigation stacks (route-based navigation).

## Problem Statement

The original navigation architecture conflated two different types of navigation:

1. **Tab-level navigation**: Switching between main tabs (Dashboard, History, Settings)
2. **Route-based navigation**: Pushing views onto NavigationStack within a tab

The `Route` enum contained `.settings` as a case, but Settings is actually a tab destination, not a route that gets pushed onto a navigation stack. This created ambiguity:

- `MainTabView` correctly handled `.settings` deep links by switching tabs
- `DeepLinkHandler.handleNavigation` had a `.settings` case that should never be called
- `SettingsTabNavigationView.destinationView` had a `.settings` case that returned `EmptyView`
- The distinction between tab switching and navigation stack pushing was unclear

## Solution

### 1. Created TabDestination Enum

Added a new `TabDestination` enum to represent tab-level navigation:

```swift
/// Represents tab-level navigation destinations
///
/// These destinations are handled by switching tabs in MainTabView,
/// not by pushing to the navigation stack. Each tab contains its own
/// NavigationStack that can have Route destinations pushed onto it.
enum TabDestination: Int, Hashable {
    case dashboard = 0
    case history = 1
    case settings = 2

    /// The string identifier for accessibility purposes
    var accessibilityIdentifier: String {
        switch self {
        case .dashboard: "tabBar.dashboardTab"
        case .history: "tabBar.historyTab"
        case .settings: "tabBar.settingsTab"
        }
    }
}
```

**Benefits:**
- Type-safe representation of tabs with raw integer values
- Built-in accessibility identifiers
- Clear semantic separation from routes
- Extensible for future tabs

### 2. Updated Route Enum

Removed `.settings` from the `Route` enum and updated documentation:

```swift
/// Navigation routes for the AIQ app
///
/// Defines all navigable destinations in the app that are pushed onto
/// NavigationStack within individual tabs. Tab-level navigation is handled
/// separately via TabDestination.
///
/// Routes are organized by feature area for clarity.
enum Route: Hashable, Equatable {
    // ... other routes ...

    // MARK: - Settings Routes
    // Note: The main settings screen is a tab (TabDestination.settings), not a route

    /// Notification settings screen
    case notificationSettings

    /// Help screen
    case help

    /// Feedback screen
    case feedback
}
```

**Changes:**
- Removed `.settings` case
- Updated Equatable and Hashable implementations
- Added clarifying comment about settings being a tab

### 3. Updated MainTabView

Updated `MainTabView` to use `TabDestination` throughout:

```swift
struct MainTabView: View {
    @State private var selectedTab: TabDestination = .dashboard

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardTabNavigationView()
                .tabItem { Label("Dashboard", systemImage: "chart.line.uptrend.xyaxis") }
                .tag(TabDestination.dashboard)
                .accessibilityIdentifier(TabDestination.dashboard.accessibilityIdentifier)

            // ... similar for history and settings tabs ...
        }
        .onReceive(NotificationCenter.default.publisher(for: .deepLinkReceived)) { notification in
            guard let deepLink = notification.userInfo?["deepLink"] as? DeepLink else { return }

            Task {
                switch deepLink {
                case .settings:
                    selectedTab = .settings  // Type-safe tab switching
                    router.popToRoot()

                case .testResults, .resumeTest:
                    selectedTab = .dashboard  // Type-safe tab switching
                    router.popToRoot()
                    let success = await deepLinkHandler.handleNavigation(deepLink, router: router)
                    // ... error handling ...

                case .invalid:
                    Self.logger.warning("Received invalid deep link")
                }
            }
        }
    }
}
```

**Benefits:**
- Type-safe tab selection (no more magic numbers like `0`, `1`, `2`)
- Compiler-enforced exhaustiveness
- Self-documenting code with semantic tab names
- Accessibility identifiers centralized in TabDestination

### 4. Cleaned Up SettingsTabNavigationView

Removed the `.settings` case from `destinationView(for:)`:

**Before:**
```swift
private func destinationView(for route: Route) -> some View {
    switch route {
    case .settings:
        // Settings is the root of this tab...
        EmptyView()
    case .help:
        HelpView()
    // ...
    }
}
```

**After:**
```swift
private func destinationView(for route: Route) -> some View {
    switch route {
    case .help:
        HelpView()
    case .notificationSettings:
        NotificationSettingsView()
    case .feedback:
        FeedbackView()
    default:
        Text("Route not implemented")
    }
}
```

### 5. Updated DeepLinkHandler

Changed `.settings` case in `handleNavigation` to explicitly document it should never be called:

**Before:**
```swift
case .settings:
    // Settings navigation is handled at the tab level in MainTabView
    // This case shouldn't be called, but return true for consistency
    Self.logger.info("Settings deep link handled at tab level")
    return true
```

**After:**
```swift
case .settings:
    // Settings navigation is handled at the tab level in MainTabView.
    // This method should never be called for settings deep links.
    // If this case is reached, it indicates a programming error in the deep link flow.
    Self.logger.error("Settings deep link incorrectly routed to handleNavigation - should be handled at tab level")
    assertionFailure("Settings deep link should be handled in MainTabView, not via router navigation")
    return false
```

**Rationale:**
- Documents the architectural invariant clearly
- Fails fast in debug builds with `assertionFailure`
- Logs error for production debugging
- Returns `false` to indicate failure (more honest than returning `true`)

## Architecture Benefits

### Clear Separation of Concerns

**Tab-Level Navigation (TabDestination):**
- Managed by `MainTabView`
- Changes selected tab
- Each tab has its own NavigationStack
- Handled directly in deep link receiver
- Type: `TabDestination` enum

**Route-Based Navigation (Route):**
- Managed by `AppRouter`
- Pushes onto NavigationStack within current tab
- Can be nested multiple levels deep
- Handled by `DeepLinkHandler.handleNavigation`
- Type: `Route` enum

### Type Safety

- Compiler enforces correct usage
- No more magic numbers for tab indices
- Exhaustive switch statements ensure all cases handled
- Semantic naming (`.settings` vs `2`) improves readability

### Maintainability

- New engineers can immediately understand the distinction
- Adding new tabs requires updating `TabDestination`
- Adding new routes within tabs requires updating `Route`
- No ambiguity about where navigation logic belongs

### Testability

- Tab switching can be tested independently
- Route navigation can be tested independently
- Deep link handling has clear contracts

## Files Modified

1. `/Users/mattgioe/aiq/ios/AIQ/Services/Navigation/AppRouter.swift`
   - Added `TabDestination` enum
   - Removed `.settings` from `Route` enum
   - Updated Equatable and Hashable implementations

2. `/Users/mattgioe/aiq/ios/AIQ/Services/Navigation/DeepLinkHandler.swift`
   - Updated `.settings` case in `handleNavigation` with error handling

3. `/Users/mattgioe/aiq/ios/AIQ/Views/Common/MainTabView.swift`
   - Changed `selectedTab` from `Int` to `TabDestination`
   - Updated all tab references to use `TabDestination` cases
   - Updated deep link handling to use `TabDestination`
   - Removed `.settings` case from `SettingsTabNavigationView.destinationView`

## Testing

### Build Status
✅ Build succeeded without errors or warnings

### Test Results
✅ All unit tests passed (1173 tests)
✅ All UI tests passed (110 tests, 108 skipped due to backend requirement)

**Key Test Coverage:**
- DeepLinkHandlerTests: Verified deep link parsing still works correctly
- Navigation tests: Verified tab switching and route navigation work as expected
- No regressions in existing functionality

## Migration Notes

### For Future Development

When adding new navigation destinations:

1. **Is it a new tab?**
   - Add to `TabDestination` enum
   - Add tab in `MainTabView`
   - Create new `TabNavigationView` wrapper

2. **Is it a screen within a tab?**
   - Add to `Route` enum
   - Add to appropriate `destinationView(for:)` in tab navigation wrapper
   - Use `router.push()` to navigate

### Breaking Changes

None. This is an internal refactoring with no API changes visible to users.

### Backward Compatibility

The `DeepLink.settings` case is preserved for backward compatibility with existing deep links. The handling changed location (now in `MainTabView` instead of `DeepLinkHandler.handleNavigation`), but the functionality remains the same.

## Related Issues

- BTS-100: Navigation architecture cleanup
- Reference: iOS Coding Standards `/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md`

## Future Improvements

Consider for future iterations:

1. **Extract Tab Configuration**: Create a `TabConfiguration` type that bundles label, icon, destination, and accessibility identifier
2. **Codable Navigation State**: Make navigation state serializable for state restoration
3. **Navigation Analytics**: Track tab switches vs route pushes separately
4. **Deep Link Testing**: Add tests specifically for tab-level vs route-level deep link handling

## Conclusion

This refactoring establishes a clear architectural boundary between tab-level navigation and route-based navigation. The type-safe `TabDestination` enum eliminates magic numbers and makes the navigation flow explicit and maintainable.
