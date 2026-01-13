import os
import SwiftUI

/// Main tab view for authenticated users
struct MainTabView: View {
    private static let logger = Logger(subsystem: "com.aiq.app", category: "MainTabView")
    @Environment(\.appRouter) private var router
    /// Selected tab with persistence across app launches.
    /// On first launch or after upgrading from versions without persistence, defaults to .dashboard.
    @AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard
    @State private var deepLinkHandler = DeepLinkHandler()

    var body: some View {
        TabView(selection: $selectedTab) {
            // Dashboard Tab
            DashboardTabNavigationView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.line.uptrend.xyaxis")
                }
                .tag(TabDestination.dashboard)
                .accessibilityIdentifier(TabDestination.dashboard.accessibilityIdentifier)

            // History Tab
            HistoryTabNavigationView()
                .tabItem {
                    Label("History", systemImage: "clock.arrow.circlepath")
                }
                .tag(TabDestination.history)
                .accessibilityIdentifier(TabDestination.history.accessibilityIdentifier)

            // Settings Tab
            SettingsTabNavigationView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag(TabDestination.settings)
                .accessibilityIdentifier(TabDestination.settings.accessibilityIdentifier)
        }
        .onChange(of: selectedTab) { newTab in
            // Update router's current tab so navigation methods target the correct tab
            router.currentTab = newTab
        }
        .onAppear {
            // Initialize router's current tab
            // Note: @AppStorage handles invalid values by falling back to the default (.dashboard)
            router.currentTab = selectedTab
        }
        .onReceive(NotificationCenter.default.publisher(for: .deepLinkReceived)) { notification in
            guard let deepLink = notification.userInfo?["deepLink"] as? DeepLink else { return }

            // Handle deep link navigation asynchronously
            Task {
                switch deepLink {
                case .settings:
                    // For settings deep link, switch to the settings tab
                    selectedTab = .settings
                    router.currentTab = .settings
                    router.popToRoot(in: .settings) // Pop to root in case there's a navigation stack

                case .testResults, .resumeTest:
                    // Switch to Dashboard tab first for test-related deep links
                    // This ensures navigation happens in the correct tab context
                    selectedTab = .dashboard
                    router.currentTab = .dashboard
                    router.popToRoot(in: .dashboard) // Clear any existing navigation stack

                    let success = await deepLinkHandler.handleNavigation(deepLink, router: router, tab: .dashboard)
                    if !success {
                        // Note: User error feedback tracked in ICG-122
                        let linkDesc = String(describing: deepLink)
                        Self.logger.error("Failed to handle deep link: \(linkDesc, privacy: .public)")
                    }

                case .invalid:
                    Self.logger.warning("Received invalid deep link")
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .notificationTapped)) { notification in
            // Extract the payload dictionary containing the original notification userInfo
            guard let payload = notification.userInfo?["payload"] as? [AnyHashable: Any] else {
                Self.logger.warning("Notification tap missing payload")
                return
            }

            // Extract deep_link URL string from the payload
            guard let deepLinkString = payload["deep_link"] as? String else {
                Self.logger.warning("Notification tap missing deep_link in payload")
                return
            }

            // Parse the deep link URL string
            guard let deepLinkURL = URL(string: deepLinkString) else {
                Self.logger.warning("Invalid deep_link URL string: \(deepLinkString, privacy: .public)")
                return
            }

            // Parse and handle the deep link
            let deepLink = deepLinkHandler.parse(deepLinkURL)
            Self.logger.info("Parsed deep link from notification: \(String(describing: deepLink), privacy: .public)")

            // Handle deep link navigation asynchronously
            Task {
                switch deepLink {
                case .settings:
                    // For settings deep link, switch to the settings tab
                    selectedTab = .settings
                    router.currentTab = .settings
                    router.popToRoot(in: .settings) // Pop to root in case there's a navigation stack

                case .testResults, .resumeTest:
                    // Switch to Dashboard tab first for test-related deep links
                    // This ensures navigation happens in the correct tab context
                    selectedTab = .dashboard
                    router.currentTab = .dashboard
                    router.popToRoot(in: .dashboard) // Clear any existing navigation stack

                    let success = await deepLinkHandler.handleNavigation(deepLink, router: router, tab: .dashboard)
                    if !success {
                        // Note: User error feedback tracked in ICG-122
                        let linkDesc = String(describing: deepLink)
                        Self.logger.error("Failed to handle notification deep link: \(linkDesc, privacy: .public)")
                    }

                case .invalid:
                    Self.logger.warning("Notification contained invalid deep link: \(deepLinkString, privacy: .public)")
                }
            }
        }
    }
}

// MARK: - Dashboard Tab Navigation

/// Wrapper view for Dashboard tab with router-based navigation
private struct DashboardTabNavigationView: View {
    @Environment(\.appRouter) private var router

    var body: some View {
        NavigationStack(path: router.binding(for: .dashboard)) {
            DashboardView()
                .navigationDestination(for: Route.self) { route in
                    destinationView(for: route)
                }
        }
    }

    /// Returns the appropriate view for a given route
    @ViewBuilder
    private func destinationView(for route: Route) -> some View {
        switch route {
        case .testTaking:
            TestTakingView()
        case let .testResults(result, isFirstTest):
            TestResultsView(
                result: result,
                onDismiss: {
                    router.pop()
                },
                isFirstTest: isFirstTest
            )
        case let .testDetail(result, userAverage):
            TestDetailView(testResult: result, userAverage: userAverage)
        case .notificationSettings:
            NotificationSettingsView()
        case .help:
            HelpView()
        default:
            Text("Route not implemented")
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - History Tab Navigation

/// Wrapper view for History tab with router-based navigation
private struct HistoryTabNavigationView: View {
    @Environment(\.appRouter) private var router

    var body: some View {
        NavigationStack(path: router.binding(for: .history)) {
            HistoryView()
                .navigationDestination(for: Route.self) { route in
                    destinationView(for: route)
                }
        }
    }

    /// Returns the appropriate view for a given route
    @ViewBuilder
    private func destinationView(for route: Route) -> some View {
        switch route {
        case let .testDetail(result, userAverage):
            TestDetailView(testResult: result, userAverage: userAverage)
        default:
            Text("Route not implemented")
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Settings Tab Navigation

/// Wrapper view for Settings tab with router-based navigation
private struct SettingsTabNavigationView: View {
    @Environment(\.appRouter) private var router

    var body: some View {
        NavigationStack(path: router.binding(for: .settings)) {
            SettingsView()
                .navigationDestination(for: Route.self) { route in
                    destinationView(for: route)
                }
        }
    }

    /// Returns the appropriate view for a given route
    @ViewBuilder
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
                .foregroundColor(.secondary)
        }
    }
}

#Preview {
    MainTabView()
}
