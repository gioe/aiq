import Foundation

/// Operation context for better error messages
enum NetworkOperation {
    case login
    case register
    case fetchQuestions
    case submitTest
    case refreshToken
    case fetchProfile
    case updateProfile
    case logout
    case generic

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
        case .logout:
            "signing out"
        case .generic:
            "completing request"
        }
    }
}

enum APIError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized(message: String? = nil)
    case forbidden(message: String? = nil)
    case notFound(message: String? = nil)
    case serverError(statusCode: Int, message: String? = nil)
    case decodingError(Error)
    case networkError(Error)
    case timeout
    case noInternetConnection
    case unknown(message: String? = nil)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            "Invalid URL"
        case .invalidResponse:
            "Invalid response from server"
        case let .unauthorized(message):
            message ?? "Your session has expired. Please log in again."
        case let .forbidden(message):
            message ?? "You don't have permission to access this resource"
        case let .notFound(message):
            message ?? "The requested resource was not found"
        case let .serverError(statusCode, message):
            if let message {
                "Server error: \(message)"
            } else {
                "Server error (code: \(statusCode))"
            }
        case let .decodingError(error):
            "Failed to process server response: \(error.localizedDescription)"
        case let .networkError(error):
            if let urlError = error as? URLError {
                switch urlError.code {
                case .notConnectedToInternet, .networkConnectionLost:
                    "No internet connection. Please check your network settings."
                case .timedOut:
                    "The request timed out. Please try again."
                case .cannotFindHost, .cannotConnectToHost:
                    "Unable to connect to server. Please try again later."
                default:
                    "Network error: \(error.localizedDescription)"
                }
            } else {
                "Network error: \(error.localizedDescription)"
            }
        case .timeout:
            "The request timed out. Please check your connection and try again."
        case .noInternetConnection:
            "No internet connection. Please check your network settings and try again."
        case let .unknown(message):
            message ?? "An unknown error occurred. Please try again."
        }
    }

    var isRetryable: Bool {
        switch self {
        case .networkError, .timeout, .noInternetConnection, .serverError:
            true
        case .unauthorized, .forbidden, .invalidURL, .invalidResponse, .notFound, .decodingError, .unknown:
            false
        }
    }
}

/// Wrapper for API errors with operation context
struct ContextualError: Error, LocalizedError {
    let error: APIError
    let operation: NetworkOperation

    var errorDescription: String? {
        guard let baseError = error.errorDescription else {
            return "An error occurred while \(operation.userFacingName)"
        }
        return "Error while \(operation.userFacingName): \(baseError)"
    }

    var underlyingError: APIError {
        error
    }

    var isRetryable: Bool {
        error.isRetryable
    }
}

struct ErrorResponse: Codable {
    let detail: String
}
