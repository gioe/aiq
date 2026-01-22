import os
import SwiftUI
import UserNotifications

/// Main tab view for authenticated users
struct MainTabView: View {
    private static let logger = Logger(subsystem: "com.aiq.app", category: "MainTabView")
    @EnvironmentObject private var router: AppRouter
    /// Selected tab with persistence across app launches.
    /// On first launch or after upgrading from versions without persistence, defaults to .dashboard.
    @AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard
    @State private var deepLinkHandler = DeepLinkHandler()
    /// Tracks whether a deep link is currently being processed to prevent concurrent handling.
    /// Thread-safety: Notification handlers use `.receive(on: DispatchQueue.main)` to ensure
    /// main thread execution before accessing this property.
    @State private var isProcessingDeepLink = false

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
        .onDisappear {
            // Reset deep link processing state when view disappears to prevent stale state
            isProcessingDeepLink = false
        }
        .onReceive(
            NotificationCenter.default.publisher(for: .deepLinkReceived)
                .receive(on: DispatchQueue.main)
        ) { notification in
            guard let deepLink = notification.userInfo?["deepLink"] as? DeepLink else { return }
            let source = notification.userInfo?["source"] as? DeepLinkSource ?? .unknown
            let originalURL = notification.userInfo?["originalURL"] as? String ?? ""
            handleDeepLinkNavigation(deepLink, source: source, originalURL: originalURL)
        }
        .onReceive(
            NotificationCenter.default.publisher(for: .notificationTapped)
                .receive(on: DispatchQueue.main)
        ) { notification in
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

        // Sanitize URL for analytics (remove query parameters)
        let sanitizedURL = sanitizeURLForAnalytics(deepLinkURL)
        handleDeepLinkNavigation(deepLink, source: .pushNotification, originalURL: sanitizedURL)
    }

    /// Sanitize a URL for analytics by removing sensitive query parameters
    private func sanitizeURLForAnalytics(_ url: URL) -> String {
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        components?.queryItems = nil
        components?.fragment = nil
        return components?.string ?? url.absoluteString
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
    ///
    /// - Parameters:
    ///   - deepLink: The parsed deep link to navigate to
    ///   - source: The source of the deep link for analytics tracking
    ///   - originalURL: The original URL string for analytics tracking
    ///
    /// - Note: Concurrent deep links are dropped (not queued) while one is being processed. This is intentional
    ///   because deep links represent user intent at a specific moment. Processing an older deep link after a
    ///   newer one completes would create unexpected navigation and poor UX.
    private func handleDeepLinkNavigation(
        _ deepLink: DeepLink,
        source: DeepLinkSource = .unknown,
        originalURL: String = ""
    ) {
        // Guard against concurrent deep link processing.
        // The flag is set before Task creation to prevent race conditions.
        guard !isProcessingDeepLink else {
            let deepLinkDescription = String(describing: deepLink)
            Self.logger.info("Dropping deep link (concurrent): \(deepLinkDescription, privacy: .public)")
            return
        }

        isProcessingDeepLink = true
        Task {
            defer { isProcessingDeepLink = false }

            switch deepLink {
            case .settings:
                // For settings deep link, switch to the settings tab
                selectedTab = .settings
                router.currentTab = .settings
                router.popToRoot(in: .settings) // Pop to root in case there's a navigation stack
                // Track successful navigation for settings (handled here, not in DeepLinkHandler)
                deepLinkHandler.trackNavigationSuccess(deepLink, source: source, originalURL: originalURL)

            case .testResults, .resumeTest:
                // Switch to Dashboard tab first for test-related deep links
                // This ensures navigation happens in the correct tab context
                selectedTab = .dashboard
                router.currentTab = .dashboard
                router.popToRoot(in: .dashboard) // Clear any existing navigation stack

                let success = await deepLinkHandler.handleNavigation(
                    deepLink,
                    router: router,
                    tab: .dashboard,
                    source: source,
                    originalURL: originalURL
                )
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
        case let .testTaking(sessionId):
            TestTakingView(sessionId: sessionId)
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
                .onAppear {
                    let error = NSError(
                        domain: "com.aiq.navigation",
                        code: 1001,
                        userInfo: [NSLocalizedDescriptionKey: "Unimplemented route in DashboardTab: \(route)"]
                    )
                    CrashlyticsErrorRecorder.recordError(
                        error,
                        context: .unimplementedRoute,
                        additionalInfo: ["tab": "dashboard", "route": String(describing: route)]
                    )
                }
        }
    }
}

// MARK: - History Tab Navigation

/// Wrapper view for History tab with router-based navigation
private struct HistoryTabNavigationView: View {
    @EnvironmentObject private var router: AppRouter

    var body: some View {
        NavigationStack(path: $router.historyPath) {
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
                .onAppear {
                    let error = NSError(
                        domain: "com.aiq.navigation",
                        code: 1001,
                        userInfo: [NSLocalizedDescriptionKey: "Unimplemented route in HistoryTab: \(route)"]
                    )
                    CrashlyticsErrorRecorder.recordError(
                        error,
                        context: .unimplementedRoute,
                        additionalInfo: ["tab": "history", "route": String(describing: route)]
                    )
                }
        }
    }
}

// MARK: - Settings Tab Navigation

/// Wrapper view for Settings tab with router-based navigation
private struct SettingsTabNavigationView: View {
    @EnvironmentObject private var router: AppRouter

    var body: some View {
        NavigationStack(path: $router.settingsPath) {
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
                .onAppear {
                    let error = NSError(
                        domain: "com.aiq.navigation",
                        code: 1001,
                        userInfo: [NSLocalizedDescriptionKey: "Unimplemented route in SettingsTab: \(route)"]
                    )
                    CrashlyticsErrorRecorder.recordError(
                        error,
                        context: .unimplementedRoute,
                        additionalInfo: ["tab": "settings", "route": String(describing: route)]
                    )
                }
        }
    }
}

#Preview {
    MainTabView()
}
