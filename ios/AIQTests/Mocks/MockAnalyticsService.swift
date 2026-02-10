@testable import AIQ
import Foundation

/// Mock AnalyticsService for testing deep link analytics tracking
///
/// Subclasses the real AnalyticsService to capture tracking calls without actually
/// sending analytics events. This is necessary because AnalyticsService is not
/// protocol-based, so we use class inheritance for testing.
///
/// ## Usage in Tests
///
/// ```swift
/// let mockAnalytics = MockAnalyticsService()
/// let handler = DeepLinkHandler(analyticsService: mockAnalytics)
///
/// // Exercise the handler...
///
/// XCTAssertTrue(mockAnalytics.trackDeepLinkSuccessCalled)
/// XCTAssertEqual(mockAnalytics.lastSuccessDestinationType, "test_results")
/// ```
final class MockAnalyticsService: AnalyticsService {
    // MARK: - Call Tracking

    private(set) var trackDeepLinkSuccessCalled = false
    private(set) var trackDeepLinkFailedCalled = false

    // MARK: - Parameter Capture

    private(set) var lastSuccessDestinationType: String?
    private(set) var lastSuccessSource: String?
    private(set) var lastSuccessURL: String?

    private(set) var lastFailedErrorType: String?
    private(set) var lastFailedSource: String?
    private(set) var lastFailedURL: String?

    // MARK: - Initialization

    init() {
        // Initialize with test-friendly settings
        // - Don't start timer to avoid background batch submissions during tests
        // - Disable auto-submit to prevent race conditions
        super.init(
            userDefaults: .standard,
            networkMonitor: NetworkMonitor.shared,
            urlSession: .shared,
            secureStorage: KeychainStorage.shared,
            batchInterval: 60.0,
            startTimer: false,
            autoSubmitWhenFull: false
        )
    }

    // MARK: - Reset

    /// Reset all call tracking and captured parameters
    func reset() {
        trackDeepLinkSuccessCalled = false
        trackDeepLinkFailedCalled = false
        lastSuccessDestinationType = nil
        lastSuccessSource = nil
        lastSuccessURL = nil
        lastFailedErrorType = nil
        lastFailedSource = nil
        lastFailedURL = nil
    }

    // MARK: - Overrides

    override func trackDeepLinkNavigationSuccess(
        destinationType: String,
        source: String,
        url: String
    ) {
        trackDeepLinkSuccessCalled = true
        lastSuccessDestinationType = destinationType
        lastSuccessSource = source
        lastSuccessURL = url

        // Don't call super to avoid actually tracking events in tests
    }

    override func trackDeepLinkNavigationFailed(
        errorType: String,
        source: String,
        url: String
    ) {
        trackDeepLinkFailedCalled = true
        lastFailedErrorType = errorType
        lastFailedSource = source
        lastFailedURL = url

        // Don't call super to avoid actually tracking events in tests
    }
}
