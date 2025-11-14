import Foundation
import OSLog

/// Analytics event types for tracking user actions and system events
enum AnalyticsEvent: String {
    // Authentication events
    case userRegistered = "user.registered"
    case userLogin = "user.login"
    case userLogout = "user.logout"
    case tokenRefreshed = "user.token_refreshed"

    // Test session events
    case testStarted = "test.started"
    case testCompleted = "test.completed"
    case testAbandoned = "test.abandoned"

    // Question events
    case questionAnswered = "question.answered"
    case questionSkipped = "question.skipped"

    // Performance events
    case slowAPIRequest = "performance.slow_api_request"
    case apiError = "api.error"

    // Security events
    case authFailed = "security.auth_failed"
}

/// Analytics service for logging and monitoring user actions in the iOS app
///
/// Uses Apple's unified logging system (os_log) for structured logging.
/// Events can be viewed in Console.app or via `log stream` command.
class AnalyticsService {
    /// Shared singleton instance
    static let shared = AnalyticsService()

    /// Logger instance for analytics events
    private let logger: Logger

    /// Logger instance for performance events
    private let performanceLogger: Logger

    /// Logger instance for error events
    private let errorLogger: Logger

    private init() {
        // Create separate loggers for different categories
        logger = Logger(subsystem: "com.iqtracker.app", category: "analytics")
        performanceLogger = Logger(subsystem: "com.iqtracker.app", category: "performance")
        errorLogger = Logger(subsystem: "com.iqtracker.app", category: "errors")
    }

    // MARK: - Public Methods

    /// Track an analytics event
    ///
    /// - Parameters:
    ///   - event: The type of event to track
    ///   - properties: Optional dictionary of event properties
    func track(event: AnalyticsEvent, properties: [String: Any]? = nil) {
        let propertiesString = properties?.description ?? "{}"
        logger.info("📊 Analytics Event: \(event.rawValue) | Properties: \(propertiesString)")

        // In production, send to external analytics service
        // Example: Firebase Analytics, Mixpanel, etc.
        #if PRODUCTION
            // Future: Integrate with external analytics service (e.g., Firebase, Mixpanel)
        #endif
    }

    /// Track user registration
    ///
    /// - Parameter email: User's email address (sanitized)
    func trackUserRegistered(email: String) {
        track(event: .userRegistered, properties: [
            "email_domain": emailDomain(from: email)
        ])
    }

    /// Track user login
    ///
    /// - Parameter email: User's email address (sanitized)
    func trackUserLogin(email: String) {
        track(event: .userLogin, properties: [
            "email_domain": emailDomain(from: email)
        ])
    }

    /// Track user logout
    func trackUserLogout() {
        track(event: .userLogout)
    }

    /// Track test session start
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID
    ///   - questionCount: Number of questions in the test
    func trackTestStarted(sessionId: Int, questionCount: Int) {
        track(event: .testStarted, properties: [
            "session_id": sessionId,
            "question_count": questionCount
        ])
    }

    /// Track test completion
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID
    ///   - iqScore: Final IQ score
    ///   - durationSeconds: Time taken to complete test
    ///   - accuracy: Accuracy percentage
    func trackTestCompleted(sessionId: Int, iqScore: Int, durationSeconds: Int, accuracy: Double) {
        track(event: .testCompleted, properties: [
            "session_id": sessionId,
            "iq_score": iqScore,
            "duration_seconds": durationSeconds,
            "accuracy_percentage": accuracy
        ])
    }

    /// Track test abandonment
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID
    ///   - answeredCount: Number of questions answered before abandonment
    func trackTestAbandoned(sessionId: Int, answeredCount: Int) {
        track(event: .testAbandoned, properties: [
            "session_id": sessionId,
            "answered_count": answeredCount
        ])
    }

    /// Track slow API request
    ///
    /// - Parameters:
    ///   - endpoint: API endpoint path
    ///   - durationSeconds: Request duration
    ///   - statusCode: HTTP status code
    func trackSlowRequest(endpoint: String, durationSeconds: Double, statusCode: Int) {
        let message = "⚠️ Slow API Request: \(endpoint) took \(durationSeconds, format: .fixed(precision: 2))s"
        performanceLogger.warning("\(message) | Status: \(statusCode)")

        track(event: .slowAPIRequest, properties: [
            "endpoint": endpoint,
            "duration_seconds": durationSeconds,
            "status_code": statusCode
        ])
    }

    /// Track API error
    ///
    /// - Parameters:
    ///   - endpoint: API endpoint path
    ///   - error: Error that occurred
    ///   - statusCode: HTTP status code if available
    func trackAPIError(endpoint: String, error: Error, statusCode: Int? = nil) {
        var properties: [String: Any] = [
            "endpoint": endpoint,
            "error_type": String(describing: type(of: error)),
            "error_message": error.localizedDescription
        ]

        if let statusCode {
            properties["status_code"] = statusCode
        }

        errorLogger.error("❌ API Error: \(endpoint) | Error: \(error.localizedDescription)")

        track(event: .apiError, properties: properties)
    }

    /// Track authentication failure
    ///
    /// - Parameter reason: Reason for authentication failure
    func trackAuthFailed(reason: String) {
        errorLogger.error("🔐 Auth Failed: \(reason)")

        track(event: .authFailed, properties: [
            "reason": reason
        ])
    }

    // MARK: - Private Helpers

    /// Extract domain from email for privacy-preserving analytics
    ///
    /// - Parameter email: Full email address
    /// - Returns: Domain portion only (e.g., "gmail.com")
    private func emailDomain(from email: String) -> String {
        guard let atIndex = email.firstIndex(of: "@") else {
            return "unknown"
        }
        return String(email[email.index(after: atIndex)...])
    }
}
