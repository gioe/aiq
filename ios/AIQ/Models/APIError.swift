import APIClient
import Foundation

/// Operation context for better error messages
enum NetworkOperation {
    /// User login operation
    case login
    /// User registration operation
    case register
    /// Fetching test questions
    case fetchQuestions
    /// Submitting test answers
    case submitTest
    /// Refreshing authentication token
    case refreshToken
    /// Fetching user profile
    case fetchProfile
    /// Updating user profile
    case updateProfile
    /// Fetching test history
    case fetchHistory
    /// User logout operation
    case logout
    /// User delete account operation
    case deleteAccount
    /// Submit user feedback
    case submitFeedback
    /// Generic network operation
    case generic

    /// User-friendly name for the operation
    var userFacingName: String {
        switch self {
        case .login:
            "signing in"
        case .register:
            "creating account"
        case .fetchQuestions:
            "loading questions"
        case .submitTest:
            "submitting test"
        case .refreshToken:
            "refreshing session"
        case .fetchProfile:
            "loading profile"
        case .updateProfile:
            "updating profile"
        case .fetchHistory:
            "loading history"
        case .logout:
            "signing out"
        case .deleteAccount:
            "deleting account"
        case .submitFeedback:
            "submitting feedback"
        case .generic:
            "completing request"
        }
    }
}

/// App-level API error that wraps ios-libs generic HTTP errors with domain-specific cases.
///
/// Generic HTTP/network error cases (unauthorized, notFound, timeout, etc.) are delegated
/// to `APIClient.APIError` from ios-libs. App-specific cases remain here.
enum AppError: Error, LocalizedError, Equatable {
    /// Generic HTTP/network error from ios-libs APIClient
    case api(APIClient.APIError)
    /// User already has an active test session
    case activeSessionConflict(sessionId: Int, message: String)
    /// User must wait before taking another test
    case testCooldown(nextEligibleDate: Date, daysRemaining: Int)

    /// User-friendly error description with clear guidance
    var errorDescription: String? {
        switch self {
        case let .api(apiError):
            apiError.errorDescription
        case let .activeSessionConflict(_, message):
            message
        case let .testCooldown(_, daysRemaining):
            "You must wait \(daysRemaining) more day\(daysRemaining == 1 ? "" : "s") before taking another test."
        }
    }

    /// Whether this error is retryable (e.g., network errors, timeouts, server errors)
    var isRetryable: Bool {
        switch self {
        case let .api(apiError):
            apiError.isRetryable
        case .activeSessionConflict, .testCooldown:
            false
        }
    }
}

/// Backward-compatible typealias — most code refers to `APIError`.
typealias APIError = AppError

/// Wrapper for API errors with operation context
struct ContextualError: Error, LocalizedError {
    /// The underlying API error
    let error: APIError
    /// The network operation that failed
    let operation: NetworkOperation

    var errorDescription: String? {
        // For some errors, just show the base error without repetitive context
        switch error {
        case let .api(apiError):
            switch apiError {
            case .unauthorized, .noInternetConnection, .networkError, .timeout:
                return error.errorDescription
            default:
                break
            }
        default:
            break
        }

        guard let baseError = error.errorDescription else {
            return "An error occurred while \(operation.userFacingName). Please try again."
        }
        if baseError.lowercased().contains(operation.userFacingName.lowercased()) {
            return baseError
        }
        return baseError
    }

    /// The underlying API error for detailed handling
    var underlyingError: APIError {
        error
    }

    /// Whether this error can be retried
    var isRetryable: Bool {
        error.isRetryable
    }
}

/// Server error response structure
struct ErrorResponse: Codable {
    /// Detailed error message from the server
    let detail: String
}

// MARK: - Active Session Error Parsing

extension AppError {
    /// Parse a 400 error to detect typed error cases (active session conflicts, test cooldown).
    /// - Parameter message: The error message from the server
    /// - Returns: A typed AppError case if detected, otherwise a badRequest error
    static func parseBadRequest(message: String?) -> AppError {
        guard let message else {
            return .api(.badRequest(message: nil))
        }

        // Check if this is an active session conflict
        // Expected format: "User already has an active test session (ID: 123). ..."
        if message.contains("already has an active test session") {
            // Extract session ID using regex
            let pattern = #"active test session \(ID: (\d+)\)"#
            if let regex = try? NSRegularExpression(pattern: pattern, options: []),
               let match = regex.firstMatch(
                   in: message,
                   options: [],
                   range: NSRange(message.startIndex..., in: message)
               ),
               let sessionIdRange = Range(match.range(at: 1), in: message),
               let sessionId = Int(message[sessionIdRange]) {
                return .activeSessionConflict(sessionId: sessionId, message: message)
            }
        }

        // Check if this is a test cooldown error
        // Expected format: "You must wait 90 days (3 months) between tests. ... You can take your
        //                   next test on YYYY-MM-DD ({days_remaining} days remaining)."
        if message.contains("must wait 90 days") {
            if let cooldownError = parseCooldownMessage(message) {
                return cooldownError
            }
        }

        // Not a typed error - return generic bad request
        return .api(.badRequest(message: message))
    }

    /// Extract next-eligible date and days-remaining from a cooldown message.
    /// Returns nil if either value cannot be parsed.
    private static func parseCooldownMessage(_ message: String) -> AppError? {
        let datePattern = #"You can take your next test on (\d{4}-\d{2}-\d{2})"#
        let daysPattern = #"\((\d+) days remaining\)"#

        guard
            let dateRegex = try? NSRegularExpression(pattern: datePattern),
            let daysRegex = try? NSRegularExpression(pattern: daysPattern),
            let dateMatch = dateRegex.firstMatch(
                in: message, range: NSRange(message.startIndex..., in: message)
            ),
            let daysMatch = daysRegex.firstMatch(
                in: message, range: NSRange(message.startIndex..., in: message)
            ),
            let dateRange = Range(dateMatch.range(at: 1), in: message),
            let daysRange = Range(daysMatch.range(at: 1), in: message),
            let daysRemaining = Int(message[daysRange])
        else {
            return nil
        }

        let dateString = String(message[dateRange])
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        guard let nextEligibleDate = formatter.date(from: dateString) else {
            return nil
        }

        return .testCooldown(nextEligibleDate: nextEligibleDate, daysRemaining: daysRemaining)
    }
}
