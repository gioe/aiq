import AIQSharedKit
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
/// Deep links can come from URL schemes (aiq://) or universal links (https://a-iq-test.com/...).
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
    /// Universal link (https://a-iq-test.com or https://dev.a-iq-test.com)
    case universalLink = "universal_link"
    /// Unknown source
    case unknown
}

/// Convert a DeepLinkError to an analytics-friendly error type string
func deepLinkErrorTypeString(from error: DeepLinkError) -> String {
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
