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
        case .dashboard: "tabBar.dashboardTab"
        case .history: "tabBar.historyTab"
        case .settings: "tabBar.settingsTab"
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
    case testTaking

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
        case (.testTaking, .testTaking):
            true
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
        case .testTaking:
            hasher.combine("testTaking")
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
/// Provides centralized navigation control using SwiftUI's NavigationPath.
/// Supports push, pop, popToRoot, and direct navigation for deep linking.
///
/// Usage:
/// ```swift
/// // Inject into environment
/// @StateObject private var router = AppRouter()
/// var body: some View {
///     NavigationStack(path: $router.path) {
///         // Root view
///     }
///     .environmentObject(router)
/// }
///
/// // Navigate from child views
/// @EnvironmentObject var router: AppRouter
/// router.push(.testTaking)
/// ```
@MainActor
final class AppRouter: ObservableObject {
    /// The navigation path managing the stack of routes
    @Published var path = NavigationPath()

    // MARK: - Initialization

    init() {}

    // MARK: - Navigation Methods

    /// Push a new route onto the navigation stack
    ///
    /// - Parameter route: The route to navigate to
    func push(_ route: Route) {
        path.append(route)
    }

    /// Pop the last route from the navigation stack
    ///
    /// If the stack is empty, this method does nothing.
    func pop() {
        guard !path.isEmpty else { return }
        path.removeLast()
    }

    /// Pop all routes and return to the root view
    func popToRoot() {
        path.removeLast(path.count)
    }

    /// Navigate directly to a specific route, replacing the current stack
    ///
    /// This is useful for deep linking or handling notifications.
    /// The new route becomes the only item in the navigation stack.
    ///
    /// - Parameter route: The route to navigate to
    func navigateTo(_ route: Route) {
        popToRoot()
        push(route)
    }

    /// Navigate to multiple routes in sequence
    ///
    /// This is useful for deep linking where you need to establish
    /// a specific navigation hierarchy (e.g., Dashboard -> History -> TestDetail).
    ///
    /// - Parameter routes: The routes to navigate to, in order
    func navigateTo(_ routes: [Route]) {
        popToRoot()
        for route in routes {
            push(route)
        }
    }

    // MARK: - State Query Methods

    /// Check if the navigation stack is empty (at root)
    var isAtRoot: Bool {
        path.isEmpty
    }

    /// Get the current depth of the navigation stack
    var depth: Int {
        path.count
    }
}

// MARK: - Environment Key

/// Environment key for injecting AppRouter into the SwiftUI environment
struct AppRouterKey: EnvironmentKey {
    @MainActor
    static let defaultValue = AppRouter()
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
