# BTS-68: Persist Tab Selection Across App Launches - Analysis

## Task Overview

**Objective**: Save and restore selected tab on app launch to improve user experience.

**Current State**: The selected tab is initialized to `.dashboard` on every app launch and is not persisted across sessions.

**Acceptance Criteria**:
- Selected tab saved on change
- Restored on app launch
- Defaults to dashboard if no saved state

**Labels**: deferred, post-launch, state-persistence

**Dependencies**: Requires ICG-101 to be completed first (not found in GitHub issues)

## Current Implementation Analysis

### MainTabView.swift

Location: `/Users/mattgioe/aiq/ios/AIQ/Views/Common/MainTabView.swift`

**Current Behavior**:
```swift
struct MainTabView: View {
    @State private var selectedTab: TabDestination = .dashboard

    var body: some View {
        TabView(selection: $selectedTab) {
            // Dashboard, History, Settings tabs
        }
        .onChange(of: selectedTab) { newTab in
            router.currentTab = newTab
        }
        .onAppear {
            router.currentTab = selectedTab
        }
    }
}
```

**Key Observations**:
1. Tab selection is managed with `@State private var selectedTab: TabDestination = .dashboard`
2. The `TabDestination` enum is defined in `AppRouter.swift` with raw values:
   - `case dashboard = 0`
   - `case history = 1`
   - `case settings = 2`
3. The `selectedTab` state is synchronized with `router.currentTab` on change
4. Deep link handling switches tabs programmatically (e.g., for settings, test results)

## Existing Storage Patterns in Codebase

### 1. @AppStorage Usage

The codebase already uses `@AppStorage` for persisting simple user preferences:

**Example from OnboardingViewModel.swift**:
```swift
@AppStorage("hasCompletedOnboarding") var hasCompletedOnboarding: Bool = false
```

**Example from RootView.swift**:
```swift
@AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding: Bool = false
```

### 2. UserDefaults-based Storage Services

The codebase has established patterns for UserDefaults-based storage:

**PrivacyConsentStorage.swift**:
```swift
class PrivacyConsentStorage: PrivacyConsentStorageProtocol {
    private let userDefaults: UserDefaults
    private let consentKey = "com.aiq.privacyConsentAccepted"

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    func hasAcceptedConsent() -> Bool {
        userDefaults.bool(forKey: consentKey)
    }
}
```

**LocalAnswerStorage.swift**:
```swift
class LocalAnswerStorage: LocalAnswerStorageProtocol {
    private let userDefaults: UserDefaults
    private let storageKey = "com.aiq.savedTestProgress"
    private let queue = DispatchQueue(label: "com.aiq.localStorage")

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    func saveProgress(_ progress: SavedTestProgress) throws {
        try queue.sync {
            let encoder = JSONEncoder()
            let data = try encoder.encode(progress)
            userDefaults.set(data, forKey: storageKey)
        }
    }
}
```

## Implementation Recommendation

### Approach 1: @AppStorage (Recommended)

This is the **simplest and most SwiftUI-native approach** for persisting simple UI state like tab selection.

**Why This Approach?**
- SwiftUI property wrapper designed for exactly this use case
- Already used in the codebase for `hasCompletedOnboarding`
- Automatic binding to UserDefaults with minimal code
- No need for additional service layer
- Follows existing patterns in `RootView.swift` and `OnboardingViewModel.swift`

**Implementation**:

```swift
struct MainTabView: View {
    @AppStorage("selectedTab") private var selectedTab: TabDestination = .dashboard
    @Environment(\.appRouter) private var router
    @State private var deepLinkHandler = DeepLinkHandler()

    var body: some View {
        TabView(selection: $selectedTab) {
            // ... existing tab views
        }
        .onChange(of: selectedTab) { newTab in
            router.currentTab = newTab
        }
        .onAppear {
            router.currentTab = selectedTab
        }
        // ... existing deep link handling
    }
}
```

**Key Points**:
- `TabDestination` already conforms to `Int` and `Hashable`, which makes it compatible with `@AppStorage`
- The raw value (0, 1, 2) will be stored in UserDefaults
- The key `"selectedTab"` should be changed to a namespaced key like `"com.aiq.selectedTab"` per coding standards
- Default value `.dashboard` satisfies the acceptance criteria

**Testing Considerations**:
1. Tab selection persists after app restart
2. Defaults to dashboard on first launch
3. Deep link navigation still works (switches tabs and updates storage)
4. Tab changes are saved immediately

### Approach 2: TabPersistenceStorage Service (Over-Engineered)

This approach would create a dedicated storage service similar to `PrivacyConsentStorage`.

**Why NOT This Approach?**
- Adds unnecessary complexity for a single simple value
- Creates additional files and protocols
- Doesn't provide any benefit over `@AppStorage` for this use case
- Would only be justified if we had multiple tab-related settings or complex business logic

**Only Consider This If**:
- Future requirements emerge for complex tab state (e.g., per-tab scroll position)
- Need to integrate with backend API preferences
- Require sophisticated migration logic

## Architecture Considerations

### MVVM Compliance

**Does this require a ViewModel?**
No. According to the coding standards:
- Views can use `@AppStorage` directly for simple UI state
- Tab selection is purely a UI concern with no business logic
- The `AppRouter` already handles navigation coordination

**Precedent**: `RootView.swift` uses `@AppStorage` directly without a ViewModel for `hasCompletedOnboarding`.

### Deep Link Interaction

The implementation must ensure deep links continue to work:

```swift
case .settings:
    selectedTab = .settings  // This will trigger @AppStorage save
    router.currentTab = .settings

case .testResults, .resumeTest:
    selectedTab = .dashboard  // This will trigger @AppStorage save
    router.currentTab = .dashboard
```

Because `selectedTab` is bound to `@AppStorage`, any programmatic updates (including deep links) will automatically persist.

## Dependency Analysis: ICG-101

**Issue**: The task mentions "Requires ICG-101 to be completed first" but this issue was not found in the GitHub repository.

**Potential Meanings**:
1. **Internal Jira Ticket**: May be a ticket in an internal system not synced to GitHub
2. **Obsolete Dependency**: May have been completed or removed
3. **Typo**: Could be a different ticket number

**Recommendation**:
- Clarify the ICG-101 dependency before implementation
- If it's blocking, determine what functionality it provides
- If it's obsolete or a mistake, proceed with implementation

## Implementation Plan

### Phase 1: Simple Implementation
**Estimated Time**: 1-2 hours

1. **Update MainTabView.swift**
   - Change `@State private var selectedTab` to `@AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard`
   - Verify existing `onChange` and deep link logic still works

2. **Manual Testing**
   - Launch app, verify dashboard tab is selected
   - Switch to History tab, force quit app
   - Relaunch app, verify History tab is selected
   - Switch to Settings tab, force quit app
   - Relaunch app, verify Settings tab is selected
   - Test deep link navigation (settings, test results)
   - Verify deep link navigation persists selected tab

3. **Consider Unit Tests** (Optional)
   - Testing `@AppStorage` is typically integration-level
   - May not require dedicated unit tests for this simple change
   - Manual testing may be sufficient

### Phase 2: Code Review & Documentation (Optional)
**Estimated Time**: 30 minutes

1. **Update Documentation**
   - Document the persistence behavior in relevant files
   - Add comment explaining the storage key choice

2. **Code Review**
   - Ensure pattern aligns with existing `@AppStorage` usage
   - Verify no race conditions with deep link handling

## Recommended Subagent Assignment

### Primary: ios-engineer

**Responsibilities**:
1. Implement `@AppStorage` in MainTabView.swift
2. Perform manual testing across all scenarios
3. Verify deep link integration
4. Update any relevant documentation

**Why ios-engineer?**
- Straightforward implementation task
- No complex architecture decisions needed
- Standard SwiftUI pattern application

### Secondary: ios-code-reviewer (Post-Implementation)

**Responsibilities**:
1. Review the implementation for:
   - Consistency with existing `@AppStorage` usage
   - Proper key naming convention
   - No unintended side effects
   - Deep link compatibility
2. Validate test coverage adequacy

**Why ios-code-reviewer?**
- Ensure quality and consistency
- Catch any edge cases in deep link interaction
- Verify adherence to coding standards

## Risk Assessment

### Low Risk Factors
- Simple, well-understood SwiftUI pattern
- Existing precedent in codebase
- Limited scope of change
- Easy to test manually

### Potential Issues & Mitigations

1. **Deep Link Race Conditions**
   - **Risk**: Deep link might override persisted tab before it's visible
   - **Mitigation**: Test deep link scenarios thoroughly; the current implementation should handle this correctly since deep links explicitly set `selectedTab`

2. **TabDestination Enum Changes**
   - **Risk**: If tabs are added/removed/reordered, raw values might change
   - **Mitigation**: `TabDestination` already has explicit raw values (0, 1, 2), so this is stable

3. **User Confusion**
   - **Risk**: User might not remember why they're on a different tab after relaunch
   - **Mitigation**: This is the intended UX improvement; users generally expect this behavior

## Alternatives Considered

### 1. @SceneStorage
- **Purpose**: Persist state per scene (window) for multi-window apps
- **Verdict**: Not applicable; AIQ is single-window, and we want app-level persistence

### 2. Custom Preference Service
- **Purpose**: Centralized preference management
- **Verdict**: Overkill for single value; consider if more app-level preferences emerge

### 3. Backend API Preference Sync
- **Purpose**: Sync tab preference across devices
- **Verdict**: Not required by acceptance criteria; could be future enhancement

## Conclusion

**Recommended Implementation**: Use `@AppStorage` directly in `MainTabView.swift`

**Rationale**:
- Simplest solution that meets all acceptance criteria
- Consistent with existing codebase patterns
- Minimal code change with low risk
- No additional files or complexity needed

**Estimated Total Time**: 2-3 hours (implementation + testing + review)

**Blocking Issue**: Clarify ICG-101 dependency before starting work

**Subagent Assignment**:
1. ios-engineer (primary implementation)
2. ios-code-reviewer (post-implementation review)
