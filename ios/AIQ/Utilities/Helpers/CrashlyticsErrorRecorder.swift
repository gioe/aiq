import FirebaseCrashlytics
import Foundation
import os

/// Centralized error recorder for non-fatal errors to Firebase Crashlytics.
/// This utility sends errors to Crashlytics in production builds while maintaining
/// OSLog output for local debugging.
///
/// ## Usage
/// Instead of just logging errors in catch blocks, use this recorder:
/// ```swift
/// do {
///     try await someOperation()
/// } catch {
///     CrashlyticsErrorRecorder.recordError(error, context: .fetchDashboard)
/// }
/// ```
enum CrashlyticsErrorRecorder {
    /// Context identifiers for categorizing errors in Crashlytics
    enum ErrorContext: String {
        // Authentication
        case login = "auth_login"
        case logout = "auth_logout"
        case registration = "auth_registration"
        case tokenRefresh = "auth_token_refresh"

        // Test Operations
        case startTest = "test_start"
        case submitTest = "test_submit"
        case abandonTest = "test_abandon"
        case resumeTest = "test_resume"
        case fetchQuestions = "test_fetch_questions"

        // Dashboard & History
        case fetchDashboard = "dashboard_fetch"
        case fetchHistory = "history_fetch"
        case fetchActiveSession = "dashboard_active_session"

        // Notifications
        case notificationPreferences = "notification_preferences"
        case notificationPermission = "notification_permission"

        // Feedback
        case submitFeedback = "feedback_submit"

        // Storage & Persistence
        case localSave = "storage_local_save"
        case localLoad = "storage_local_load"
        case storageRetrieve = "storage_retrieve"
        case storageDelete = "storage_delete"

        // Analytics
        case analytics = "analytics_event"

        // Navigation
        case deepLinkParse = "navigation_deeplink_parse"
        case deepLinkNavigation = "navigation_deeplink_navigation"

        // Generic
        case unknown
    }

    private static let logger = Logger(subsystem: "com.aiq.app", category: "Error")

    /// Records a non-fatal error to Crashlytics with context information.
    ///
    /// - Parameters:
    ///   - error: The error to record
    ///   - context: The context/operation where the error occurred
    ///   - additionalInfo: Optional additional key-value pairs for Crashlytics
    ///
    /// ## Behavior
    /// - In DEBUG builds: Logs to OSLog only (for local debugging)
    /// - In RELEASE builds: Records to Crashlytics AND logs to OSLog
    static func recordError(
        _ error: Error,
        context: ErrorContext,
        additionalInfo: [String: Any]? = nil
    ) {
        // Always log to OSLog for debugging
        logger.error("[\(context.rawValue)] \(error.localizedDescription)")

        #if DEBUG
            // In debug builds, print detailed error info
            print("🔴 [\(context.rawValue)] Error: \(error)")
            if let additionalInfo {
                print("   Additional info: \(additionalInfo)")
            }
        #else
            // In release builds, record to Crashlytics
            var userInfo: [String: Any] = [
                "context": context.rawValue,
                "errorType": String(describing: type(of: error))
            ]

            // Add error-specific info
            if let apiError = error as? APIError {
                userInfo["apiErrorCode"] = apiError.errorCode
                userInfo["isRetryable"] = apiError.isRetryable
            } else if let contextualError = error as? ContextualError {
                userInfo["operation"] = contextualError.operation.rawValue
                userInfo["isRetryable"] = contextualError.isRetryable
            }

            // Merge additional info
            if let additionalInfo {
                userInfo.merge(additionalInfo) { _, new in new }
            }

            // Record to Crashlytics
            let nsError = error as NSError
            Crashlytics.crashlytics().record(
                error: nsError,
                userInfo: userInfo
            )
        #endif
    }

    /// Sets user identifier in Crashlytics for better error attribution.
    ///
    /// Call this when user logs in to associate crashes/errors with a user.
    /// - Parameter userId: The user's unique identifier
    static func setUserId(_ userId: String?) {
        #if !DEBUG
            Crashlytics.crashlytics().setUserID(userId ?? "")
        #endif
    }

    /// Logs a custom key-value pair to Crashlytics for debugging.
    ///
    /// - Parameters:
    ///   - key: The key for the custom value
    ///   - value: The value to log
    static func log(key: String, value: String) {
        #if DEBUG
            print("📊 Crashlytics Log: \(key) = \(value)")
        #else
            Crashlytics.crashlytics().setCustomValue(value, forKey: key)
        #endif
    }

    /// Logs a breadcrumb message to Crashlytics.
    ///
    /// Use this to track the user's journey through the app for debugging.
    /// - Parameter message: The breadcrumb message
    static func logBreadcrumb(_ message: String) {
        #if DEBUG
            print("🍞 Breadcrumb: \(message)")
        #else
            Crashlytics.crashlytics().log(message)
        #endif
    }
}
