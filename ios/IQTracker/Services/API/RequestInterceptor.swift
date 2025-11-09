import Foundation

/// Protocol for intercepting and modifying requests before they're sent
protocol RequestInterceptor {
    /// Intercept and potentially modify a request before it's sent
    func intercept(_ request: URLRequest) async throws -> URLRequest
}

/// Protocol for intercepting and handling responses
protocol ResponseInterceptor {
    /// Intercept and potentially handle a response
    func intercept(response: HTTPURLResponse, data: Data) async throws -> Data
}

/// Logging interceptor that logs all requests
struct LoggingInterceptor: RequestInterceptor {
    func intercept(_ request: URLRequest) async throws -> URLRequest {
        NetworkLogger.shared.logRequest(request)
        return request
    }
}

/// Auth token interceptor that adds authentication headers
struct AuthTokenInterceptor: RequestInterceptor {
    private let tokenProvider: () -> String?

    init(tokenProvider: @escaping () -> String?) {
        self.tokenProvider = tokenProvider
    }

    func intercept(_ request: URLRequest) async throws -> URLRequest {
        var modifiedRequest = request

        if let token = tokenProvider() {
            modifiedRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        return modifiedRequest
    }
}

/// Network connectivity interceptor that checks for internet connection
struct ConnectivityInterceptor: RequestInterceptor {
    func intercept(_ request: URLRequest) async throws -> URLRequest {
        guard NetworkMonitor.shared.isConnected else {
            throw APIError.noInternetConnection
        }
        return request
    }
}
