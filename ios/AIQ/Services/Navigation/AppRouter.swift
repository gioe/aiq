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
    case settings = 2

    /// The string identifier for accessibility purposes
    var accessibilityIdentifier: String {
        switch self {
        case .dashboard: AccessibilityIdentifiers.TabBar.dashboardTab
        case .history: AccessibilityIdentifiers.TabBar.historyTab
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

    /// Test results screen showing the completed test results
    case testResults(result: SubmittedTestResult, isFirstTest: Bool = false)

    // MARK: - History Routes

    /// Detailed view of a specific test result from history
    case testDetail(result: TestResult, userAverage: Int?)

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

    static func == (lhs: Route, rhs: Route) -> Bool {
        switch (lhs, rhs) {
        case (.welcome, .welcome):
            true
        case (.registration, .registration):
            true
        case let (.testTaking(lhsSessionId), .testTaking(rhsSessionId)):
            lhsSessionId == rhsSessionId
        case let (.testResults(lhsResult, lhsFirst), .testResults(rhsResult, rhsFirst)):
            lhsResult.id == rhsResult.id && lhsFirst == rhsFirst
        case let (.testDetail(lhsResult, lhsAvg), .testDetail(rhsResult, rhsAvg)):
            lhsResult.id == rhsResult.id && lhsAvg == rhsAvg
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

    func hash(into hasher: inout Hasher) {
        switch self {
        case .welcome:
            hasher.combine("welcome")
        case .registration:
            hasher.combine("registration")
        case let .testTaking(sessionId):
            hasher.combine("testTaking")
            hasher.combine(sessionId)
        case let .testResults(result, isFirstTest):
            hasher.combine("testResults")
            hasher.combine(result.id)
            hasher.combine(isFirstTest)
        case let .testDetail(result, average):
            hasher.combine("testDetail")
            hasher.combine(result.id)
            hasher.combine(average)
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
/// Provides centralized navigation control using SwiftUI's NavigationPath with
/// per-tab navigation isolation. Each tab (Dashboard, History, Settings) maintains
/// its own independent navigation stack.
///
/// Usage:
/// ```swift
/// // In MainTabView
/// @StateObject private var router = AppRouter()
/// @State private var selectedTab: TabDestination = .dashboard
///
/// var body: some View {
///     TabView(selection: $selectedTab) {
///         NavigationStack(path: $router.dashboardPath) {
///             DashboardView()
///         }
///         .tag(TabDestination.dashboard)
///     }
///     .environment(\.appRouter, router)
/// }
///
/// // Navigate from child views (uses currently selected tab)
/// @Environment(\.appRouter) var router
/// router.push(.testTaking)  // Pushes to current tab's path
/// ```
@MainActor
final class AppRouter: ObservableObject {
    /// Navigation path for Dashboard tab
    @Published var dashboardPath = NavigationPath()

    /// Navigation path for History tab
    @Published var historyPath = NavigationPath()

    /// Navigation path for Settings tab
    @Published var settingsPath = NavigationPath()

    /// The currently selected tab (set by MainTabView)
    @Published var currentTab: TabDestination = .dashboard

    // MARK: - Initialization

    init() {}

    // MARK: - Path Access

    /// Get the navigation path for a specific tab
    ///
    /// - Parameter tab: The tab destination
    /// - Returns: The navigation path for the specified tab
    func path(for tab: TabDestination) -> NavigationPath {
        switch tab {
        case .dashboard: dashboardPath
        case .history: historyPath
        case .settings: settingsPath
        }
    }

    /// Set the navigation path for a specific tab
    ///
    /// - Parameters:
    ///   - path: The new navigation path
    ///   - tab: The tab destination
    func setPath(_ path: NavigationPath, for tab: TabDestination) {
        switch tab {
        case .dashboard: dashboardPath = path
        case .history: historyPath = path
        case .settings: settingsPath = path
        }
    }

    /// Get a binding to the navigation path for a specific tab
    ///
    /// This is used by NavigationStack in MainTabView to bind to the correct path.
    ///
    /// - Parameter tab: The tab destination
    /// - Returns: A binding to the navigation path for the specified tab
    func binding(for tab: TabDestination) -> Binding<NavigationPath> {
        switch tab {
        case .dashboard:
            Binding(
                get: { self.dashboardPath },
                set: { self.dashboardPath = $0 }
            )
        case .history:
            Binding(
                get: { self.historyPath },
                set: { self.historyPath = $0 }
            )
        case .settings:
            Binding(
                get: { self.settingsPath },
                set: { self.settingsPath = $0 }
            )
        }
    }

    // MARK: - Navigation Methods

    /// Push a new route onto the navigation stack
    ///
    /// This operates on the currently selected tab's navigation stack.
    ///
    /// - Parameter route: The route to navigate to
    func push(_ route: Route) {
        push(route, in: currentTab)
    }

    /// Push a new route onto the navigation stack for a specific tab
    ///
    /// - Parameters:
    ///   - route: The route to navigate to
    ///   - tab: The tab to push the route in
    func push(_ route: Route, in tab: TabDestination) {
        switch tab {
        case .dashboard:
            dashboardPath.append(route)
        case .history:
            historyPath.append(route)
        case .settings:
            settingsPath.append(route)
        }
    }

    /// Pop the last route from the navigation stack
    ///
    /// This operates on the currently selected tab's navigation stack.
    /// If the stack is empty, this method does nothing.
    func pop() {
        pop(from: currentTab)
    }

    /// Pop the last route from the navigation stack for a specific tab
    ///
    /// - Parameter tab: The tab to pop from
    func pop(from tab: TabDestination) {
        switch tab {
        case .dashboard:
            guard !dashboardPath.isEmpty else { return }
            dashboardPath.removeLast()
        case .history:
            guard !historyPath.isEmpty else { return }
            historyPath.removeLast()
        case .settings:
            guard !settingsPath.isEmpty else { return }
            settingsPath.removeLast()
        }
    }

    /// Pop all routes and return to the root view
    ///
    /// This operates on the currently selected tab's navigation stack.
    func popToRoot() {
        popToRoot(in: currentTab)
    }

    /// Pop all routes and return to the root view for a specific tab
    ///
    /// - Parameter tab: The tab to pop to root in
    func popToRoot(in tab: TabDestination) {
        switch tab {
        case .dashboard: dashboardPath = NavigationPath()
        case .history: historyPath = NavigationPath()
        case .settings: settingsPath = NavigationPath()
        }
    }

    /// Navigate directly to a specific route, replacing the current stack
    ///
    /// This is useful for deep linking or handling notifications.
    /// The new route becomes the only item in the navigation stack.
    /// This operates on the currently selected tab's navigation stack.
    ///
    /// - Parameter route: The route to navigate to
    func navigateTo(_ route: Route) {
        navigateTo(route, in: currentTab)
    }

    /// Navigate directly to a specific route in a specific tab
    ///
    /// - Parameters:
    ///   - route: The route to navigate to
    ///   - tab: The tab to navigate in
    func navigateTo(_ route: Route, in tab: TabDestination) {
        popToRoot(in: tab)
        push(route, in: tab)
    }

    /// Navigate to multiple routes in sequence
    ///
    /// This is useful for deep linking where you need to establish
    /// a specific navigation hierarchy (e.g., Dashboard -> TestTaking -> TestResults).
    /// This operates on the currently selected tab's navigation stack.
    ///
    /// - Parameter routes: The routes to navigate to, in order
    func navigateTo(_ routes: [Route]) {
        navigateTo(routes, in: currentTab)
    }

    /// Navigate to multiple routes in sequence for a specific tab
    ///
    /// - Parameters:
    ///   - routes: The routes to navigate to, in order
    ///   - tab: The tab to navigate in
    func navigateTo(_ routes: [Route], in tab: TabDestination) {
        var newPath = NavigationPath()
        for route in routes {
            newPath.append(route)
        }
        switch tab {
        case .dashboard: dashboardPath = newPath
        case .history: historyPath = newPath
        case .settings: settingsPath = newPath
        }
    }

    // MARK: - State Query Methods

    /// Check if the navigation stack is empty (at root)
    ///
    /// This checks the currently selected tab's navigation stack.
    var isAtRoot: Bool {
        isAtRoot(in: currentTab)
    }

    /// Check if a specific tab's navigation stack is empty (at root)
    ///
    /// - Parameter tab: The tab to check
    /// - Returns: True if the tab is at root, false otherwise
    func isAtRoot(in tab: TabDestination) -> Bool {
        path(for: tab).isEmpty
    }

    /// Get the current depth of the navigation stack
    ///
    /// This returns the depth of the currently selected tab's navigation stack.
    var depth: Int {
        depth(in: currentTab)
    }

    /// Get the depth of a specific tab's navigation stack
    ///
    /// - Parameter tab: The tab to check
    /// - Returns: The depth of the tab's navigation stack
    func depth(in tab: TabDestination) -> Int {
        path(for: tab).count
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
