import AIQSharedKit
import Foundation
import os

/// Result of a deep link navigation attempt
enum DeepLinkNavigationResult: Equatable {
    /// Successfully navigated to the specified tab
    case navigated(tab: TabDestination)

    /// Navigation was dropped due to concurrent processing
    case dropped

    /// Invalid deep link that couldn't be processed
    case invalid

    /// Navigation failed (e.g., API error when fetching test results)
    case failed(DeepLink)
}

/// Callback type for updating the selected tab
typealias TabSelectionHandler = (TabDestination) -> Void

/// Protocol for deep link navigation service (enables testing)
@MainActor
protocol DeepLinkNavigationServiceProtocol {
    func navigate(
        to deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) async -> DeepLinkNavigationResult
}

/// Service responsible for handling deep link navigation using ios-libs ``DeepLinkHandler``.
///
/// Routes deep links through the appropriate per-tab ``NavigationCoordinator`` via SharedKit's
/// ``DeepLinkHandler``. For routes that need async resolution (e.g., test results requiring an
/// API call), the service handles the async work directly then navigates via the coordinator.
///
/// Settings deep links are handled at the tab level (switching tabs) rather than through
/// coordinator push, since Settings is a tab destination, not a route.
@MainActor
final class DeepLinkNavigationService: DeepLinkNavigationServiceProtocol {
    // MARK: - Properties

    private static let logger = Logger(subsystem: "com.aiq.app", category: "DeepLinkNavigation")

    private let router: AppRouter
    private let parser: AIQDeepLinkParser
    private let tabSelectionHandler: TabSelectionHandler
    private let toastManager: any ToastManagerProtocol
    private let analyticsManager: AnalyticsManagerProtocol
    private let apiServiceProvider: () -> OpenAPIServiceProtocol

    /// Tracks whether a deep link is currently being processed to prevent concurrent handling
    private var isProcessingDeepLink = false

    // MARK: - Initialization

    init(
        router: AppRouter,
        parser: AIQDeepLinkParser = AIQDeepLinkParser(),
        tabSelectionHandler: @escaping TabSelectionHandler,
        toastManager: any ToastManagerProtocol,
        analyticsManager: AnalyticsManagerProtocol = ServiceContainer.shared.resolve(),
        apiServiceProvider: @escaping () -> OpenAPIServiceProtocol = { ServiceContainer.shared.resolve() }
    ) {
        self.router = router
        self.parser = parser
        self.tabSelectionHandler = tabSelectionHandler
        self.toastManager = toastManager
        self.analyticsManager = analyticsManager
        self.apiServiceProvider = apiServiceProvider
    }

    // MARK: - Public API

    /// Navigate to a deep link destination.
    ///
    /// For routes the parser can resolve synchronously (e.g., resume test), routing flows
    /// through the ios-libs ``DeepLinkHandler`` and the tab's ``NavigationCoordinator``.
    /// For routes needing async resolution (test results) or tab-level handling (settings),
    /// this service handles them directly.
    func navigate(
        to deepLink: DeepLink,
        source: DeepLinkSource = .unknown,
        originalURL: String = ""
    ) async -> DeepLinkNavigationResult {
        guard !isProcessingDeepLink else {
            let deepLinkDescription = String(describing: deepLink)
            Self.logger.info("Dropping deep link (concurrent): \(deepLinkDescription, privacy: .public)")
            return .dropped
        }

        isProcessingDeepLink = true
        defer { isProcessingDeepLink = false }

        switch deepLink {
        case .settings:
            return handleSettingsNavigation(source: source, originalURL: originalURL)

        case .testResults:
            return await handleTestResultsNavigation(
                deepLink,
                source: source,
                originalURL: originalURL
            )

        case let .resumeTest(sessionId):
            return handleResumeTestNavigation(
                sessionId: sessionId,
                deepLink: deepLink,
                source: source,
                originalURL: originalURL
            )

        case let .joinGroup(inviteCode):
            return await handleJoinGroupNavigation(
                inviteCode: inviteCode,
                deepLink: deepLink,
                source: source,
                originalURL: originalURL
            )

        case .invalid:
            Self.logger.warning("Received invalid deep link: \(String(describing: deepLink), privacy: .public)")
            return .invalid
        }
    }

    // MARK: - Private Helpers

    /// Handle settings deep link by switching to the settings tab
    private func handleSettingsNavigation(
        source: DeepLinkSource,
        originalURL: String
    ) -> DeepLinkNavigationResult {
        tabSelectionHandler(.settings)
        router.currentTab = .settings
        router.popToRoot(in: .settings)

        trackSuccess(deepLink: .settings, source: source, originalURL: originalURL)
        return .navigated(tab: .settings)
    }

    /// Handle resume test via ios-libs DeepLinkHandler routing through the dashboard coordinator
    private func handleResumeTestNavigation(
        sessionId: Int,
        deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) -> DeepLinkNavigationResult {
        tabSelectionHandler(.dashboard)
        router.currentTab = .dashboard

        // Use ios-libs DeepLinkHandler to route through the dashboard coordinator
        let handler = DeepLinkHandler(
            coordinator: router.dashboardCoordinator,
            parser: parser,
            loggerSubsystem: "com.aiq.app"
        )

        // Construct the URL for the handler (it re-parses to get the action)
        let resumeURL = URL(string: "aiq://test/resume/\(sessionId)")!
        let handled = handler.handle(url: resumeURL)

        if handled {
            trackSuccess(deepLink: deepLink, source: source, originalURL: originalURL)
            return .navigated(tab: .dashboard)
        }

        handleNavigationFailure(deepLink: deepLink)
        return .failed(deepLink)
    }

    /// Handle test results deep link (requires async API call)
    private func handleTestResultsNavigation(
        _ deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) async -> DeepLinkNavigationResult {
        guard case let .testResults(id) = deepLink else { return .invalid }

        tabSelectionHandler(.dashboard)
        router.currentTab = .dashboard
        router.popToRoot(in: .dashboard)

        // Fetch test result from API
        let apiService = apiServiceProvider()
        do {
            let result = try await apiService.getTestResults(resultId: id)
            // Navigate via the dashboard coordinator directly
            router.dashboardCoordinator.push(.testDetail(result: result, userAverage: nil))
            trackSuccess(deepLink: deepLink, source: source, originalURL: originalURL)
            return .navigated(tab: .dashboard)
        } catch {
            Self.logger.error("Failed to fetch test result \(id): \(error.localizedDescription, privacy: .public)")
            CrashlyticsErrorRecorder.recordError(error, context: .deepLinkNavigation)
            trackFailure(errorType: "api_fetch_failed", source: source, originalURL: originalURL)
            handleNavigationFailure(deepLink: deepLink)
            return .failed(deepLink)
        }
    }

    /// Handle join group deep link (requires async API call to join the group)
    private func handleJoinGroupNavigation(
        inviteCode: String,
        deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) async -> DeepLinkNavigationResult {
        tabSelectionHandler(.groups)
        router.currentTab = .groups
        router.popToRoot(in: .groups)

        let apiService = apiServiceProvider()
        do {
            let group = try await apiService.joinGroup(inviteCode: inviteCode)
            router.groupsCoordinator.push(.groupDetail(groupId: group.id))
            trackSuccess(deepLink: deepLink, source: source, originalURL: originalURL)
            return .navigated(tab: .groups)
        } catch {
            Self.logger.error(
                "Failed to join group with invite code: \(error.localizedDescription, privacy: .public)"
            )
            CrashlyticsErrorRecorder.recordError(error, context: .deepLinkNavigation)
            trackFailure(errorType: "join_group_failed", source: source, originalURL: originalURL)
            handleNavigationFailure(deepLink: deepLink)
            return .failed(deepLink)
        }
    }

    private func handleNavigationFailure(deepLink: DeepLink) {
        let linkDesc = String(describing: deepLink)
        Self.logger.error("Failed to handle deep link: \(linkDesc, privacy: .public)")

        let message = switch deepLink {
        case .testResults:
            "toast.deeplink.navigation.failed".localized
        case .resumeTest:
            "toast.deeplink.resume.unavailable".localized
        case .joinGroup:
            "toast.deeplink.join.group.failed".localized
        default:
            "toast.deeplink.navigation.failed".localized
        }

        toastManager.show(message, type: .error)
    }

    // MARK: - Analytics

    private func trackSuccess(deepLink: DeepLink, source: DeepLinkSource, originalURL: String) {
        analyticsManager.trackDeepLinkNavigationSuccess(
            destinationType: deepLink.analyticsDestinationType,
            source: source.rawValue,
            url: originalURL
        )
    }

    private func trackFailure(errorType: String, source: DeepLinkSource, originalURL: String) {
        analyticsManager.trackDeepLinkNavigationFailed(
            errorType: errorType,
            source: source.rawValue,
            url: originalURL
        )
    }
}
