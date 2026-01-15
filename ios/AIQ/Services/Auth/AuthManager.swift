import Combine
import Foundation

/// Manages authentication state for the entire app
@MainActor
class AuthManager: ObservableObject, AuthManagerProtocol {
    /// Shared singleton instance
    ///
    /// - Warning: Deprecated. Use `ServiceContainer.shared.resolve(AuthManagerProtocol.self)` instead.
    ///   ServiceContainer now owns the singleton instances directly, making this property redundant.
    @available(*, deprecated, message: "Use ServiceContainer.shared.resolve(AuthManagerProtocol.self) instead")
    static let shared = AuthManager()

    @Published private(set) var isAuthenticated: Bool = false
    @Published private(set) var currentUser: User?
    @Published private(set) var isLoading: Bool = false
    @Published private(set) var authError: Error?

    var isAuthenticatedPublisher: Published<Bool>.Publisher { $isAuthenticated }
    var isLoadingPublisher: Published<Bool>.Publisher { $isLoading }
    var authErrorPublisher: Published<Error?>.Publisher { $authError }

    private let authService: AuthServiceProtocol
    private let tokenRefreshInterceptor: TokenRefreshInterceptor

    /// Factory closure for creating DeviceTokenManager - using lazy initialization
    /// to break circular dependency with NotificationManager
    private let deviceTokenManagerFactory: () -> DeviceTokenManagerProtocol
    private lazy var deviceTokenManager: DeviceTokenManagerProtocol = deviceTokenManagerFactory()

    init(
        authService: AuthServiceProtocol = AuthService.shared,
        deviceTokenManagerFactory: @escaping @MainActor () -> DeviceTokenManagerProtocol = {
            NotificationManager.shared
        }
    ) {
        self.authService = authService
        self.deviceTokenManagerFactory = deviceTokenManagerFactory
        tokenRefreshInterceptor = TokenRefreshInterceptor(authService: authService)

        // Set up token refresh interceptor in APIClient
        if authService is AuthService {
            // Access the shared APIClient and set the auth service
            // Note: This must be done asynchronously due to actor isolation
            Task {
                await APIClient.shared.setAuthService(authService)
            }
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
        lastName: String,
        birthYear: Int? = nil,
        educationLevel: EducationLevel? = nil,
        country: String? = nil,
        region: String? = nil
    ) async throws {
        isLoading = true
        authError = nil

        do {
            let response = try await authService.register(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName,
                birthYear: birthYear,
                educationLevel: educationLevel,
                country: country,
                region: region
            )

            isAuthenticated = true
            currentUser = response.user
            isLoading = false

            // Track analytics
            AnalyticsService.shared.trackUserRegistered(email: email)
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

            // Track analytics
            AnalyticsService.shared.trackUserLogin(email: email)
        } catch {
            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .login
            )
            authError = contextualError
            isLoading = false

            // Track failed authentication
            AnalyticsService.shared.trackAuthFailed(reason: error.localizedDescription)
            throw contextualError
        }
    }

    func logout() async {
        isLoading = true

        // Unregister device token first
        await deviceTokenManager.unregisterDeviceToken()

        do {
            try await authService.logout()
        } catch {
            // Log error but don't fail logout - silently continue
            #if DEBUG
                print("⚠️ Logout error: \(error.localizedDescription)")
            #endif
        }

        isAuthenticated = false
        currentUser = nil
        isLoading = false
        authError = nil

        // Track analytics
        AnalyticsService.shared.trackUserLogout()
    }

    func deleteAccount() async throws {
        guard !isLoading else {
            throw APIError.badRequest(message: NSLocalizedString("error.auth.operation.in.progress", comment: ""))
        }

        isLoading = true
        authError = nil

        do {
            // Unregister device token first
            await deviceTokenManager.unregisterDeviceToken()

            // Call the delete account endpoint
            try await authService.deleteAccount()

            // Clear authentication state
            isAuthenticated = false
            currentUser = nil
            isLoading = false
            authError = nil

            // Track analytics
            AnalyticsService.shared.track(event: .accountDeleted)

            // Clear all cached data
            await DataCache.shared.clearAll()
        } catch {
            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .deleteAccount
            )
            authError = contextualError
            isLoading = false
            throw contextualError
        }
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
