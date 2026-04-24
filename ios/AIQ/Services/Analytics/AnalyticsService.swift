import AIQSharedKit
import Foundation

// MARK: - App-Level Analytics Event Names

/// Analytics event types for tracking user actions and system events.
///
/// Each case maps to a backend event name string. Use these with the
/// `AnalyticsManagerProtocol` convenience extensions below.
enum AIQAnalyticsEvent: String {
    // Authentication events
    case userRegistered = "user.registered"
    case userLogin = "user.login"
    case userLogout = "user.logout"
    case tokenRefreshed = "user.token_refreshed"

    // Test session events
    case testStarted = "test.started"
    case testCompleted = "test.completed"
    case testAbandoned = "test.abandoned"
    case testAbandonedFromDashboard = "test.abandoned_from_dashboard"
    case testResumedFromDashboard = "test.resumed_from_dashboard"
    case activeSessionConflict = "test.active_session_conflict"
    case activeSessionErrorRecovered = "test.active_session_error_recovered"
    case activeSessionDetected = "test.active_session_detected"

    // Question events
    case questionAnswered = "question.answered"
    case questionSkipped = "question.skipped"

    // Performance events
    case slowAPIRequest = "performance.slow_api_request"
    case apiError = "api.error"

    // Security events
    case authFailed = "security.auth_failed"
    case certificatePinningInitialized = "security.certificate_pinning.initialized"
    case certificatePinningInitializationFailed = "security.certificate_pinning.initialization_failed"

    /// Account events
    case accountDeleted = "account.deleted"

    // Background refresh events
    case backgroundRefreshCompleted = "background.refresh.completed"
    case backgroundRefreshFailed = "background.refresh.failed"
    case backgroundRefreshExpired = "background.refresh.expired"
    case backgroundRefreshScheduleFailed = "background.refresh.schedule_failed"
    case backgroundRefreshNotificationSent = "background.refresh.notification_sent"
    case backgroundRefreshNotificationFailed = "background.refresh.notification_failed"

    // Notification engagement events
    case notificationTapped = "notification.tapped"
    case notificationUpgradePromptShown = "notification.upgrade_prompt.shown"
    case notificationUpgradePromptAccepted = "notification.upgrade_prompt.accepted"
    case notificationUpgradePromptDismissed = "notification.upgrade_prompt.dismissed"
    case notificationFullPermissionGranted = "notification.full_permission.granted"
    case notificationFullPermissionDenied = "notification.full_permission.denied"

    // Deep link events
    case deepLinkNavigationSuccess = "deeplink.navigation.success"
    case deepLinkNavigationFailed = "deeplink.navigation.failed"

    // Guest conversion events
    case guestResultViewed = "guest_conversion.result_viewed"
    case guestConversionStarted = "guest_conversion.started"
    case guestConversionAuthSucceeded = "guest_conversion.auth_succeeded"
    case guestConversionAuthFailed = "guest_conversion.auth_failed"
    case guestConversionClaimSucceeded = "guest_conversion.claim_succeeded"
    case guestConversionClaimFailed = "guest_conversion.claim_failed"
    case guestConversionMaybeLaterDismissed = "guest_conversion.maybe_later_dismissed"
}

enum SignInProvider: String {
    case password
    case apple
    case google
}

enum GuestConversionPath: String {
    case apple
    case google
    case email
}

// MARK: - AnalyticsManagerProtocol Convenience Extensions

extension AnalyticsManagerProtocol {
    /// Track an AIQ analytics event with optional properties
    func track(event: AIQAnalyticsEvent, properties: [String: Any]? = nil) {
        track(AnalyticsEvent(name: event.rawValue, parameters: properties))
    }

    // MARK: - Authentication

    func trackUserRegistered(email: String) {
        track(event: .userRegistered, properties: [
            "email_domain": emailDomain(from: email)
        ])
    }

    func trackUserLogin(email: String, provider: SignInProvider) {
        track(event: .userLogin, properties: [
            "email_domain": emailDomain(from: email),
            "provider": provider.rawValue
        ])
    }

    func trackUserLogout() {
        track(event: .userLogout)
    }

    // MARK: - Test Sessions

    func trackTestStarted(sessionId: Int, questionCount: Int) {
        track(event: .testStarted, properties: [
            "session_id": sessionId,
            "question_count": questionCount
        ])
    }

    func trackTestCompleted(sessionId: Int, iqScore: Int, durationSeconds: Int, accuracy: Double) {
        track(event: .testCompleted, properties: [
            "session_id": sessionId,
            "iq_score": iqScore,
            "duration_seconds": durationSeconds,
            "accuracy_percentage": accuracy
        ])
    }

    func trackTestAbandoned(sessionId: Int, answeredCount: Int) {
        track(event: .testAbandoned, properties: [
            "session_id": sessionId,
            "answered_count": answeredCount
        ])
    }

    func trackActiveSessionConflict(sessionId: Int) {
        track(event: .activeSessionConflict, properties: [
            "session_id": sessionId
        ])
    }

    func trackTestResumedFromDashboard(sessionId: Int, questionsAnswered: Int) {
        track(event: .testResumedFromDashboard, properties: [
            "session_id": sessionId,
            "questions_answered": questionsAnswered
        ])
    }

    func trackTestAbandonedFromDashboard(sessionId: Int, questionsAnswered: Int) {
        track(event: .testAbandonedFromDashboard, properties: [
            "session_id": sessionId,
            "questions_answered": questionsAnswered
        ])
    }

    func trackActiveSessionErrorRecovered(sessionId: Int, recoveryAction: String) {
        track(event: .activeSessionErrorRecovered, properties: [
            "session_id": sessionId,
            "recovery_action": recoveryAction
        ])
    }

    func trackActiveSessionDetected(sessionId: Int, questionsAnswered: Int) {
        track(event: .activeSessionDetected, properties: [
            "session_id": sessionId,
            "questions_answered": questionsAnswered
        ])
    }

    // MARK: - Performance & Errors

    func trackSlowRequest(endpoint: String, durationSeconds: Double, statusCode: Int) {
        track(event: .slowAPIRequest, properties: [
            "endpoint": endpoint,
            "duration_seconds": durationSeconds,
            "status_code": statusCode
        ])
    }

    func trackAPIError(endpoint: String, error: Error, statusCode: Int? = nil) {
        var properties: [String: Any] = [
            "endpoint": endpoint,
            "error_type": String(describing: type(of: error)),
            "error_message": error.localizedDescription
        ]
        if let statusCode {
            properties["status_code"] = statusCode
        }
        track(event: .apiError, properties: properties)
    }

    func trackAuthFailed(reason: String) {
        track(event: .authFailed, properties: ["reason": reason])
    }

    // MARK: - Guest Conversion

    func trackGuestResultViewed(sessionId: Int, hasClaimToken: Bool) {
        track(event: .guestResultViewed, properties: [
            "session_id": sessionId,
            "has_claim_token": hasClaimToken
        ])
    }

    func trackGuestConversionStarted(path: GuestConversionPath) {
        track(event: .guestConversionStarted, properties: [
            "path": path.rawValue
        ])
    }

    func trackGuestConversionAuthSucceeded(path: GuestConversionPath) {
        track(event: .guestConversionAuthSucceeded, properties: [
            "path": path.rawValue
        ])
    }

    func trackGuestConversionAuthFailed(path: GuestConversionPath, error: Error) {
        track(event: .guestConversionAuthFailed, properties: guestConversionFailureProperties(
            path: path,
            error: error
        ))
    }

    func trackGuestConversionClaimSucceeded(path: GuestConversionPath) {
        track(event: .guestConversionClaimSucceeded, properties: [
            "path": path.rawValue
        ])
    }

    func trackGuestConversionClaimFailed(path: GuestConversionPath, error: Error) {
        track(event: .guestConversionClaimFailed, properties: guestConversionFailureProperties(
            path: path,
            error: error
        ))
    }

    func trackGuestConversionMaybeLaterDismissed() {
        track(event: .guestConversionMaybeLaterDismissed)
    }

    // MARK: - Security

    func trackCertificatePinningInitialized(domain: String, pinCount: Int) {
        track(event: .certificatePinningInitialized, properties: [
            "domain": domain,
            "pin_count": pinCount
        ])
    }

    func trackCertificatePinningInitializationFailed(reason: String, domain: String? = nil) {
        var properties: [String: Any] = ["reason": reason]
        if let domain {
            properties["domain"] = domain
        }
        track(event: .certificatePinningInitializationFailed, properties: properties)
    }

    // MARK: - Notifications

    func trackNotificationTapped(notificationType: String, authorizationStatus: String) {
        track(event: .notificationTapped, properties: [
            "notification_type": notificationType,
            "authorization_status": authorizationStatus
        ])
    }

    func trackNotificationUpgradePromptShown(notificationType: String) {
        track(event: .notificationUpgradePromptShown, properties: [
            "notification_type": notificationType
        ])
    }

    func trackNotificationUpgradePromptAccepted() {
        track(event: .notificationUpgradePromptAccepted)
    }

    func trackNotificationUpgradePromptDismissed() {
        track(event: .notificationUpgradePromptDismissed)
    }

    func trackNotificationFullPermissionGranted() {
        track(event: .notificationFullPermissionGranted)
    }

    func trackNotificationFullPermissionDenied() {
        track(event: .notificationFullPermissionDenied)
    }

    // MARK: - Deep Links

    func trackDeepLinkNavigationSuccess(destinationType: String, source: String, url: String) {
        track(event: .deepLinkNavigationSuccess, properties: [
            "destination_type": destinationType,
            "source": source,
            "url_scheme": extractScheme(from: url)
        ])
    }

    func trackDeepLinkNavigationFailed(errorType: String, source: String, url: String) {
        track(event: .deepLinkNavigationFailed, properties: [
            "error_type": errorType,
            "source": source,
            "url_scheme": extractScheme(from: url)
        ])
    }

    // MARK: - Background Refresh

    func trackBackgroundRefreshCompleted() {
        track(event: .backgroundRefreshCompleted)
    }

    func trackBackgroundRefreshFailed() {
        track(event: .backgroundRefreshFailed)
    }

    func trackBackgroundRefreshExpired() {
        track(event: .backgroundRefreshExpired)
    }

    func trackBackgroundRefreshScheduleFailed() {
        track(event: .backgroundRefreshScheduleFailed)
    }

    func trackBackgroundRefreshNotificationSent() {
        track(event: .backgroundRefreshNotificationSent)
    }

    func trackBackgroundRefreshNotificationFailed() {
        track(event: .backgroundRefreshNotificationFailed)
    }

    // MARK: - Account

    func trackAccountDeleted() {
        track(event: .accountDeleted)
    }

    // MARK: - Private Helpers

    private func emailDomain(from email: String) -> String {
        guard let atIndex = email.firstIndex(of: "@") else {
            return "unknown"
        }
        return String(email[email.index(after: atIndex)...])
    }

    private func extractScheme(from urlString: String) -> String {
        guard let url = URL(string: urlString) else { return "unknown" }
        return url.scheme ?? "unknown"
    }

    private func guestConversionFailureProperties(
        path: GuestConversionPath,
        error: Error
    ) -> [String: Any] {
        [
            "path": path.rawValue,
            "error_type": String(describing: type(of: error))
        ]
    }
}
