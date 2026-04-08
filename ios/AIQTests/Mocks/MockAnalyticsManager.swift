@testable import AIQ
import AIQSharedKit
import Foundation

/// Mock AnalyticsManager for testing analytics tracking across features
///
/// Captures all tracked events for assertion in tests. Since the convenience tracking
/// methods (e.g., `trackDeepLinkNavigationSuccess`) are protocol extensions on
/// `AnalyticsManagerProtocol`, they call through to `track(_:)` which this mock captures.
///
/// ## Usage in Tests
///
/// ```swift
/// let mockAnalytics = MockAnalyticsManager()
/// let handler = DeepLinkHandler(analyticsManager: mockAnalytics)
///
/// // Exercise the handler...
///
/// #expect(mockAnalytics.trackDeepLinkSuccessCalled)
/// #expect(mockAnalytics.lastSuccessDestinationType == "test_results")
/// ```
final class MockAnalyticsManager: AnalyticsManagerProtocol {
    // MARK: - Raw Capture

    private(set) var trackedEvents: [AnalyticsEvent] = []
    private(set) var trackedScreens: [(name: String, parameters: [String: Any]?)] = []
    private(set) var userProperties: [String: String?] = [:]
    private(set) var userID: String?
    private(set) var resetCount = 0

    // MARK: - AnalyticsManagerProtocol

    func addProvider(_: AnalyticsProvider) {}

    func track(_ event: AnalyticsEvent) {
        trackedEvents.append(event)
    }

    func track(_ name: String, parameters: [String: Any]?) {
        trackedEvents.append(AnalyticsEvent(name: name, parameters: parameters))
    }

    func trackScreen(_ name: String, parameters: [String: Any]?) {
        trackedScreens.append((name, parameters))
    }

    func setUserProperty(_ value: String?, forName name: String) {
        userProperties[name] = value
    }

    func setUserID(_ userID: String?) {
        self.userID = userID
    }

    func reset() {
        resetCount += 1
    }

    // MARK: - Convenience Queries

    /// Reset all captured data
    func resetCaptures() {
        trackedEvents.removeAll()
        trackedScreens.removeAll()
        userProperties.removeAll()
        userID = nil
        resetCount = 0
    }

    /// Find all events matching a given AIQ event type
    func events(ofType type: AIQAnalyticsEvent) -> [AnalyticsEvent] {
        trackedEvents.filter { $0.name == type.rawValue }
    }

    /// Check if an event of the given type was tracked
    func wasTracked(_ type: AIQAnalyticsEvent) -> Bool {
        trackedEvents.contains { $0.name == type.rawValue }
    }

    /// Get the last event of a given type
    func lastEvent(ofType type: AIQAnalyticsEvent) -> AnalyticsEvent? {
        trackedEvents.last { $0.name == type.rawValue }
    }

    // MARK: - Legacy-Compatible Computed Properties

    var trackDeepLinkSuccessCalled: Bool {
        wasTracked(.deepLinkNavigationSuccess)
    }

    var trackDeepLinkFailedCalled: Bool {
        wasTracked(.deepLinkNavigationFailed)
    }

    var trackTestResumedFromDashboardCalled: Bool {
        wasTracked(.testResumedFromDashboard)
    }

    var trackTestAbandonedFromDashboardCalled: Bool {
        wasTracked(.testAbandonedFromDashboard)
    }

    var trackActiveSessionDetectedCalled: Bool {
        wasTracked(.activeSessionDetected)
    }

    var trackActiveSessionDetectedCallCount: Int {
        events(ofType: .activeSessionDetected).count
    }

    var lastSuccessDestinationType: String? {
        lastEvent(ofType: .deepLinkNavigationSuccess)?.parameters?["destination_type"] as? String
    }

    var lastSuccessSource: String? {
        lastEvent(ofType: .deepLinkNavigationSuccess)?.parameters?["source"] as? String
    }

    var lastSuccessURL: String? {
        lastEvent(ofType: .deepLinkNavigationSuccess)?.parameters?["url_scheme"] as? String
    }

    var lastFailedErrorType: String? {
        lastEvent(ofType: .deepLinkNavigationFailed)?.parameters?["error_type"] as? String
    }

    var lastFailedSource: String? {
        lastEvent(ofType: .deepLinkNavigationFailed)?.parameters?["source"] as? String
    }

    var lastFailedURLScheme: String? {
        lastEvent(ofType: .deepLinkNavigationFailed)?.parameters?["url_scheme"] as? String
    }

    var lastResumedSessionId: Int? {
        lastEvent(ofType: .testResumedFromDashboard)?.parameters?["session_id"] as? Int
    }

    var lastResumedQuestionsAnswered: Int? {
        lastEvent(ofType: .testResumedFromDashboard)?.parameters?["questions_answered"] as? Int
    }

    var lastAbandonedSessionId: Int? {
        lastEvent(ofType: .testAbandonedFromDashboard)?.parameters?["session_id"] as? Int
    }

    var lastAbandonedQuestionsAnswered: Int? {
        lastEvent(ofType: .testAbandonedFromDashboard)?.parameters?["questions_answered"] as? Int
    }

    var lastDetectedSessionId: Int? {
        lastEvent(ofType: .activeSessionDetected)?.parameters?["session_id"] as? Int
    }

    var lastDetectedQuestionsAnswered: Int? {
        lastEvent(ofType: .activeSessionDetected)?.parameters?["questions_answered"] as? Int
    }
}
