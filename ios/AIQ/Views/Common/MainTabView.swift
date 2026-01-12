import os
import SwiftUI

/// Main tab view for authenticated users
struct MainTabView: View {
    private static let logger = Logger(subsystem: "com.aiq.app", category: "MainTabView")
    @Environment(\.appRouter) private var router
    @State private var selectedTab: TabDestination = .dashboard
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
