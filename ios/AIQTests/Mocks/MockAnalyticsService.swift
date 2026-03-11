@testable import AIQ
import Foundation

/// Mock AnalyticsService for testing analytics tracking across features
///
/// Subclasses the real AnalyticsService to capture tracking calls without actually
/// sending analytics events. This is necessary because AnalyticsService is not
/// protocol-based, so we use class inheritance for testing.
///
/// Covers: deep link navigation, active session detection, test resume, and test abandonment.
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
    private(set) var trackTestResumedFromDashboardCalled = false
    private(set) var trackTestAbandonedFromDashboardCalled = false
    private(set) var trackActiveSessionDetectedCalled = false
    private(set) var trackActiveSessionDetectedCallCount = 0

    // MARK: - Parameter Capture

    private(set) var lastSuccessDestinationType: String?
    private(set) var lastSuccessSource: String?
    private(set) var lastSuccessURL: String?

    private(set) var lastFailedErrorType: String?
    private(set) var lastFailedSource: String?
    private(set) var lastFailedURL: String?

    private(set) var lastResumedSessionId: Int?
    private(set) var lastResumedQuestionsAnswered: Int?

    private(set) var lastAbandonedSessionId: Int?
    private(set) var lastAbandonedQuestionsAnswered: Int?

    private(set) var lastDetectedSessionId: Int?
    private(set) var lastDetectedQuestionsAnswered: Int?

    // MARK: - Initialization

    init() {
        // Initialize with test-friendly settings
        // - Don't start timer to avoid background batch submissions during tests
        // - Disable auto-submit to prevent race conditions
        super.init(
            userDefaults: .standard,
            networkMonitor: NetworkMonitor.shared,
            urlSession: .shared,
            secureStorage: KeychainStorage(),
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
        trackTestResumedFromDashboardCalled = false
        lastResumedSessionId = nil
        lastResumedQuestionsAnswered = nil
        trackTestAbandonedFromDashboardCalled = false
        lastAbandonedSessionId = nil
        lastAbandonedQuestionsAnswered = nil
        trackActiveSessionDetectedCalled = false
        trackActiveSessionDetectedCallCount = 0
        lastDetectedSessionId = nil
        lastDetectedQuestionsAnswered = nil
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

    override func trackTestResumedFromDashboard(sessionId: Int, questionsAnswered: Int) {
        trackTestResumedFromDashboardCalled = true
        lastResumedSessionId = sessionId
        lastResumedQuestionsAnswered = questionsAnswered

        // Don't call super to avoid actually tracking events in tests
    }

    override func trackTestAbandonedFromDashboard(sessionId: Int, questionsAnswered: Int) {
        trackTestAbandonedFromDashboardCalled = true
        lastAbandonedSessionId = sessionId
        lastAbandonedQuestionsAnswered = questionsAnswered

        // Don't call super to avoid actually tracking events in tests
    }

    override func trackActiveSessionDetected(sessionId: Int, questionsAnswered: Int) {
        trackActiveSessionDetectedCalled = true
        trackActiveSessionDetectedCallCount += 1
        lastDetectedSessionId = sessionId
        lastDetectedQuestionsAnswered = questionsAnswered

        // Don't call super to avoid actually tracking events in tests
    }
}
