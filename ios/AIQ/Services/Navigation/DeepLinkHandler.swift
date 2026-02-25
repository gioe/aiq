import Foundation
import os

/// Error types for deep link parsing failures
enum DeepLinkError: LocalizedError {
    case unrecognizedSchemeOrHost(url: String)
    case emptyPath(url: String)
    case unrecognizedRoute(route: String, url: String)
    case missingTestActionOrID(url: String)
    case invalidTestResultsID(identifier: String, url: String)
    case nonPositiveTestResultsID(id: Int, url: String)
    case invalidSessionID(identifier: String, url: String)
    case nonPositiveSessionID(id: Int, url: String)
    case unrecognizedTestAction(action: String, url: String)

    var errorDescription: String? {
        switch self {
        case let .unrecognizedSchemeOrHost(url):
            String(format: NSLocalizedString("error.deeplink.unrecognized.scheme", comment: ""), url)
        case let .emptyPath(url):
            String(format: NSLocalizedString("error.deeplink.empty.path", comment: ""), url)
        case let .unrecognizedRoute(route, url):
            String(format: NSLocalizedString("error.deeplink.unrecognized.route", comment: ""), route, url)
        case let .missingTestActionOrID(url):
            String(format: NSLocalizedString("error.deeplink.missing.test.action", comment: ""), url)
        case let .invalidTestResultsID(identifier, url):
            String(format: NSLocalizedString("error.deeplink.invalid.test.results.id", comment: ""), identifier, url)
        case let .nonPositiveTestResultsID(id, url):
            String(format: NSLocalizedString("error.deeplink.non.positive.test.results.id", comment: ""), id, url)
        case let .invalidSessionID(identifier, url):
            String(format: NSLocalizedString("error.deeplink.invalid.session.id", comment: ""), identifier, url)
        case let .nonPositiveSessionID(id, url):
            String(format: NSLocalizedString("error.deeplink.non.positive.session.id", comment: ""), id, url)
        case let .unrecognizedTestAction(action, url):
            String(format: NSLocalizedString("error.deeplink.unrecognized.test.action", comment: ""), action, url)
        }
    }
}

/// Represents a parsed deep link destination with associated data
///
/// Deep links can come from URL schemes (aiq://) or universal links (https://aiq.app/...).
/// This enum represents the structured navigation destination after parsing.
///
/// Note: The backend sends `aiq://login` in logout-all notifications, but there is no `.login`
/// case here. The URL parses as `.invalid`. See the "Known Unhandled Deep Links" section in
/// `DeepLinkHandler` documentation for details on why this is acceptable.
enum DeepLink: Equatable {
    /// View specific test results by result ID
    case testResults(id: Int)

    /// Resume a test session by session ID
    case resumeTest(sessionId: Int)

    /// Navigate to settings
    ///
    /// Note: Settings navigation is handled at the tab level (MainTabView), not via
    /// router.push(). This deep link switches to the settings tab rather than pushing
    /// a route onto the navigation stack.
    case settings

    /// Invalid or unrecognized deep link
    case invalid

    /// Returns the analytics destination type string for this deep link
    var analyticsDestinationType: String {
        switch self {
        case .testResults:
            "test_results"
        case .resumeTest:
            "resume_test"
        case .settings:
            "settings"
        case .invalid:
            "invalid"
        }
    }
}

/// Source of a deep link for analytics tracking
enum DeepLinkSource: String {
    /// Deep link from a push notification
    case pushNotification = "push_notification"
    /// Deep link from an external app
    case externalApp = "external_app"
    /// Deep link from Safari or a web view
    case safari
    /// Custom URL scheme (aiq://)
    case urlScheme = "url_scheme"
    /// Universal link (https://aiq.app or https://dev.aiq.app)
    case universalLink = "universal_link"
    /// Unknown source
    case unknown
}

/// Protocol for deep link handling (enables testing with mock/spy)
///
/// This protocol abstracts the methods that `DeepLinkNavigationService` depends on,
/// allowing tests to inject a mock that verifies correct parameters are passed
/// for navigation calls and analytics tracking.
protocol DeepLinkHandlerProtocol {
    /// Parse a URL into a structured DeepLink
    func parse(_ url: URL) -> DeepLink

    /// Handle a deep link by converting it to a route and navigating via the router
    @MainActor
    func handleNavigation(
        _ deepLink: DeepLink,
        router: AppRouter,
        tab: TabDestination?,
        source: DeepLinkSource,
        originalURL: String
    ) async -> Bool

    /// Track a successful deep link navigation (for use when navigation happens outside this handler)
    @MainActor
    func trackNavigationSuccess(
        _ deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    )

    /// Track a failed deep link parse
    @MainActor
    func trackParseFailed(
        error: DeepLinkError,
        source: DeepLinkSource,
        originalURL: String
    )
}

/// Handles parsing of URL schemes and universal links into structured navigation commands
///
/// Supports both URL schemes (aiq://) and universal links (https://aiq.app/..., https://dev.aiq.app/...).
/// Returns a DeepLink enum representing the parsed destination.
///
/// Supported URL patterns:
/// - `aiq://test/results/{id}` - View specific test results
/// - `aiq://test/resume/{sessionId}` - Resume a test session
/// - `aiq://settings` - Open settings
/// - `https://aiq.app/test/results/{id}` - View specific test results (production)
/// - `https://aiq.app/test/resume/{sessionId}` - Resume a test session (production)
/// - `https://aiq.app/settings` - Open settings (production)
/// - `https://dev.aiq.app/test/results/{id}` - View specific test results (development)
/// - `https://dev.aiq.app/test/resume/{sessionId}` - Resume a test session (development)
/// - `https://dev.aiq.app/settings` - Open settings (development)
///
/// ## Known Unhandled Deep Links
///
/// The following deep links are sent by the backend but not yet handled by this parser:
/// - `aiq://login` - Sent in logout-all security notifications (see `send_logout_all_notification`
///   in the backend `apns_service.py`). Currently parses as `.invalid` because "login" is not a
///   recognized route. When a user taps a logout-all notification, the app shows an error toast
///   instead of navigating to the login screen. This is acceptable for now because logout-all
///   already forces the user back to the welcome/login screen by invalidating their session tokens.
///   A future implementation could add a `.login` case to `DeepLink` for explicit navigation.
///
/// ## Query Parameters and Fragments
/// Query parameters and URL fragments are ignored during parsing. The handler routes
/// exclusively based on path components, so `aiq://test/results/123?source=notification`
/// and `aiq://test/results/123#section` both resolve to `testResults(id: 123)`. This ensures
/// consistent routing behavior regardless of tracking parameters, analytics tags, or
/// fragment identifiers that may be appended by external systems (e.g., email campaigns,
/// push notification payloads). It also prevents query strings from being misinterpreted
/// as part of the navigation path.
///
/// ## Extra Path Component Handling
/// Extra path components beyond the expected pattern are tolerated but logged as warnings.
/// For example, `aiq://test/results/123/extra` parses successfully as `testResults(id: 123)`
/// but logs a warning. This lenient behavior allows forward compatibility while alerting
/// developers to potentially malformed links.
///
/// ## Settings Route Leniency
/// The settings route exhibits special lenient parsing behavior:
/// - Base URL: `aiq://settings` or `https://aiq.app/settings` parses as `.settings`
/// - Extra components: `aiq://settings/notifications` also parses as `.settings`
/// - Extra components are logged as warnings and tracked via analytics
///   (error type: `malformed_settings_extra_components`)
///
/// **Rationale:**
/// - Enables forward compatibility if we later introduce settings
///   sub-paths (e.g., `settings/notifications`, `settings/privacy`)
/// - Prevents user-facing errors from stale or malformed deep links
/// - Analytics tracking helps identify if users are receiving incorrect link formats
/// - Tab-level navigation: Settings navigation is handled by switching
///   tabs, not pushing routes, so sub-path routing is not yet implemented
///
/// **Future Enhancement:**
/// If sub-path routing is needed (e.g., to deep link directly to notification settings), the parser can be
/// extended to recognize specific patterns like `settings/notifications` → `.notificationSettings` without
/// breaking existing behavior.
///
/// Usage:
/// ```swift
/// let handler = DeepLinkHandler()
/// if let url = URL(string: "aiq://test/results/123") {
///     let deepLink = handler.parse(url)
///     switch deepLink {
///     case .testResults(let id):
///         // Navigate to test results with id
///     case .invalid:
///         // Handle invalid link
///     default:
///         break
///     }
/// }
/// ```
struct DeepLinkHandler: DeepLinkHandlerProtocol {
    // MARK: - Constants

    /// URL scheme for AIQ deep links (aiq://)
    private static let urlScheme = "aiq"

    /// Universal link hosts (production and development)
    private static let universalLinkHosts = ["aiq.app", "dev.aiq.app"]

    /// Logger for deep link parsing events
    private static let logger = Logger(subsystem: "com.aiq.app", category: "DeepLink")

    // MARK: - Dependencies

    /// Analytics service for tracking deep link events
    private let analyticsService: AnalyticsService

    // MARK: - Initialization

    /// Initialize with default analytics service
    init(analyticsService: AnalyticsService = .shared) {
        self.analyticsService = analyticsService
    }

    // MARK: - Public API

    /// Parse a URL into a structured DeepLink
    ///
    /// - Parameter url: The URL to parse (can be URL scheme or universal link)
    /// - Returns: A DeepLink representing the destination, or .invalid if unrecognized
    func parse(_ url: URL) -> DeepLink {
        // Check if this is a URL scheme (aiq://) or universal link (https://aiq.app or https://dev.aiq.app)
        if url.scheme == Self.urlScheme {
            return parseURLScheme(url)
        } else if url.scheme == "https", let host = url.host, Self.universalLinkHosts.contains(host) {
            return parseUniversalLink(url)
        }

        recordInvalidDeepLink(.unrecognizedSchemeOrHost(url: url.absoluteString))
        return .invalid
    }

    // MARK: - Private Helpers

    /// Records a deep link parsing failure to both logger and Crashlytics
    private func recordInvalidDeepLink(_ error: DeepLinkError) {
        Self.logger.warning("\(error.localizedDescription, privacy: .public)")
        CrashlyticsErrorRecorder.recordError(error, context: .deepLinkParse)
    }

    /// Parse a URL scheme link (aiq://...)
    private func parseURLScheme(_ url: URL) -> DeepLink {
        // For URL schemes, the host is the first path component
        // aiq://test/results/123 -> host: "test", path: "/results/123"
        let host = url.host ?? ""
        let pathComponents = url.pathComponents.filter { $0 != "/" }

        return parsePathComponents(host: host, pathComponents: pathComponents, originalURL: url)
    }

    /// Parse a universal link (https://aiq.app/...)
    private func parseUniversalLink(_ url: URL) -> DeepLink {
        // For universal links, everything is in the path
        // https://aiq.app/test/results/123 -> path: "/test/results/123"
        let pathComponents = url.pathComponents.filter { $0 != "/" }

        // Extract host (first component) and remaining path
        guard !pathComponents.isEmpty else {
            recordInvalidDeepLink(.emptyPath(url: url.absoluteString))
            return .invalid
        }

        let host = pathComponents[0]
        let remainingComponents = Array(pathComponents.dropFirst())

        return parsePathComponents(host: host, pathComponents: remainingComponents, originalURL: url)
    }

    /// Parse path components into a DeepLink
    ///
    /// - Parameters:
    ///   - host: The first path component (e.g., "test", "settings")
    ///   - pathComponents: The remaining path components
    ///   - originalURL: The original URL for logging purposes
    /// - Returns: A parsed DeepLink or .invalid
    private func parsePathComponents(host: String, pathComponents: [String], originalURL: URL) -> DeepLink {
        switch host {
        case "test":
            return parseTestRoute(pathComponents: pathComponents, originalURL: originalURL)
        case "settings":
            return parseSettingsRoute(pathComponents: pathComponents, originalURL: originalURL)
        // Note: "login" is not handled here. The backend sends aiq://login in logout-all
        // notifications, but the app doesn't need to navigate explicitly because logout-all
        // already invalidates session tokens, returning the user to the welcome screen.
        // If explicit login navigation is needed in the future, add: case "login": return .login
        default:
            recordInvalidDeepLink(.unrecognizedRoute(route: host, url: originalURL.absoluteString))
            return .invalid
        }
    }

    /// Parse test-related routes
    ///
    /// Supported patterns:
    /// - test/results/{id}
    /// - test/resume/{sessionId}
    ///
    /// Note: Extra path components beyond the expected pattern are tolerated but logged as warnings.
    /// For example, `test/results/123/extra/path` will parse as `testResults(id: 123)` but log
    /// a warning about the unexpected components. This lenient behavior allows forward compatibility
    /// if the URL structure evolves, while still alerting developers to potentially malformed links.
    private func parseTestRoute(pathComponents: [String], originalURL: URL) -> DeepLink {
        guard pathComponents.count >= 2 else {
            recordInvalidDeepLink(.missingTestActionOrID(url: originalURL.absoluteString))
            return .invalid
        }

        let action = pathComponents[0]
        let identifier = pathComponents[1]

        // Log warning if extra path components are present beyond action and identifier.
        // Expected format: [action, identifier] (e.g., ["results", "123"])
        // Extra components are ignored but may indicate a malformed URL or future URL pattern.
        if pathComponents.count > 2 {
            let extraComponents = Array(pathComponents.dropFirst(2))
            // Use .auto privacy to allow full details during development while
            // redacting potentially sensitive URL data on user devices.
            Self.logger.warning(
                """
                Deep link has extra path components that will be ignored: \
                \(extraComponents, privacy: .auto) in URL: \(originalURL, privacy: .auto)
                """
            )
        }

        switch action {
        case "results":
            // Parse test results ID
            guard let id = Int(identifier) else {
                recordInvalidDeepLink(.invalidTestResultsID(identifier: identifier, url: originalURL.absoluteString))
                return .invalid
            }
            // Validate ID is positive (database IDs are always > 0)
            guard id > 0 else {
                recordInvalidDeepLink(.nonPositiveTestResultsID(id: id, url: originalURL.absoluteString))
                return .invalid
            }
            return .testResults(id: id)

        case "resume":
            // Parse session ID
            guard let sessionId = Int(identifier) else {
                recordInvalidDeepLink(.invalidSessionID(identifier: identifier, url: originalURL.absoluteString))
                return .invalid
            }
            // Validate session ID is positive (database IDs are always > 0)
            guard sessionId > 0 else {
                recordInvalidDeepLink(.nonPositiveSessionID(id: sessionId, url: originalURL.absoluteString))
                return .invalid
            }
            return .resumeTest(sessionId: sessionId)

        default:
            recordInvalidDeepLink(.unrecognizedTestAction(action: action, url: originalURL.absoluteString))
            return .invalid
        }
    }

    /// Parse settings route
    ///
    /// Supported pattern:
    /// - settings
    ///
    /// Note: Extra path components beyond "settings" are tolerated but logged as warnings.
    /// For example, `settings/notifications` will parse as `.settings` but log
    /// a warning about the unexpected components. This lenient behavior allows forward
    /// compatibility if the URL structure evolves (e.g., future settings subpaths),
    /// while still alerting developers to potentially malformed links.
    private func parseSettingsRoute(pathComponents: [String], originalURL: URL) -> DeepLink {
        // Log warning if extra path components are present beyond "settings".
        // Expected format: [] (no additional components)
        // Extra components are ignored but may indicate a malformed URL or future URL pattern.
        if !pathComponents.isEmpty {
            // Use .auto privacy to allow full details during development while
            // redacting potentially sensitive URL data on user devices.
            Self.logger.warning(
                """
                Deep link has extra path components that will be ignored: \
                \(pathComponents, privacy: .auto) in URL: \(originalURL, privacy: .auto)
                """
            )

            // Track analytics for malformed settings deep links
            // This helps identify if users are receiving incorrect deep link formats
            // or if we need to support additional settings sub-paths in the future
            analyticsService.trackDeepLinkNavigationFailed(
                errorType: "malformed_settings_extra_components",
                source: "unknown",
                url: originalURL.absoluteString
            )
        }
        return .settings
    }
}

// MARK: - Deep Link Navigation

extension DeepLinkHandler {
    /// Protocol-conforming entry point that resolves the API service from ServiceContainer
    ///
    /// This method satisfies the `DeepLinkHandlerProtocol` requirement and delegates to the
    /// full implementation with an internally-resolved `apiService`. The API service is an
    /// implementation detail that callers through the protocol don't need to provide.
    @MainActor
    func handleNavigation(
        _ deepLink: DeepLink,
        router: AppRouter,
        tab: TabDestination?,
        source: DeepLinkSource,
        originalURL: String
    ) async -> Bool {
        await handleNavigation(
            deepLink,
            router: router,
            tab: tab,
            apiService: ServiceContainer.shared.resolve(OpenAPIServiceProtocol.self)!,
            source: source,
            originalURL: originalURL
        )
    }

    /// Handle a deep link by converting it to a route and navigating via the router
    ///
    /// This method performs any necessary data fetching (e.g., fetching test results by ID)
    /// before navigating to the appropriate route in the specified tab.
    ///
    /// - Parameters:
    ///   - deepLink: The parsed deep link to handle
    ///   - router: The app router to use for navigation
    ///   - tab: The tab to navigate in (defaults to current tab)
    ///   - apiService: The API client for fetching data (defaults to shared instance)
    ///   - source: The source of the deep link for analytics tracking
    ///   - originalURL: The original URL string for analytics tracking
    /// - Returns: True if navigation was initiated, false if the deep link couldn't be handled
    @MainActor
    func handleNavigation(
        _ deepLink: DeepLink,
        router: AppRouter,
        tab: TabDestination? = nil,
        apiService: OpenAPIServiceProtocol = ServiceContainer.shared.resolve(OpenAPIServiceProtocol.self)!,
        source: DeepLinkSource = .unknown,
        originalURL: String = ""
    ) async -> Bool {
        let targetTab = tab ?? router.currentTab

        switch deepLink {
        case let .testResults(id):
            if let result = await handleTestResultsNavigation(
                id: id, router: router, targetTab: targetTab, apiService: apiService
            ) {
                router.navigateTo(.testDetail(result: result, userAverage: nil), in: targetTab)
                trackSuccess(deepLink: deepLink, source: source, originalURL: originalURL)
                return true
            }
            trackFailure(errorType: "api_fetch_failed", source: source, originalURL: originalURL)
            return false
        case let .resumeTest(sessionId):
            Self.logger.info("Navigating to resume test session: \(sessionId, privacy: .public)")
            router.navigateTo(.testTaking(sessionId: sessionId), in: targetTab)
            trackSuccess(deepLink: deepLink, source: source, originalURL: originalURL)
            return true
        case .settings:
            // Settings navigation is handled at the tab level in MainTabView.
            // This case should never be reached - if it is, it's a programming error.
            // Log and track the error but don't crash the app.
            Self.logger.error("Settings deep link incorrectly routed to handleNavigation - programming error")
            trackFailure(errorType: "settings_routing_error", source: source, originalURL: originalURL)
            CrashlyticsErrorRecorder.recordError(
                NSError(
                    domain: "com.aiq.deeplink",
                    code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "Settings deep link routed to handleNavigation"]
                ),
                context: .deepLinkNavigation
            )
            return false
        case .invalid:
            Self.logger.warning("Attempted to navigate with invalid deep link")
            trackFailure(errorType: "invalid_deep_link", source: source, originalURL: originalURL)
            return false
        }
    }

    /// Handle test results deep link navigation
    @MainActor
    private func handleTestResultsNavigation(
        id: Int,
        router _: AppRouter,
        targetTab _: TabDestination,
        apiService: OpenAPIServiceProtocol
    ) async -> TestResult? {
        do {
            return try await apiService.getTestResults(resultId: id)
        } catch {
            Self.logger.error("Failed to fetch test result \(id): \(error.localizedDescription, privacy: .public)")
            CrashlyticsErrorRecorder.recordError(error, context: .deepLinkNavigation)
            return nil
        }
    }

    /// Track successful deep link navigation
    private func trackSuccess(deepLink: DeepLink, source: DeepLinkSource, originalURL: String) {
        analyticsService.trackDeepLinkNavigationSuccess(
            destinationType: deepLink.analyticsDestinationType,
            source: source.rawValue,
            url: originalURL
        )
    }

    /// Track failed deep link navigation
    private func trackFailure(errorType: String, source: DeepLinkSource, originalURL: String) {
        analyticsService.trackDeepLinkNavigationFailed(
            errorType: errorType,
            source: source.rawValue,
            url: originalURL
        )
    }

    /// Track a successful deep link navigation (for use when navigation happens outside this handler)
    ///
    /// - Parameters:
    ///   - deepLink: The deep link that was successfully navigated
    ///   - source: The source of the deep link
    ///   - originalURL: The original URL string
    @MainActor
    func trackNavigationSuccess(
        _ deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) {
        analyticsService.trackDeepLinkNavigationSuccess(
            destinationType: deepLink.analyticsDestinationType,
            source: source.rawValue,
            url: originalURL
        )
    }

    /// Track a failed deep link parse (for use when parsing fails)
    ///
    /// - Parameters:
    ///   - error: The error that caused the failure
    ///   - source: The source of the deep link
    ///   - originalURL: The original URL string
    @MainActor
    func trackParseFailed(
        error: DeepLinkError,
        source: DeepLinkSource,
        originalURL: String
    ) {
        analyticsService.trackDeepLinkNavigationFailed(
            errorType: errorTypeString(from: error),
            source: source.rawValue,
            url: originalURL
        )
    }

    /// Convert a DeepLinkError to an analytics-friendly error type string
    private func errorTypeString(from error: DeepLinkError) -> String {
        switch error {
        case .unrecognizedSchemeOrHost:
            "unrecognized_scheme_or_host"
        case .emptyPath:
            "empty_path"
        case .unrecognizedRoute:
            "unrecognized_route"
        case .missingTestActionOrID:
            "missing_test_action_or_id"
        case .invalidTestResultsID:
            "invalid_test_results_id"
        case .nonPositiveTestResultsID:
            "non_positive_test_results_id"
        case .invalidSessionID:
            "invalid_session_id"
        case .nonPositiveSessionID:
            "non_positive_session_id"
        case .unrecognizedTestAction:
            "unrecognized_test_action"
        }
    }
}
