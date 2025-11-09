import Combine
import Foundation

/// Manages authentication state for the entire app
@MainActor
class AuthManager: ObservableObject, AuthManagerProtocol {
    static let shared = AuthManager()

    @Published private(set) var isAuthenticated: Bool = false
    @Published private(set) var currentUser: User?
    @Published private(set) var isLoading: Bool = false
    @Published private(set) var authError: Error?

    var isLoadingPublisher: Published<Bool>.Publisher { $isLoading }
    var authErrorPublisher: Published<Error?>.Publisher { $authError }

    private let authService: AuthServiceProtocol
    private let tokenRefreshInterceptor: TokenRefreshInterceptor

    init(authService: AuthServiceProtocol = AuthService.shared) {
        self.authService = authService
        tokenRefreshInterceptor = TokenRefreshInterceptor(authService: authService)

        // Set up token refresh interceptor in APIClient
        if let apiClient = authService as? AuthService {
            // Access the shared APIClient and set the auth service
            APIClient.shared.setAuthService(authService)
        }

        // Initialize state from existing session
        isAuthenticated = authService.isAuthenticated
        currentUser = authService.currentUser
    }

    // MARK: - Public Methods

    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String
    ) async throws {
        isLoading = true
        authError = nil

        do {
            let response = try await authService.register(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName
            )

            isAuthenticated = true
            currentUser = response.user
            isLoading = false
        } catch {
            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .register
            )
            authError = contextualError
            isLoading = false
            throw contextualError
        }
    }

    func login(email: String, password: String) async throws {
        isLoading = true
        authError = nil

        do {
            let response = try await authService.login(email: email, password: password)

            isAuthenticated = true
            currentUser = response.user
            isLoading = false
        } catch {
            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .login
            )
            authError = contextualError
            isLoading = false
            throw contextualError
        }
    }

    func logout() async {
        isLoading = true

        do {
            try await authService.logout()
        } catch {
            // Log error but don't fail logout
            print("⚠️ Logout error: \(error.localizedDescription)")
        }

        isAuthenticated = false
        currentUser = nil
        isLoading = false
        authError = nil
    }

    func refreshToken() async throws {
        do {
            let response = try await authService.refreshToken()
            currentUser = response.user
        } catch {
            // Token refresh failed - logout user
            await logout()
            throw error
        }
    }

    func clearError() {
        authError = nil
    }

    // MARK: - Session Management

    /// Check if the current session is valid
    func validateSession() async {
        guard isAuthenticated else { return }

        do {
            // Try to refresh token to validate session
            try await refreshToken()
        } catch {
            // Session invalid - logout
            await logout()
        }
    }

    /// Restore session from stored credentials
    func restoreSession() async {
        guard authService.isAuthenticated else {
            isAuthenticated = false
            return
        }

        // Validate the stored session
        await validateSession()
    }
}

// MARK: - Convenience Extensions

extension AuthManager {
    /// Check if a user is logged in and has a valid session
    var hasValidSession: Bool {
        isAuthenticated && currentUser != nil
    }

    /// Get the user's full name
    var userFullName: String? {
        currentUser?.fullName
    }

    /// Get the user's email
    var userEmail: String? {
        currentUser?.email
    }
}
