@testable import AIQ
import Foundation

/// Mock/spy implementation of DeepLinkHandlerProtocol for testing
///
/// Captures all method calls and their parameters so tests can verify
/// that DeepLinkNavigationService delegates to the handler correctly.
///
/// Uses a class (not actor) for simpler test ergonomics. Tests run sequentially
/// within a test class, so actor isolation is unnecessary overhead.
final class MockDeepLinkHandler: DeepLinkHandlerProtocol, @unchecked Sendable {
    // MARK: - Call Tracking

    private(set) var parseCalled = false
    private(set) var parseCallCount = 0
    private(set) var handleNavigationCalled = false
    private(set) var handleNavigationCallCount = 0
    private(set) var trackNavigationSuccessCalled = false
    private(set) var trackNavigationSuccessCallCount = 0
    private(set) var trackParseFailedCalled = false
    private(set) var trackParseFailedCallCount = 0

    // MARK: - Parameter Capture

    private(set) var lastParseURL: URL?
    private(set) var lastHandleNavigationDeepLink: DeepLink?
    private(set) var lastHandleNavigationRouter: AppRouter?
    private(set) var lastHandleNavigationTab: TabDestination?
    private(set) var lastHandleNavigationSource: DeepLinkSource?
    private(set) var lastHandleNavigationOriginalURL: String?
    private(set) var lastTrackSuccessDeepLink: DeepLink?
    private(set) var lastTrackSuccessSource: DeepLinkSource?
    private(set) var lastTrackSuccessOriginalURL: String?
    private(set) var lastTrackParseFailedError: DeepLinkError?
    private(set) var lastTrackParseFailedSource: DeepLinkSource?
    private(set) var lastTrackParseFailedOriginalURL: String?

    // MARK: - Response Stubs

    /// The DeepLink to return from parse(). Defaults to .invalid.
    var parseResult: DeepLink = .invalid

    /// Whether handleNavigation should return success. Defaults to true.
    var handleNavigationResult: Bool = true

    // MARK: - DeepLinkHandlerProtocol

    func parse(_ url: URL) -> DeepLink {
        parseCalled = true
        parseCallCount += 1
        lastParseURL = url
        return parseResult
    }

    @MainActor
    func handleNavigation(
        _ deepLink: DeepLink,
        router: AppRouter,
        tab: TabDestination?,
        source: DeepLinkSource,
        originalURL: String
    ) async -> Bool {
        handleNavigationCalled = true
        handleNavigationCallCount += 1
        lastHandleNavigationDeepLink = deepLink
        lastHandleNavigationRouter = router
        lastHandleNavigationTab = tab
        lastHandleNavigationSource = source
        lastHandleNavigationOriginalURL = originalURL
        return handleNavigationResult
    }

    func trackNavigationSuccess(
        _ deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) {
        trackNavigationSuccessCalled = true
        trackNavigationSuccessCallCount += 1
        lastTrackSuccessDeepLink = deepLink
        lastTrackSuccessSource = source
        lastTrackSuccessOriginalURL = originalURL
    }

    func trackParseFailed(
        error: DeepLinkError,
        source: DeepLinkSource,
        originalURL: String
    ) {
        trackParseFailedCalled = true
        trackParseFailedCallCount += 1
        lastTrackParseFailedError = error
        lastTrackParseFailedSource = source
        lastTrackParseFailedOriginalURL = originalURL
    }

    // MARK: - Convenience

    /// Reset all tracking state
    func reset() {
        parseCalled = false
        parseCallCount = 0
        handleNavigationCalled = false
        handleNavigationCallCount = 0
        trackNavigationSuccessCalled = false
        trackNavigationSuccessCallCount = 0
        trackParseFailedCalled = false
        trackParseFailedCallCount = 0

        lastParseURL = nil
        lastHandleNavigationDeepLink = nil
        lastHandleNavigationRouter = nil
        lastHandleNavigationTab = nil
        lastHandleNavigationSource = nil
        lastHandleNavigationOriginalURL = nil
        lastTrackSuccessDeepLink = nil
        lastTrackSuccessSource = nil
        lastTrackSuccessOriginalURL = nil
        lastTrackParseFailedError = nil
        lastTrackParseFailedSource = nil
        lastTrackParseFailedOriginalURL = nil

        parseResult = .invalid
        handleNavigationResult = true
    }
}
