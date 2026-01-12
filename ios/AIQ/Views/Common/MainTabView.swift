import os
import SwiftUI

/// Main tab view for authenticated users
struct MainTabView: View {
    private static let logger = Logger(subsystem: "com.aiq.app", category: "MainTabView")
    @Environment(\.appRouter) private var router
    @State private var selectedTab = 0
    @State private var deepLinkHandler = DeepLinkHandler()

    var body: some View {
        TabView(selection: $selectedTab) {
            // Dashboard Tab
            DashboardTabNavigationView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.line.uptrend.xyaxis")
                }
                .tag(0)
                .accessibilityIdentifier(AccessibilityIdentifiers.TabBar.dashboardTab)

            // History Tab
            HistoryTabNavigationView()
                .tabItem {
                    Label("History", systemImage: "clock.arrow.circlepath")
                }
                .tag(1)
                .accessibilityIdentifier(AccessibilityIdentifiers.TabBar.historyTab)

            // Settings Tab
            SettingsTabNavigationView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag(2)
                .accessibilityIdentifier(AccessibilityIdentifiers.TabBar.settingsTab)
        }
        .onReceive(NotificationCenter.default.publisher(for: .deepLinkReceived)) { notification in
            guard let deepLink = notification.userInfo?["deepLink"] as? DeepLink else { return }

            // Handle deep link navigation asynchronously
            Task {
                switch deepLink {
                case .settings:
                    // For settings deep link, switch to the settings tab
                    selectedTab = 2 // Settings tab
                    router.popToRoot() // Pop to root in case there's a navigation stack

                case .testResults, .resumeTest:
                    // Switch to Dashboard tab first for test-related deep links
                    // This ensures navigation happens in the correct tab context
                    selectedTab = 0 // Dashboard tab
                    router.popToRoot() // Clear any existing navigation stack

                    let success = await deepLinkHandler.handleNavigation(deepLink, router: router)
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
        NavigationStack(path: Binding(
            get: { router.path },
            set: { router.path = $0 }
        )) {
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
        NavigationStack(path: Binding(
            get: { router.path },
            set: { router.path = $0 }
        )) {
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
        NavigationStack(path: Binding(
            get: { router.path },
            set: { router.path = $0 }
        )) {
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
        case .settings:
            // Settings is the root of this tab, so navigation to it should pop to root
            // Since we're already at SettingsView, this case shouldn't occur in navigation stack
            EmptyView()
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
