import Foundation

/// Error type for token refresh operations
enum TokenRefreshError: Error {
    case shouldRetryRequest
    case refreshFailed(Error)
}

/// Response interceptor that automatically refreshes tokens on 401 errors
class TokenRefreshInterceptor: ResponseInterceptor {
    private weak var authService: AuthServiceProtocol?
    private var isRefreshing = false
    private var refreshTask: Task<AuthResponse, Error>?

    init(authService: AuthServiceProtocol? = nil) {
        self.authService = authService
    }

    func setAuthService(_ authService: AuthServiceProtocol) {
        self.authService = authService
    }

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
            throw APIError.unauthorized(message: "Authentication service not available")
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
                // Token refresh failed - clear auth state
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
