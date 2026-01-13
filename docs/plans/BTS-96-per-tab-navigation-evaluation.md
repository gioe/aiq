# BTS-96: Evaluate Per-Tab Navigation Paths for Tab Isolation

## Overview

This task evaluates whether the current shared `AppRouter` architecture should be refactored to provide per-tab navigation isolation. Currently, all three tabs (Dashboard, History, Settings) share a single `NavigationPath` through `AppRouter`, which could lead to cross-tab state contamination and unexpected navigation behavior as the app grows.

## Strategic Context

### Problem Statement

The AIQ app uses a `TabView` with three tabs (Dashboard, History, Settings), each containing its own `NavigationStack`. However, all three stacks are bound to the same `AppRouter.path`, creating potential issues:

1. **State Contamination Risk**: Navigation actions in one tab can theoretically affect the navigation stack of another tab if not carefully managed
2. **Deep Link Complexity**: Deep link handling currently switches tabs and then manipulates the shared navigation path, which works but is fragile
3. **Tab Switching Behavior**: When users switch between tabs, the shared path architecture makes it unclear whether navigation state should be preserved or reset
4. **Future Scalability**: As more navigation paths are added to History and Settings tabs (per ICG-014, ICG-015), the single shared path becomes harder to reason about

### Current Architecture Analysis

**What We Have:**
- Single `AppRouter` instance with one `NavigationPath`
- Three `NavigationStack` wrappers in `MainTabView.swift`:
  - `DashboardTabNavigationView` - Handles test-related routes (`.testTaking`, `.testResults`, `.testDetail`)
  - `HistoryTabNavigationView` - Currently handles only `.testDetail` route
  - `SettingsTabNavigationView` - Handles settings sub-screens (`.help`, `.notificationSettings`, `.feedback`)
- Each stack binds to the same `router.path` using a two-way Binding
- Deep links handled in `MainTabView` by switching tabs then calling `router.popToRoot()` and `router.navigateTo()`

**How It Works Today:**
1. Each tab's `NavigationStack` is bound to the shared `router.path`
2. When a view calls `router.push()`, it appends to the shared path
3. The currently visible tab's `NavigationStack` reacts to path changes
4. Non-visible tabs also have their stacks bound to the same path, but they're not displayed
5. Deep links switch the selected tab, pop to root, then push the target route

**Current Router Usage Patterns:**

From code analysis, the router is used in:
- **DashboardView**: Pushes to `.testTaking` for test initiation/resumption
- **HistoryView**: Pushes to `.testDetail` to show test result details
- **SettingsView**: Pushes to `.help`, `.feedback` for settings sub-screens
- **TestResultsView**: Pops back after viewing results
- **DeepLinkHandler**: Uses `navigateTo()` for deep link navigation

### Success Criteria

1. Document the current shared router behavior, including:
   - How navigation state is shared across tabs
   - Current deep link handling mechanism
   - Any existing bugs or edge cases

2. Analyze use cases that require cross-tab navigation:
   - Deep links from notifications (e.g., `aiq://test/results/123`)
   - Deep links from universal links
   - In-app navigation flows that cross tab boundaries (if any)

3. If per-tab isolation is needed, propose an architecture that:
   - Provides independent navigation paths for each tab
   - Preserves deep link functionality
   - Maintains appropriate navigation state when switching tabs
   - Follows SwiftUI best practices

4. Validate the solution through:
   - Manual testing of tab switching behavior
   - Deep link testing across scenarios
   - Verification that navigation state is appropriately isolated or preserved

### Why Now?

This evaluation is prioritized for post-launch because:
- The current architecture works for the MVP scope
- History and Settings tabs are about to receive more navigation complexity (ICG-014, ICG-015)
- It's easier to refactor navigation before those tabs gain more features
- This is an architectural decision that becomes harder to change later

## Technical Approach

### High-Level Analysis Questions

1. **Does the shared path cause actual problems?**
   - Can navigation in one tab affect another tab's stack?
   - Are there race conditions or unexpected behaviors?
   - How does the SwiftUI `NavigationStack` binding actually work with tab switching?

2. **What are the tradeoffs of per-tab paths?**
   - Increased complexity vs. better isolation
   - Impact on deep link implementation
   - Memory implications of maintaining multiple paths

3. **What do industry patterns suggest?**
   - How do major iOS apps handle tab + navigation architecture?
   - What does SwiftUI documentation recommend?
   - Are there known SwiftUI gotchas with the current approach?

### Proposed Architectures (To Be Evaluated)

#### Option A: Keep Shared Router (Current Architecture)

**Pros:**
- Simple, centralized navigation control
- Deep links are straightforward (switch tab, manipulate path)
- Single source of truth for navigation state
- Works for current MVP scope

**Cons:**
- Conceptually confusing (why do all tabs share a path?)
- Risk of cross-tab contamination
- Harder to reason about as complexity grows
- Tab-specific navigation state isn't encapsulated

**When to Choose:**
- If testing reveals no actual issues with the current approach
- If the app's navigation remains simple
- If deep linking is a primary concern

---

#### Option B: Per-Tab Path with Router Wrapper

Create a `TabRouter` that maintains separate paths for each tab while preserving a unified interface.

**Architecture:**
```swift
@MainActor
final class TabRouter: ObservableObject {
    @Published var dashboardPath = NavigationPath()
    @Published var historyPath = NavigationPath()
    @Published var settingsPath = NavigationPath()

    private var currentTab: TabDestination = .dashboard

    // Public interface mimics AppRouter
    func push(_ route: Route, tab: TabDestination) {
        switch tab {
        case .dashboard: dashboardPath.append(route)
        case .history: historyPath.append(route)
        case .settings: settingsPath.append(route)
        }
    }

    func pop(tab: TabDestination) { /* ... */ }
    func popToRoot(tab: TabDestination) { /* ... */ }

    // Deep link support
    func navigateTo(_ route: Route, tab: TabDestination, switchingTabs: Bool = true) {
        if switchingTabs {
            currentTab = tab
        }
        popToRoot(tab: tab)
        push(route, tab: tab)
    }
}
```

**Pros:**
- Clear isolation between tab navigation states
- Each tab's navigation is independent
- Preserves navigation state when switching tabs (if desired)
- Easier to reason about navigation per-feature

**Cons:**
- More complex implementation
- Requires explicit tab parameter in navigation calls
- Deep link logic needs updating
- Migration effort from current architecture

**When to Choose:**
- If tab switching reveals state contamination issues
- If History/Settings tabs will gain complex navigation hierarchies
- If preserving per-tab navigation state is important for UX

---

#### Option C: Hybrid Approach (Smart Router)

Keep a single router but implement smart path management that automatically isolates based on the active tab.

**Architecture:**
```swift
@MainActor
final class SmartRouter: ObservableObject {
    @Published private var paths: [TabDestination: NavigationPath] = [
        .dashboard: NavigationPath(),
        .history: NavigationPath(),
        .settings: NavigationPath()
    ]

    var currentTab: TabDestination = .dashboard {
        didSet { objectWillChange.send() }
    }

    var path: NavigationPath {
        get { paths[currentTab] ?? NavigationPath() }
        set { paths[currentTab] = newValue }
    }

    func push(_ route: Route) {
        path.append(route)
    }

    // Other methods remain the same interface
}
```

**Pros:**
- Minimal changes to existing code (same interface)
- Automatic per-tab isolation
- Preserves navigation state per tab
- Clean deep link support

**Cons:**
- More complex internal logic
- Computed property for path might have performance implications
- Harder to debug which tab's path is being modified
- Magic behavior could surprise developers

**When to Choose:**
- If we want isolation without changing call sites
- If maintaining API compatibility is critical
- If migration effort needs to be minimized

---

### Key Decisions & Tradeoffs

**Decision 1: Isolation vs. Simplicity**
- **Tradeoff**: Isolated paths are cleaner conceptually but add complexity
- **Considerations**: Current app scope is small; will History/Settings tabs grow significantly?

**Decision 2: Navigation State Persistence**
- **Tradeoff**: Should tab navigation stacks be preserved when switching tabs, or reset?
- **Considerations**: User expectations (iOS apps typically preserve), memory usage, app state management

**Decision 3: Deep Link Architecture**
- **Tradeoff**: Current approach (switch tab + manipulate path) is simple but couples tabs to navigation
- **Considerations**: How frequently will deep links be used? Are there better patterns?

### Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Shared path causes actual bugs in production | High | Low | Comprehensive testing of tab switching + navigation scenarios |
| Refactor introduces regressions | High | Medium | Extensive automated and manual testing before merge |
| Over-engineering for a simple use case | Medium | Medium | Defer refactoring until complexity justifies it |
| Deep links break after refactor | High | Low | Dedicated deep link test suite |

## Implementation Plan

### Phase 1: Analysis & Documentation
**Goal**: Understand current behavior and identify any actual issues
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Document current shared router behavior in detail | None | 1h | Create flow diagrams showing path sharing |
| 1.2 | Test tab switching with navigation stacks in all tabs | 1.1 | 30min | Manual testing: push to stacks, switch tabs, observe behavior |
| 1.3 | Test deep link scenarios across all tabs | 1.1 | 30min | Test notification deep links, universal links, URL schemes |
| 1.4 | Identify any bugs or unexpected behaviors | 1.2, 1.3 | 30min | Document actual issues vs. theoretical concerns |
| 1.5 | Review SwiftUI NavigationStack + TabView best practices | 1.1 | 30min | Research Apple docs, community patterns, blog posts |

### Phase 2: Cross-Tab Navigation Analysis
**Goal**: Catalog all navigation scenarios and assess cross-tab requirements
**Duration**: 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Map all current navigation flows by tab | Phase 1 | 30min | Document: Dashboard routes, History routes, Settings routes |
| 2.2 | Identify cross-tab navigation use cases | 2.1 | 30min | E.g., Settings → Help, Dashboard → Test → Results → History |
| 2.3 | Analyze deep link requirements | 2.1 | 30min | Which deep links exist? Which tabs do they target? |
| 2.4 | Document expected tab switching + nav state behavior | 2.1 | 30min | Should stacks preserve state? Reset? Context-dependent? |

### Phase 3: Architecture Decision
**Goal**: Choose the optimal architecture based on findings
**Duration**: 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Evaluate Option A (Keep Shared Router) | Phase 2 | 30min | List pros/cons based on actual findings |
| 3.2 | Evaluate Option B (Per-Tab Path Router) | Phase 2 | 30min | Prototype if promising; assess migration effort |
| 3.3 | Evaluate Option C (Hybrid Smart Router) | Phase 2 | 30min | Consider implementation complexity vs. benefits |
| 3.4 | Make architecture recommendation | 3.1, 3.2, 3.3 | 30min | Document chosen approach with rationale |

### Phase 4: Implementation (If Refactor Needed)
**Goal**: Implement chosen architecture if shared router proves insufficient
**Duration**: 4-6 hours (conditional)

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Implement new router architecture | Phase 3 | 2-3h | Create TabRouter or SmartRouter based on decision |
| 4.2 | Update MainTabView navigation bindings | 4.1 | 1h | Wire up per-tab paths to NavigationStack |
| 4.3 | Update deep link handling | 4.1 | 1h | Ensure deep links work with new architecture |
| 4.4 | Update all router call sites (views) | 4.1 | 1-2h | Migrate push/pop/navigateTo calls |
| 4.5 | Update AppRouter environment key | 4.1 | 15min | Inject new router type into environment |

### Phase 5: Testing & Validation
**Goal**: Verify the solution works correctly across all scenarios
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Test tab switching preserves navigation state | Phase 4 | 30min | Manual: push routes, switch tabs, verify stacks |
| 5.2 | Test deep link scenarios | Phase 4 | 30min | Verify all deep link types work correctly |
| 5.3 | Test cross-tab navigation flows (if any) | Phase 4 | 30min | Ensure any cross-tab use cases work |
| 5.4 | Run full regression test suite | Phase 4 | 1h | Automated tests + manual smoke testing |
| 5.5 | Document new navigation architecture | 5.1-5.4 | 30min | Update docs with chosen approach and patterns |

### Phase 6 (Optional): Future Enhancements
**Goal**: Additional improvements discovered during evaluation
**Duration**: Variable

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Add automated tests for navigation state | Phase 5 | 1-2h | UI tests for tab + navigation scenarios |
| 6.2 | Improve deep link error handling | Phase 5 | 1h | Better user feedback for invalid deep links |
| 6.3 | Add navigation analytics | Phase 5 | 1h | Track user navigation patterns for UX insights |

## Open Questions

1. **Tab State Preservation**: Should navigation stacks be preserved when switching tabs, or reset to root?
   - **Answer TBD**: Depends on user testing and iOS platform conventions (most apps preserve)

2. **Deep Link Priority**: How important is deep link functionality vs. clean tab isolation?
   - **Answer TBD**: Need product input; likely both are important

3. **Migration Risk**: If refactoring, what's the risk of breaking existing navigation?
   - **Answer TBD**: Assess during Phase 1 testing

4. **Performance**: Does maintaining multiple NavigationPaths have memory/performance implications?
   - **Answer TBD**: Unlikely to be significant, but worth measuring

5. **SwiftUI Best Practices**: What does Apple recommend for TabView + NavigationStack architecture?
   - **Answer TBD**: Research during Phase 1.5

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| TBD | Architecture choice | To be determined after Phase 3 |
| TBD | Tab state preservation policy | To be determined after Phase 2 |

## Appendix

### Related Tickets
- **ICG-014**: Migrate History tab to router-based navigation (adds more History routes)
- **ICG-015**: Migrate Settings tab to router-based navigation (adds more Settings routes)
- **BTS-100**: Separate TabDestination from Route enum (recently completed, simplified architecture)

### Relevant Files
- `/Users/mattgioe/aiq/ios/AIQ/Views/Common/MainTabView.swift` - Tab structure and navigation wrappers
- `/Users/mattgioe/aiq/ios/AIQ/Services/Navigation/AppRouter.swift` - Current router implementation
- `/Users/mattgioe/aiq/ios/AIQ/Services/Navigation/DeepLinkHandler.swift` - Deep link parsing and navigation

### Research Resources
- [Apple Documentation: NavigationStack](https://developer.apple.com/documentation/swiftui/navigationstack)
- [Apple Documentation: TabView](https://developer.apple.com/documentation/swiftui/tabview)
- [WWDC Videos on Navigation](https://developer.apple.com/videos/play/wwdc2022/10054/)

### Test Scenarios

**Scenario 1: Basic Tab Switching**
1. Open Dashboard tab
2. Push to TestTaking route
3. Switch to History tab
4. Switch back to Dashboard tab
5. **Expected**: Dashboard still shows TestTaking route

**Scenario 2: Deep Link to Specific Tab**
1. App in background
2. Receive deep link: `aiq://test/results/123`
3. **Expected**: App switches to Dashboard tab, shows TestDetail for result 123

**Scenario 3: Cross-Tab State Isolation**
1. Dashboard: Push to TestTaking
2. History: Push to TestDetail
3. Switch between tabs
4. **Expected**: Each tab maintains its own navigation stack independently

**Scenario 4: Deep Link Resets Stack**
1. Dashboard: Push to TestTaking, then TestResults
2. Receive deep link: `aiq://test/results/456`
3. **Expected**: Navigation stack resets, shows TestDetail for result 456

---

## Summary

This evaluation will determine whether the current shared `AppRouter` architecture should be refactored to provide per-tab navigation isolation. The plan prioritizes analysis and testing before implementation, ensuring that any refactoring is justified by actual issues rather than theoretical concerns. The decision will be data-driven, based on real behavior testing and consideration of the app's future navigation complexity.
