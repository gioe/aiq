import Foundation
import os

/// Authentication service implementation
class AuthService: AuthServiceProtocol {
    /// Shared singleton instance
    ///
    /// - Warning: Deprecated. Instances are now created and owned by ServiceContainer.
    ///   This property remains only for backward compatibility with tests.
    @available(*, deprecated, message: "AuthService instances are now created by ServiceContainer")
    static let shared = AuthService()

    private let apiClient: APIClientProtocol
    private let secureStorage: SecureStorageProtocol
    private var _currentUser: User?
    private let logger = Logger(subsystem: "com.aiq.app", category: "AuthService")

    var isAuthenticated: Bool {
        getAccessToken() != nil
    }

    var currentUser: User? {
        _currentUser
    }

    init(
        apiClient: APIClientProtocol = APIClient.shared,
        secureStorage: SecureStorageProtocol = KeychainStorage.shared
    ) {
        self.apiClient = apiClient
        self.secureStorage = secureStorage

        // Try to load existing token and set on API client
        do {
            if let token = try secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue) {
                apiClient.setAuthToken(token)
            }
        } catch {
            // Log storage error but don't crash - this is graceful degradation
            logger.error("Failed to retrieve access token during init: \(error.localizedDescription, privacy: .public)")
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .storageRetrieve,
                additionalInfo: ["key": SecureStorageKey.accessToken.rawValue, "operation": "init"]
            )
            #if DEBUG
                print("⚠️ [AuthService] Storage error during init: \(error)")
            #endif
        }
    }

    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear: Int? = nil,
        educationLevel: EducationLevel? = nil,
        country: String? = nil,
        region: String? = nil
    ) async throws -> AuthResponse {
        #if DEBUG
            print("🔐 Starting registration")
            print("   - Email: \(email)")
            print("   - First name: \(firstName), Last name: \(lastName)")
            print("   - Birth year: \(birthYear?.description ?? "nil")")
            print("   - Education level: \(educationLevel?.rawValue ?? "nil")")
        #endif

        let request = RegisterRequest(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName,
            birthYear: birthYear,
            educationLevel: educationLevel,
            country: country,
            region: region
        )

        do {
            let response: AuthResponse = try await apiClient.request(
                endpoint: .register,
                method: .post,
                body: request,
                requiresAuth: false,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )

            #if DEBUG
                print("✅ Registration successful")
                print("   - Access token length: \(response.accessToken.count)")
                print("   - User ID: \(response.user.id)")
                print("   - User email: \(response.user.email)")
            #endif

            // Save tokens and user
            try saveAuthData(response)

            return response
        } catch {
            #if DEBUG
                print("❌ Registration failed with error: \(error)")
            #endif
            throw error
        }
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        #if DEBUG
            print("🔐 Starting login")
            print("   - Email: \(email)")
        #endif
        let request = LoginRequest(email: email, password: password)

        do {
            let response: AuthResponse = try await apiClient.request(
                endpoint: .login,
                method: .post,
                body: request,
                requiresAuth: false,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )

            let tokenPrefix = response.accessToken.prefix(10)
            logger.notice("✅ Login API successful - token: \(tokenPrefix)..., user: \(response.user.email)")

            // Save tokens and user
            do {
                try saveAuthData(response)
                logger.notice("✅ Auth data saved to keychain")
            } catch {
                logger.error("❌ Failed to save auth data: \(error.localizedDescription, privacy: .public)")
                throw error
            }

            return response
        } catch {
            logger.error("❌ Login failed: \(error.localizedDescription, privacy: .public)")
            throw error
        }
    }

    func refreshToken() async throws -> AuthResponse {
        guard let refreshToken = try secureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        ) else {
            throw AuthError.noRefreshToken
        }

        // Send refresh token in Authorization header, not body
        let response: AuthResponse = try await apiClient.request(
            endpoint: .refreshToken,
            method: .post,
            body: String?.none,
            requiresAuth: false,
            customHeaders: ["Authorization": "Bearer \(refreshToken)"],
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )

        // Save new tokens
        try saveAuthData(response)

        return response
    }

    func logout() async throws {
        // Call logout endpoint (best effort - don't fail if it errors)
        try? await apiClient.request(
            endpoint: .logout,
            method: .post,
            body: String?.none,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        ) as String

        // Clear local data
        clearAuthData()
    }

    func deleteAccount() async throws {
        #if DEBUG
            print("🗑️ Starting account deletion")
        #endif

        // Call delete account endpoint - propagate errors to caller
        // This is critical: user must know if deletion failed to avoid GDPR issues
        //
        // Backend behavior: Returns 204 No Content on success (empty body)
        // This causes a decodingError when the APIClient tries to decode the response.
        // We treat decodingError as success since it indicates 2xx with empty body.
        // Any other error (network, 4xx, 5xx) is a real failure.
        do {
            let _: String? = try await apiClient.request(
                endpoint: .deleteAccount,
                method: .delete,
                body: String?.none,
                requiresAuth: true,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )
            // If we somehow got a response body, that's also success
            onDeleteSuccess()
        } catch let error as APIError {
            switch error {
            case .decodingError:
                // Expected path: 204 No Content causes decoding error with empty body
                onDeleteSuccess()
            default:
                // Real API failures (network, server errors, etc.)
                #if DEBUG
                    print("❌ Account deletion failed: \(error)")
                #endif
                throw AuthError.accountDeletionFailed(underlying: error)
            }
        } catch {
            // Non-API errors (shouldn't happen, but handle defensively)
            #if DEBUG
                print("❌ Account deletion failed: \(error)")
            #endif
            throw AuthError.accountDeletionFailed(underlying: error)
        }
    }

    private func onDeleteSuccess() {
        #if DEBUG
            print("✅ Account deletion successful")
        #endif
        clearAuthData()
    }

    func getAccessToken() -> String? {
        do {
            return try secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
        } catch {
            // Log storage error but return nil for graceful degradation
            logger.error("Failed to retrieve access token: \(error.localizedDescription, privacy: .public)")
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .storageRetrieve,
                additionalInfo: ["key": SecureStorageKey.accessToken.rawValue, "operation": "getAccessToken"]
            )
            #if DEBUG
                print("⚠️ [AuthService] Storage error in getAccessToken: \(error)")
            #endif
            return nil
        }
    }

    // MARK: - Private Methods

    private func saveAuthData(_ response: AuthResponse) throws {
        // Step 1: Capture current state before making changes
        let oldAccessToken = try? secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
        let oldRefreshToken = try? secureStorage.retrieve(forKey: SecureStorageKey.refreshToken.rawValue)
        let oldUserId = try? secureStorage.retrieve(forKey: SecureStorageKey.userId.rawValue)

        do {
            // Step 2: Attempt all saves
            try secureStorage.save(
                response.accessToken,
                forKey: SecureStorageKey.accessToken.rawValue
            )
            try secureStorage.save(
                response.refreshToken,
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            try secureStorage.save(
                String(describing: response.user.id),
                forKey: SecureStorageKey.userId.rawValue
            )

            // Step 3: Only update API client and in-memory state after successful saves
            apiClient.setAuthToken(response.accessToken)
            _currentUser = response.user
        } catch {
            // Step 4: Rollback on any failure
            do {
                try restoreAuthState(
                    accessToken: oldAccessToken,
                    refreshToken: oldRefreshToken,
                    userId: oldUserId
                )
            } catch let rollbackError {
                #if DEBUG
                    print("⚠️ Auth rollback failed: \(rollbackError)")
                #endif
                // Note: We still throw the original error below.
                // Rollback failure is logged but doesn't change error propagation.
            }
            throw error
        }
    }

    /// Restores authentication state to previous values
    /// - Parameters:
    ///   - accessToken: Previous access token (nil if none existed)
    ///   - refreshToken: Previous refresh token (nil if none existed)
    ///   - userId: Previous user ID (nil if none existed)
    /// - Throws: SecureStorageError if restoration fails
    /// - Note: If this method throws during rollback, auth state may be inconsistent.
    ///         The caller logs the failure but propagates the original error.
    private func restoreAuthState(
        accessToken: String?,
        refreshToken: String?,
        userId: String?
    ) throws {
        // Restore or delete each key based on previous state
        if let accessToken {
            try secureStorage.save(accessToken, forKey: SecureStorageKey.accessToken.rawValue)
        } else {
            try secureStorage.delete(forKey: SecureStorageKey.accessToken.rawValue)
        }

        if let refreshToken {
            try secureStorage.save(refreshToken, forKey: SecureStorageKey.refreshToken.rawValue)
        } else {
            try secureStorage.delete(forKey: SecureStorageKey.refreshToken.rawValue)
        }

        if let userId {
            try secureStorage.save(userId, forKey: SecureStorageKey.userId.rawValue)
        } else {
            try secureStorage.delete(forKey: SecureStorageKey.userId.rawValue)
        }
    }

    private func clearAuthData() {
        // Remove tokens from keychain
        do {
            try secureStorage.deleteAll()
            #if DEBUG
                print("✅ [AuthService] Successfully cleared secure storage")
            #endif
        } catch {
            // Log storage error but continue clearing other state
            // This is critical - if deletion fails, tokens remain in storage!
            logger.error("Failed to clear secure storage: \(error.localizedDescription, privacy: .public)")
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .storageDelete,
                additionalInfo: ["operation": "clearAuthData", "severity": "critical"]
            )
            #if DEBUG
                print("❌ [AuthService] Storage error during clearAuthData: \(error)")
                print("   WARNING: Tokens may still exist in secure storage!")
            #endif
        }

        // Clear API client token
        apiClient.setAuthToken(nil)

        // Clear current user
        _currentUser = nil
    }
}

/// Authentication-specific errors
enum AuthError: Error, LocalizedError {
    case noRefreshToken
    case invalidCredentials
    case sessionExpired
    case accountDeletionFailed(underlying: Error)

    var errorDescription: String? {
        switch self {
        case .noRefreshToken:
            NSLocalizedString("error.auth.no.refresh.token", comment: "")
        case .invalidCredentials:
            NSLocalizedString("error.auth.invalid.credentials", comment: "")
        case .sessionExpired:
            NSLocalizedString("error.auth.session.expired", comment: "")
        case .accountDeletionFailed:
            NSLocalizedString("error.auth.account.deletion.failed", comment: "")
        }
    }
}
