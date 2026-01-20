import os
import SwiftUI
import UserNotifications

/// Main tab view for authenticated users
struct MainTabView: View {
    private static let logger = Logger(subsystem: "com.aiq.app", category: "MainTabView")
    @Environment(\.appRouter) private var router
    /// Selected tab with persistence across app launches.
    /// On first launch or after upgrading from versions without persistence, defaults to .dashboard.
    @AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard
    @State private var deepLinkHandler = DeepLinkHandler()

    // MARK: - Upgrade Prompt State

    /// Whether to show the notification upgrade prompt
    @State private var showUpgradePrompt = false
    /// Notification manager for checking authorization status and requesting permission
    private let notificationManager: NotificationManagerProtocol
    /// Analytics service for tracking engagement
    private let analyticsService: AnalyticsService

    // MARK: - Initialization

    init() {
        guard let manager = ServiceContainer.shared.resolve(NotificationManagerProtocol.self) else {
            preconditionFailure(
                "NotificationManager must be registered in ServiceContainer before MainTabView initialization"
            )
        }
        notificationManager = manager
        analyticsService = AnalyticsService.shared
    }

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
            handleDeepLinkNavigation(deepLink)
        }
        .onReceive(NotificationCenter.default.publisher(for: .notificationTapped)) { notification in
            handleNotificationTap(notification)
        }
        .sheet(isPresented: $showUpgradePrompt) {
            NotificationUpgradePromptView(
                onEnableNotifications: {
                    handleUpgradePromptAccepted()
                },
                onDismiss: {
                    analyticsService.trackNotificationUpgradePromptDismissed()
                }
            )
        }
    }

    // MARK: - Notification Tap Handling

    /// Handle notification tap and check if upgrade prompt should be shown
    private func handleNotificationTap(_ notification: Notification) {
        // Extract notification type
        let notificationType = notification.userInfo?["type"] as? String ?? "unknown"

        // Extract authorization status from the notification (set by AppDelegate)
        let authStatusRawValue = notification.userInfo?["authorizationStatus"] as? Int ?? 0
        let authStatus = UNAuthorizationStatus(rawValue: authStatusRawValue) ?? .notDetermined

        // Check if we should show upgrade prompt for provisional users
        if shouldShowUpgradePrompt(authorizationStatus: authStatus) {
            analyticsService.trackNotificationUpgradePromptShown(notificationType: notificationType)
            notificationManager.hasShownUpgradePrompt = true
            showUpgradePrompt = true
            // Note: We still process the notification navigation below
        }

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
        handleDeepLinkNavigation(deepLink)
    }

    /// Determine if the upgrade prompt should be shown
    ///
    /// Shows the prompt if:
    /// - User has provisional authorization (not full)
    /// - Upgrade prompt hasn't been shown before
    private func shouldShowUpgradePrompt(authorizationStatus: UNAuthorizationStatus) -> Bool {
        // Only show for provisional users
        guard authorizationStatus == .provisional else {
            return false
        }

        // Don't show if already shown
        guard !notificationManager.hasShownUpgradePrompt else {
            Self.logger.info("Upgrade prompt already shown, skipping")
            return false
        }

        return true
    }

    /// Handle user accepting the upgrade prompt
    private func handleUpgradePromptAccepted() {
        analyticsService.trackNotificationUpgradePromptAccepted()

        Task {
            let granted = await notificationManager.requestAuthorization()
            if granted {
                analyticsService.trackNotificationFullPermissionGranted()
                Self.logger.info("User upgraded from provisional to full notification authorization")
            } else {
                analyticsService.trackNotificationFullPermissionDenied()
                Self.logger.info("User denied full notification authorization upgrade")
            }
        }
    }

    // MARK: - Private Helpers

    /// Handles deep link navigation by switching to the appropriate tab and navigating to the destination.
    /// This method consolidates navigation logic for both `.deepLinkReceived` and `.notificationTapped` handlers.
    private func handleDeepLinkNavigation(_ deepLink: DeepLink) {
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
                    let linkDesc = String(describing: deepLink)
                    Self.logger.error("Failed to handle deep link: \(linkDesc, privacy: .public)")

                    // Show user-friendly error toast based on deep link type
                    let message = switch deepLink {
                    case .testResults:
                        // Navigation failed due to API error (couldn't fetch test results)
                        "toast.deeplink.navigation.failed".localized
                    case .resumeTest:
                        // Resume test not yet implemented
                        "toast.deeplink.resume.unavailable".localized
                    default:
                        "toast.deeplink.navigation.failed".localized
                    }
                    ToastManager.shared.show(message, type: .error)
                }

            case .invalid:
                Self.logger.warning("Received invalid deep link: \(String(describing: deepLink), privacy: .public)")
            }
        }
    }
}

// MARK: - Dashboard Tab Navigation

/// Wrapper view for Dashboard tab with router-based navigation
private struct DashboardTabNavigationView: View {
    @EnvironmentObject private var router: AppRouter

    var body: some View {
        NavigationStack(path: $router.dashboardPath) {
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
