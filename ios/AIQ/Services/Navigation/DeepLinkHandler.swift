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
    case settingsSubPathNotAllowed(url: String)

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
        case let .settingsSubPathNotAllowed(url):
            String(format: NSLocalizedString("error.deeplink.settings.subpath.not.allowed", comment: ""), url)
        }
    }
}

/// Represents a parsed deep link destination with associated data
///
/// Deep links can come from URL schemes (aiq://) or universal links (https://aiq.app/...).
/// This enum represents the structured navigation destination after parsing.
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
}

/// Handles parsing of URL schemes and universal links into structured navigation commands
///
/// Supports both URL schemes (aiq://) and universal links (https://aiq.app/...).
/// Returns a DeepLink enum representing the parsed destination.
///
/// Supported URL patterns:
/// - `aiq://test/results/{id}` - View specific test results
/// - `aiq://test/resume/{sessionId}` - Resume a test session
/// - `aiq://settings` - Open settings
/// - `https://aiq.app/test/results/{id}` - View specific test results
/// - `https://aiq.app/test/resume/{sessionId}` - Resume a test session
/// - `https://aiq.app/settings` - Open settings
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
struct DeepLinkHandler {
    // MARK: - Constants

    /// URL scheme for AIQ deep links (aiq://)
    private static let urlScheme = "aiq"

    /// Universal link host (aiq.app)
    private static let universalLinkHost = "aiq.app"

    /// Logger for deep link parsing events
    private static let logger = Logger(subsystem: "com.aiq.app", category: "DeepLink")

    // MARK: - Public API

    /// Parse a URL into a structured DeepLink
    ///
    /// - Parameter url: The URL to parse (can be URL scheme or universal link)
    /// - Returns: A DeepLink representing the destination, or .invalid if unrecognized
    func parse(_ url: URL) -> DeepLink {
        // Check if this is a URL scheme (aiq://) or universal link (https://aiq.app)
        if url.scheme == Self.urlScheme {
            return parseURLScheme(url)
        } else if url.scheme == "https" && url.host == Self.universalLinkHost {
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
    private func parseTestRoute(pathComponents: [String], originalURL: URL) -> DeepLink {
        guard pathComponents.count >= 2 else {
            recordInvalidDeepLink(.missingTestActionOrID(url: originalURL.absoluteString))
            return .invalid
        }

        let action = pathComponents[0]
        let identifier = pathComponents[1]

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
    private func parseSettingsRoute(pathComponents: [String], originalURL: URL) -> DeepLink {
        // Settings route should have no additional path components
        guard pathComponents.isEmpty else {
            recordInvalidDeepLink(.settingsSubPathNotAllowed(url: originalURL.absoluteString))
            return .invalid
        }
        return .settings
    }
}

// MARK: - Deep Link Navigation

extension DeepLinkHandler {
    /// Handle a deep link by converting it to a route and navigating via the router
    ///
    /// This method performs any necessary data fetching (e.g., fetching test results by ID)
    /// before navigating to the appropriate route.
    ///
    /// - Parameters:
    ///   - deepLink: The parsed deep link to handle
    ///   - router: The app router to use for navigation
    ///   - apiClient: The API client for fetching data (optional, defaults to shared instance)
    /// - Returns: True if navigation was initiated, false if the deep link couldn't be handled
    @MainActor
    func handleNavigation(
        _ deepLink: DeepLink,
        router: AppRouter,
        apiClient: APIClientProtocol = APIClient.shared
    ) async -> Bool {
        switch deepLink {
        case let .testResults(id):
            // Fetch test result from API
            do {
                let result: TestResult = try await apiClient.request(
                    endpoint: .testResults(String(id)),
                    method: .get,
                    body: nil as String?,
                    requiresAuth: true
                )

                // Convert TestResult to SubmittedTestResult for navigation
                // Note: We use the result data we have; userAverage can be nil for deep links
                router.navigateTo(.testDetail(result: result, userAverage: nil))
                return true
            } catch {
                Self.logger.error("Failed to fetch test result \(id): \(error.localizedDescription, privacy: .public)")
                // Record error to Crashlytics
                CrashlyticsErrorRecorder.recordError(error, context: .deepLinkNavigation)
                return false
            }

        case let .resumeTest(sessionId):
            // Session resumption is not yet implemented - we cannot resume a specific session.
            // Navigating to a fresh test would violate user expectations.
            // See ICG-132 for full session resumption implementation.
            Self.logger.warning(
                """
                Resume test deep link received for sessionId: \(sessionId, privacy: .public). \
                Session resumption not yet implemented - deep link cannot be handled.
                """
            )
            return false

        case .settings:
            // Settings navigation is handled at the tab level in MainTabView.
            // This case should never be reached - if it is, there's a bug in the deep link routing logic.
            Self.logger.error("Settings deep link incorrectly routed to handleNavigation - programming error")
            fatalError("Settings deep link should be handled in MainTabView, not via router navigation")

        case .invalid:
            Self.logger.warning("Attempted to navigate with invalid deep link")
            return false
        }
    }
}
