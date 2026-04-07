import AIQSharedKit
import Foundation
import os

/// Parses AIQ deep link URLs into navigation actions using SharedKit's ``DeepLinkParser`` protocol.
///
/// Supports both URL schemes (aiq://) and universal links (https://aiq.app/..., https://dev.aiq.app/...).
/// Returns a ``DeepLinkAction`` describing the navigation to perform, or `nil` for unrecognized URLs.
///
/// Supported URL patterns:
/// - `aiq://test/results/{id}` - View specific test results
/// - `aiq://test/resume/{sessionId}` - Resume a test session
/// - `aiq://settings` - Open settings (returns nil — handled at tab level by DeepLinkNavigationService)
/// - `https://aiq.app/...` and `https://dev.aiq.app/...` - Same patterns as universal links
///
/// ## Async Routes
/// Some deep link destinations require async data fetching before navigation (e.g., test results
/// need an API call to fetch the full TestResult). For these routes, the parser returns a
/// ``DeepLink`` enum value via the ``parseDeepLink(_:)`` method, and the navigation service
/// handles the async resolution and coordinator routing.
///
/// ## Settings Navigation
/// Settings deep links are handled at the tab level (switching to the settings tab) rather than
/// via coordinator push. The parser returns `nil` for settings URLs, and the navigation service
/// handles tab switching directly.
struct AIQDeepLinkParser: DeepLinkParser {
    typealias Route = AIQ.Route

    private static let logger = Logger(subsystem: "com.aiq.app", category: "AIQDeepLinkParser")

    /// URL scheme for AIQ deep links (aiq://)
    private static let urlScheme = "aiq"

    /// Universal link hosts (production and development)
    private static let universalLinkHosts = ["aiq.app", "dev.aiq.app"]

    /// Analytics manager for tracking malformed deep link events
    private let analyticsManager: AnalyticsManagerProtocol

    init(analyticsManager: AnalyticsManagerProtocol = ServiceContainer.shared.resolve()) {
        self.analyticsManager = analyticsManager
    }

    // MARK: - DeepLinkParser Conformance

    /// Parse a URL into a navigation action for the coordinator.
    ///
    /// Returns `nil` for:
    /// - Unrecognized URLs
    /// - Settings deep links (handled at tab level)
    /// - Test results deep links (require async API call — use ``parseDeepLink(_:)`` instead)
    func parse(url: URL) -> DeepLinkAction<Route>? {
        let deepLink = parseDeepLink(url)

        switch deepLink {
        case let .resumeTest(sessionId):
            return .popToRootThenPush(.testTaking(sessionId: sessionId))
        case .testResults:
            // Requires async API call to fetch TestResult — handled by DeepLinkNavigationService
            return nil
        case .settings:
            // Handled at tab level by DeepLinkNavigationService
            return nil
        case .invalid:
            return nil
        }
    }

    // MARK: - Deep Link Parsing

    /// Parse a URL into a structured DeepLink enum value.
    ///
    /// This method is used by ``DeepLinkNavigationService`` for routes that need
    /// async resolution or tab-level handling (where the ``DeepLinkParser`` protocol's
    /// synchronous ``parse(url:)`` returns `nil`).
    func parseDeepLink(_ url: URL) -> DeepLink {
        if url.scheme == Self.urlScheme {
            return parseURLScheme(url)
        } else if url.scheme == "https", let host = url.host, Self.universalLinkHosts.contains(host) {
            return parseUniversalLink(url)
        }

        recordInvalidDeepLink(.unrecognizedSchemeOrHost(url: url.absoluteString))
        return .invalid
    }

    // MARK: - Private Helpers

    private func recordInvalidDeepLink(_ error: DeepLinkError) {
        Self.logger.warning("\(error.localizedDescription, privacy: .public)")
        CrashlyticsErrorRecorder.recordError(error, context: .deepLinkParse)
    }

    private func parseURLScheme(_ url: URL) -> DeepLink {
        let host = url.host ?? ""
        let pathComponents = url.pathComponents.filter { $0 != "/" }
        return parsePathComponents(host: host, pathComponents: pathComponents, originalURL: url)
    }

    private func parseUniversalLink(_ url: URL) -> DeepLink {
        let pathComponents = url.pathComponents.filter { $0 != "/" }

        guard !pathComponents.isEmpty else {
            recordInvalidDeepLink(.emptyPath(url: url.absoluteString))
            return .invalid
        }

        let host = pathComponents[0]
        let remainingComponents = Array(pathComponents.dropFirst())
        return parsePathComponents(host: host, pathComponents: remainingComponents, originalURL: url)
    }

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

    private func parseTestRoute(pathComponents: [String], originalURL: URL) -> DeepLink {
        guard pathComponents.count >= 2 else {
            recordInvalidDeepLink(.missingTestActionOrID(url: originalURL.absoluteString))
            return .invalid
        }

        let action = pathComponents[0]
        let identifier = pathComponents[1]

        if pathComponents.count > 2 {
            let extraComponents = Array(pathComponents.dropFirst(2))
            Self.logger.warning(
                """
                Deep link has extra path components that will be ignored: \
                \(extraComponents, privacy: .auto) in URL: \(originalURL, privacy: .auto)
                """
            )
        }

        switch action {
        case "results":
            guard let id = Int(identifier) else {
                recordInvalidDeepLink(.invalidTestResultsID(identifier: identifier, url: originalURL.absoluteString))
                return .invalid
            }
            guard id > 0 else {
                recordInvalidDeepLink(.nonPositiveTestResultsID(id: id, url: originalURL.absoluteString))
                return .invalid
            }
            return .testResults(id: id)

        case "resume":
            guard let sessionId = Int(identifier) else {
                recordInvalidDeepLink(.invalidSessionID(identifier: identifier, url: originalURL.absoluteString))
                return .invalid
            }
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

    private func parseSettingsRoute(pathComponents: [String], originalURL: URL) -> DeepLink {
        if !pathComponents.isEmpty {
            Self.logger.warning(
                """
                Deep link has extra path components that will be ignored: \
                \(pathComponents, privacy: .auto) in URL: \(originalURL, privacy: .auto)
                """
            )

            analyticsManager.trackDeepLinkNavigationFailed(
                errorType: "malformed_settings_extra_components",
                source: "unknown",
                url: originalURL.absoluteString
            )
        }
        return .settings
    }
}
