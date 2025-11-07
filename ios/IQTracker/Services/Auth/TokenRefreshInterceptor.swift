import Foundation

/// Response interceptor that automatically refreshes tokens on 401 errors
class TokenRefreshInterceptor {
    private let authService: AuthServiceProtocol
    private var isRefreshing = false
    private var refreshTask: Task<AuthResponse, Error>?

    init(authService: AuthServiceProtocol = AuthService.shared) {
        self.authService = authService
    }

    /// Handle 401 unauthorized responses by refreshing the token
    func handleUnauthorized() async throws {
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
                throw error
            }
        }

        refreshTask = task

        defer {
            refreshTask = nil
            isRefreshing = false
        }

        _ = try await task.value
    }

    /// Check if we should attempt token refresh for an error
    func shouldRefreshToken(for error: Error) -> Bool {
        if let apiError = error as? APIError {
            switch apiError {
            case .unauthorized:
                return true
            default:
                return false
            }
        }
        return false
    }
}
