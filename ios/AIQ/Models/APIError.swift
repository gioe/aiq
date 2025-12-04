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
        case .generic:
            "completing request"
        }
    }
}

enum APIError: Error, LocalizedError {
    /// The URL is invalid or malformed
    case invalidURL
    /// The server response is invalid or unexpected
    case invalidResponse
    /// Authentication failed or token expired
    case unauthorized(message: String? = nil)
    /// Access to the resource is forbidden
    case forbidden(message: String? = nil)
    /// The requested resource was not found
    case notFound(message: String? = nil)
    /// Bad request - client error
    case badRequest(message: String? = nil)
    /// User already has an active test session
    case activeSessionConflict(sessionId: Int, message: String)
    /// Server error occurred
    case serverError(statusCode: Int, message: String? = nil)
    /// Failed to decode the server response
    case decodingError(Error)
    /// Network connectivity error
    case networkError(Error)
    /// Request timed out
    case timeout
    /// No internet connection available
    case noInternetConnection
    /// Unknown error occurred
    case unknown(message: String? = nil)
    /// Unprocessable entity
    case unprocessableEntity(message: String? = nil)

    /// User-friendly error description with clear guidance
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            "There was a problem with the request. Please try again or contact support if the issue persists."
        case .invalidResponse:
            "We received an unexpected response from the server. Please try again."
        case let .unauthorized(message):
            message ?? "Your session has expired. Please log in again to continue."
        case let .forbidden(message):
            message ?? "Access denied. You don't have permission to perform this action."
        case let .notFound(message):
            message ?? "We couldn't find what you're looking for. It may have been removed or is no longer available."
        case let .unprocessableEntity(message):
            message ?? "We couldn't process your request. Please check your information and try again."
        case let .badRequest(message):
            message ?? "There was a problem with your request. Please check your information and try again."
        case let .activeSessionConflict(_, message):
            message
        case let .serverError(statusCode, message):
            if let message {
                "Server error: \(message). Please try again in a few moments."
            } else {
                "Our servers are experiencing issues (code: \(statusCode)). Please try again in a few moments."
            }
        case let .decodingError(error):
            """
            We couldn't understand the server's response. Please try again or contact support if this continues. \
            Technical details: \(error.localizedDescription)
            """
        case let .networkError(error):
            if let urlError = error as? URLError {
                switch urlError.code {
                case .notConnectedToInternet, .networkConnectionLost:
                    "No internet connection detected. Please check your Wi-Fi or cellular data and try again."
                case .timedOut:
                    "The connection timed out. Please check your internet connection and try again."
                case .cannotFindHost, .cannotConnectToHost:
                    "Unable to reach the server. Please check your internet connection and try again later."
                default:
                    "A network error occurred. Please check your connection and try again."
                }
            } else {
                "A network error occurred. Please check your connection and try again."
            }
        case .timeout:
            "The request took too long to complete. Please check your internet connection and try again."
        case .noInternetConnection:
            "No internet connection detected. Please check your Wi-Fi or cellular data settings and try again."
        case let .unknown(message):
            message ?? "Something unexpected happened. Please try again or contact support if the issue continues."
        }
    }

    /// Whether this error is retryable (e.g., network errors, timeouts, server errors)
    var isRetryable: Bool {
        switch self {
        case .networkError, .timeout, .noInternetConnection, .serverError:
            true
        case .badRequest, .unprocessableEntity, .unauthorized, .forbidden,
             .invalidURL, .invalidResponse, .notFound,
             .activeSessionConflict, .decodingError, .unknown:
            false
        }
    }
}

/// Wrapper for API errors with operation context
struct ContextualError: Error, LocalizedError {
    /// The underlying API error
    let error: APIError
    /// The network operation that failed
    let operation: NetworkOperation

    var errorDescription: String? {
        // For some errors, just show the base error without repetitive context
        switch error {
        case .unauthorized, .noInternetConnection, .networkError, .timeout:
            // These errors already have clear messaging, no need to repeat operation
            return error.errorDescription
        default:
            // For other errors, add context about what we were trying to do
            guard let baseError = error.errorDescription else {
                return "An error occurred while \(operation.userFacingName). Please try again."
            }
            // Check if the base error already mentions the operation to avoid redundancy
            if baseError.lowercased().contains(operation.userFacingName.lowercased()) {
                return baseError
            }
            return baseError
        }
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

extension APIError {
    /// Parse a 400 error to detect active session conflicts
    /// - Parameter message: The error message from the server
    /// - Returns: An activeSessionConflict error if detected, otherwise a badRequest error
    static func parseBadRequest(message: String?) -> APIError {
        guard let message else {
            return .badRequest(message: nil)
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

        // Not an active session conflict - return generic bad request
        return .badRequest(message: message)
    }
}
