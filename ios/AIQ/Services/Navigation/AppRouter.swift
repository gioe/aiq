import AIQSharedKit
import Foundation
import SwiftUI

/// Represents tab-level navigation destinations
///
/// These destinations are handled by switching tabs in MainTabView,
/// not by pushing to the navigation stack. Each tab contains its own
/// NavigationStack that can have Route destinations pushed onto it.
///
/// Usage:
/// ```swift
/// // In MainTabView
/// TabView(selection: $selectedTab) {
///     DashboardView()
///         .tag(TabDestination.dashboard.rawValue)
/// }
/// ```
enum TabDestination: Int, Hashable {
    case dashboard = 0
    case history = 1
    case groups = 2
    case settings = 3

    /// The string identifier for accessibility purposes
    var accessibilityIdentifier: String {
        switch self {
        case .dashboard: AccessibilityIdentifiers.TabBar.dashboardTab
        case .history: AccessibilityIdentifiers.TabBar.historyTab
        case .groups: AccessibilityIdentifiers.TabBar.groupsTab
        case .settings: AccessibilityIdentifiers.TabBar.settingsTab
        }
    }
}

/// Navigation routes for the AIQ app
///
/// Defines all navigable destinations in the app that are pushed onto
/// NavigationStack within individual tabs. Tab-level navigation is handled
/// separately via TabDestination.
///
/// Routes are organized by feature area for clarity.
enum Route: Hashable, Equatable {
    // MARK: - Authentication Routes

    /// Welcome/Login screen
    case welcome

    /// Registration screen
    case registration

    // MARK: - Test Routes

    /// Test taking screen (starts new test or resumes existing)
    /// - Parameter sessionId: Optional session ID to resume via deep link. Defaults to nil (start new test).
    case testTaking(sessionId: Int? = nil)

    /// Adaptive test taking screen (starts new adaptive CAT test)
    /// No parameters - adaptive tests don't support resume by sessionId
    case adaptiveTestTaking

    /// Test results screen showing the completed test results
    case testResults(result: SubmittedTestResult)

    /// Detailed score breakdown screen
    case scoreBreakdown(result: SubmittedTestResult)

    // MARK: - History Routes

    /// Detailed view of a specific test result from history
    case testDetail(result: TestResult, userAverage: Int?)

    // MARK: - Groups Routes

    /// Group detail screen showing leaderboard and members
    case groupDetail(groupId: Int)

    /// Create a new group screen
    case createGroup

    /// Join a group via invite code screen
    case joinGroup

    // MARK: - Settings Routes

    // Note: The main settings screen is a tab (TabDestination.settings).
    //       These routes represent sub-screens pushed from the settings tab.

    /// Notification settings screen
    case notificationSettings

    /// Help screen
    case help

    /// Feedback screen
    case feedback

    // MARK: - Equatable Conformance

    // swiftlint:disable:next cyclomatic_complexity
    static func == (lhs: Route, rhs: Route) -> Bool {
        switch (lhs, rhs) {
        case (.welcome, .welcome):
            true
        case (.registration, .registration):
            true
        case let (.testTaking(lhsSessionId), .testTaking(rhsSessionId)):
            lhsSessionId == rhsSessionId
        case (.adaptiveTestTaking, .adaptiveTestTaking):
            true
        case let (.testResults(lhsResult), .testResults(rhsResult)):
            lhsResult.id == rhsResult.id
        case let (.testDetail(lhsResult, lhsAvg), .testDetail(rhsResult, rhsAvg)):
            lhsResult.id == rhsResult.id && lhsAvg == rhsAvg
        case let (.scoreBreakdown(lhsResult), .scoreBreakdown(rhsResult)):
            lhsResult.id == rhsResult.id
        case let (.groupDetail(lhsId), .groupDetail(rhsId)):
            lhsId == rhsId
        case (.createGroup, .createGroup):
            true
        case (.joinGroup, .joinGroup):
            true
        case (.notificationSettings, .notificationSettings):
            true
        case (.help, .help):
            true
        case (.feedback, .feedback):
            true
        default:
            false
        }
    }

    // MARK: - Hashable Conformance

    // swiftlint:disable:next cyclomatic_complexity
    func hash(into hasher: inout Hasher) {
        switch self {
        case .welcome:
            hasher.combine("welcome")
        case .registration:
            hasher.combine("registration")
        case let .testTaking(sessionId):
            hasher.combine("testTaking")
            hasher.combine(sessionId)
        case .adaptiveTestTaking:
            hasher.combine("adaptiveTestTaking")
        case let .testResults(result):
            hasher.combine("testResults")
            hasher.combine(result.id)
        case let .testDetail(result, average):
            hasher.combine("testDetail")
            hasher.combine(result.id)
            hasher.combine(average)
        case let .scoreBreakdown(result):
            hasher.combine("scoreBreakdown")
            hasher.combine(result.id)
        case let .groupDetail(groupId):
            hasher.combine("groupDetail")
            hasher.combine(groupId)
        case .createGroup:
            hasher.combine("createGroup")
        case .joinGroup:
            hasher.combine("joinGroup")
        case .notificationSettings:
            hasher.combine("notificationSettings")
        case .help:
            hasher.combine("help")
        case .feedback:
            hasher.combine("feedback")
        }
    }
}

/// Router for managing navigation state in the AIQ app
///
/// Wraps per-tab ``NavigationCoordinator`` instances from SharedKit, providing
/// centralized navigation control with per-tab isolation. Each tab (Dashboard,
/// History, Settings) maintains its own independent coordinator and navigation stack.
///
/// Usage:
/// ```swift
/// // In MainTabView — each tab uses CoordinatedNavigationStack
/// CoordinatedNavigationStack(coordinator: router.dashboardCoordinator) { route in
///     destinationView(for: route)
/// } root: {
///     DashboardView()
/// }
///
/// // Navigate from child views (uses currently selected tab)
/// @EnvironmentObject var router: AppRouter
/// router.push(.testTaking)  // Pushes to current tab's coordinator
/// ```
@MainActor
final class AppRouter: ObservableObject {
    /// Per-tab navigation coordinators backed by SharedKit's NavigationCoordinator
    let dashboardCoordinator = NavigationCoordinator<Route>(loggerSubsystem: "com.aiq.app")
    let historyCoordinator = NavigationCoordinator<Route>(loggerSubsystem: "com.aiq.app")
    let groupsCoordinator = NavigationCoordinator<Route>(loggerSubsystem: "com.aiq.app")
    let settingsCoordinator = NavigationCoordinator<Route>(loggerSubsystem: "com.aiq.app")

    /// The currently selected tab (set by MainTabView)
    @Published var currentTab: TabDestination = .dashboard

    // MARK: - Coordinator Access

    /// Get the navigation coordinator for a specific tab
    func coordinator(for tab: TabDestination) -> NavigationCoordinator<Route> {
        switch tab {
        case .dashboard: dashboardCoordinator
        case .history: historyCoordinator
        case .groups: groupsCoordinator
        case .settings: settingsCoordinator
        }
    }

    // MARK: - Navigation Methods (delegate to coordinators)

    /// Push a new route onto the current tab's navigation stack
    func push(_ route: Route) {
        coordinator(for: currentTab).push(route)
    }

    /// Push a new route onto a specific tab's navigation stack
    func push(_ route: Route, in tab: TabDestination) {
        coordinator(for: tab).push(route)
    }

    /// Pop the last route from the current tab's navigation stack
    func pop() {
        coordinator(for: currentTab).pop()
    }

    /// Pop the last route from a specific tab's navigation stack
    func pop(from tab: TabDestination) {
        coordinator(for: tab).pop()
    }

    /// Pop all routes and return to root in the current tab
    func popToRoot() {
        coordinator(for: currentTab).popToRoot()
    }

    /// Pop all routes and return to root in a specific tab
    func popToRoot(in tab: TabDestination) {
        coordinator(for: tab).popToRoot()
    }

    /// Navigate directly to a route, replacing the current stack
    func navigateTo(_ route: Route) {
        navigateTo(route, in: currentTab)
    }

    /// Navigate directly to a route in a specific tab
    func navigateTo(_ route: Route, in tab: TabDestination) {
        let coord = coordinator(for: tab)
        coord.popToRoot()
        coord.push(route)
    }

    /// Navigate to multiple routes in sequence
    func navigateTo(_ routes: [Route]) {
        navigateTo(routes, in: currentTab)
    }

    /// Navigate to multiple routes in sequence for a specific tab
    func navigateTo(_ routes: [Route], in tab: TabDestination) {
        let coord = coordinator(for: tab)
        coord.popToRoot()
        for route in routes {
            coord.push(route)
        }
    }

    // MARK: - State Query Methods

    /// Check if the current tab's navigation stack is at root
    var isAtRoot: Bool {
        isAtRoot(in: currentTab)
    }

    /// Check if a specific tab's navigation stack is at root
    func isAtRoot(in tab: TabDestination) -> Bool {
        coordinator(for: tab).path.isEmpty
    }

    /// Get the current tab's navigation stack depth
    var depth: Int {
        depth(in: currentTab)
    }

    /// Get a specific tab's navigation stack depth
    func depth(in tab: TabDestination) -> Int {
        coordinator(for: tab).path.count
    }
}

// MARK: - Environment Key

/// Environment key for injecting AppRouter into the SwiftUI environment
///
/// Note: Using MainActor.assumeIsolated to access the main actor-isolated
/// AppRouter initialization. In practice, SwiftUI environment access
/// always happens on the main actor.
struct AppRouterKey: EnvironmentKey {
    static var defaultValue: AppRouter {
        MainActor.assumeIsolated {
            AppRouter()
        }
    }
}

extension EnvironmentValues {
    /// Access the app router from the environment
    ///
    /// Usage:
    /// ```swift
    /// @Environment(\.appRouter) var router
    /// router.push(.testTaking)
    /// ```
    var appRouter: AppRouter {
        get { self[AppRouterKey.self] }
        set { self[AppRouterKey.self] = newValue }
    }
}

// MARK: - View Extension

extension View {
    /// Inject an AppRouter into the environment
    ///
    /// - Parameter router: The router to inject
    /// - Returns: A view with the router available in its environment
    func withAppRouter(_ router: AppRouter) -> some View {
        environment(\.appRouter, router)
    }
}
