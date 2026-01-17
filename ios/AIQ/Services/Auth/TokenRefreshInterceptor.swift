import Foundation

/// Error type for token refresh operations
enum TokenRefreshError: Error {
    /// Indicates the original request should be retried with the new token
    case shouldRetryRequest
    /// Token refresh failed with an underlying error
    case refreshFailed(Error)
}

/// Response interceptor that automatically refreshes tokens on 401 errors
///
/// Thread-Safety: This actor ensures safe concurrent access to token refresh state.
/// Multiple concurrent 401 responses will share a single refresh task, preventing
/// duplicate refresh requests.
actor TokenRefreshInterceptor: ResponseInterceptor {
    var authService: AuthServiceProtocol?
    var isRefreshing = false
    var refreshTask: Task<AuthResponse, Error>?

    init(authService: AuthServiceProtocol? = nil) {
        self.authService = authService
    }

    /// Set the authentication service for token refresh operations
    /// - Parameter authService: The authentication service to use for refreshing tokens
    func setAuthService(_ authService: AuthServiceProtocol) {
        self.authService = authService
    }

    /// Intercept HTTP responses and handle 401 unauthorized errors by refreshing the token
    /// - Parameters:
    ///   - response: The HTTP response to intercept
    ///   - data: The response data
    /// - Returns: The response data, or throws an error if token refresh is needed
    /// - Throws: `TokenRefreshError.shouldRetryRequest` to signal the request should be retried
    func intercept(response: HTTPURLResponse, data: Data) async throws -> Data {
        // Only intercept 401 errors
        guard response.statusCode == 401 else {
            return data
        }

        // Refresh the token
        try await refreshToken()

        // Signal that the request should be retried
        throw TokenRefreshError.shouldRetryRequest
    }

    /// Handle 401 unauthorized responses by refreshing the token
    private func refreshToken() async throws {
        guard let authService else {
            throw APIError.unauthorized(message: NSLocalizedString("error.auth.service.not.available", comment: ""))
        }

        // If already refreshing, wait for that task
        if let existingTask = refreshTask {
            _ = try await existingTask.value
            return
        }

        // Start new refresh task
        isRefreshing = true
        let task = Task<AuthResponse, Error> {
            do {
                let response = try await authService.refreshToken()
                return response
            } catch {
                // Token refresh failed - log to Crashlytics for debugging
                CrashlyticsErrorRecorder.recordError(
                    error,
                    context: .tokenRefresh,
                    additionalInfo: [
                        "event": "silent_logout",
                        "reason": "token_refresh_failed"
                    ]
                )
                CrashlyticsErrorRecorder.logBreadcrumb(
                    "Silent logout triggered: token refresh failed"
                )

                // Clear auth state (silent logout)
                try? await authService.logout()
                throw TokenRefreshError.refreshFailed(error)
            }
        }

        refreshTask = task

        defer {
            refreshTask = nil
            isRefreshing = false
        }

        _ = try await task.value
    }
}
