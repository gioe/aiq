import Combine
import Foundation
import os

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
    private let logger = Logger(subsystem: "com.aiq.app", category: "AuthManager")
    private let signposter = OSSignposter(subsystem: "com.aiq.app", category: "Auth")

    /// Factory closure for creating DeviceTokenManager - using lazy initialization
    /// to break circular dependency with NotificationManager
    private let deviceTokenManagerFactory: () -> DeviceTokenManagerProtocol
    private lazy var deviceTokenManager: DeviceTokenManagerProtocol = deviceTokenManagerFactory()

    init(
        authService: AuthServiceProtocol = ServiceContainer.shared.resolve(AuthServiceProtocol.self)!,
        deviceTokenManagerFactory: @escaping @MainActor () -> DeviceTokenManagerProtocol = {
            guard let manager = ServiceContainer.shared.resolve(NotificationManagerProtocol.self),
                  let tokenManager = manager as? DeviceTokenManagerProtocol else {
                fatalError("NotificationManagerProtocol not registered in ServiceContainer")
            }
            return tokenManager
        }
    ) {
        self.authService = authService
        self.deviceTokenManagerFactory = deviceTokenManagerFactory

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

        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval("Auth.Register", id: signpostID)
        let startTime = CFAbsoluteTimeGetCurrent()

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

            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.Register", state)
            logger.info("Registration completed in \(elapsed, format: .fixed(precision: 2))s")

            isAuthenticated = true
            currentUser = response.user
            isLoading = false

            // Track analytics
            AnalyticsService.shared.trackUserRegistered(email: email)
        } catch {
            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.Register", state)
            let errorDesc = error.localizedDescription
            logger.warning(
                "Registration failed after \(elapsed, format: .fixed(precision: 2))s: \(errorDesc, privacy: .public)"
            )

            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(message: error.localizedDescription),
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

        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval("Auth.Login", id: signpostID)
        let startTime = CFAbsoluteTimeGetCurrent()

        do {
            let response = try await authService.login(email: email, password: password)

            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.Login", state)
            logger.info("Login completed in \(elapsed, format: .fixed(precision: 2))s")

            isAuthenticated = true
            currentUser = response.user
            isLoading = false

            // Track analytics
            AnalyticsService.shared.trackUserLogin(email: email)
        } catch {
            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.Login", state)
            let errorDesc = error.localizedDescription
            logger.warning(
                "Login failed after \(elapsed, format: .fixed(precision: 2))s: \(errorDesc, privacy: .public)"
            )

            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(message: error.localizedDescription),
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

        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval("Auth.Logout", id: signpostID)
        let startTime = CFAbsoluteTimeGetCurrent()

        // Unregister device token first
        await deviceTokenManager.unregisterDeviceToken()

        var logoutFailed = false
        do {
            try await authService.logout()
        } catch {
            logoutFailed = true
            let errorDesc = error.localizedDescription
            logger.warning("Logout request failed: \(errorDesc, privacy: .public)")
        }

        let elapsed = CFAbsoluteTimeGetCurrent() - startTime
        signposter.endInterval("Auth.Logout", state)
        if logoutFailed {
            logger.info("Logout completed locally in \(elapsed, format: .fixed(precision: 2))s (API call failed)")
        } else {
            logger.info("Logout completed in \(elapsed, format: .fixed(precision: 2))s")
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

        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval("Auth.DeleteAccount", id: signpostID)
        let startTime = CFAbsoluteTimeGetCurrent()

        do {
            // Unregister device token first
            await deviceTokenManager.unregisterDeviceToken()

            // Call the delete account endpoint
            try await authService.deleteAccount()

            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.DeleteAccount", state)
            logger.info("Account deletion completed in \(elapsed, format: .fixed(precision: 2))s")

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
            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.DeleteAccount", state)
            let errorDesc = error.localizedDescription
            logger.warning(
                "Delete account failed after \(elapsed, format: .fixed(precision: 2))s: \(errorDesc, privacy: .public)"
            )

            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(message: error.localizedDescription),
                operation: .deleteAccount
            )
            authError = contextualError
            isLoading = false
            throw contextualError
        }
    }

    func refreshToken() async throws {
        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval("Auth.TokenRefresh", id: signpostID)
        let startTime = CFAbsoluteTimeGetCurrent()

        do {
            let response = try await authService.refreshToken()

            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.TokenRefresh", state)
            logger.info("Token refresh completed in \(elapsed, format: .fixed(precision: 2))s")

            currentUser = response.user
        } catch {
            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            signposter.endInterval("Auth.TokenRefresh", state)
            let errorDesc = error.localizedDescription
            logger.warning(
                "Token refresh failed after \(elapsed, format: .fixed(precision: 2))s: \(errorDesc, privacy: .public)"
            )

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
