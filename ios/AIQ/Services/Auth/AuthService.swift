import AIQAPIClient
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

    private let apiService: OpenAPIServiceProtocol
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
        apiService: OpenAPIServiceProtocol = ServiceContainer.shared.resolve(OpenAPIServiceProtocol.self)!,
        secureStorage: SecureStorageProtocol = KeychainStorage.shared
    ) {
        self.apiService = apiService
        self.secureStorage = secureStorage

        // Restore tokens from keychain into middleware on init
        do {
            if let accessToken = try secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue),
               let refreshToken = try secureStorage.retrieve(forKey: SecureStorageKey.refreshToken.rawValue) {
                Task {
                    await apiService.setTokens(accessToken: accessToken, refreshToken: refreshToken)
                }
            }
        } catch {
            // Log storage error but don't crash - this is graceful degradation
            logger.error("Failed to retrieve tokens during init: \(error.localizedDescription, privacy: .public)")
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .storageRetrieve,
                additionalInfo: ["key": SecureStorageKey.accessToken.rawValue, "operation": "init"]
            )
            #if DEBUG
                print("[WARN] [AuthService] Storage error during init: \(error)")
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
            print("[AUTH] Starting registration")
            print("   - Email: \(email)")
            print("   - First name: \(firstName), Last name: \(lastName)")
            print("   - Birth year: \(birthYear?.description ?? "nil")")
            print("   - Education level: \(educationLevel?.rawValue ?? "nil")")
        #endif

        do {
            let response = try await apiService.register(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName,
                birthYear: birthYear,
                educationLevel: educationLevel,
                country: country,
                region: region
            )

            #if DEBUG
                print("[SUCCESS] Registration successful")
                print("   - Access token length: \(response.accessToken.count)")
                print("   - User ID: \(response.user.id)")
                print("   - User email: \(response.user.email)")
            #endif

            // Save tokens and user
            try await saveAuthData(response)

            return response
        } catch {
            #if DEBUG
                print("[ERROR] Registration failed with error: \(error)")
            #endif
            throw error
        }
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        #if DEBUG
            print("[AUTH] Starting login")
            print("   - Email: \(email)")
        #endif

        do {
            let response = try await apiService.login(email: email, password: password)

            #if DEBUG
                print("[SUCCESS] Login successful")
                print("   - Access token length: \(response.accessToken.count)")
                print("   - User ID: \(response.user.id)")
                print("   - User email: \(response.user.email)")
            #endif

            // Save tokens and user
            try await saveAuthData(response)

            return response
        } catch {
            #if DEBUG
                print("[ERROR] Login failed with error: \(error)")
            #endif
            throw error
        }
    }

    func refreshToken() async throws -> AuthResponse {
        guard try secureStorage.retrieve(forKey: SecureStorageKey.refreshToken.rawValue) != nil else {
            throw AuthError.noRefreshToken
        }

        // The OpenAPI middleware handles sending the refresh token
        let response = try await apiService.refreshToken()

        // Save new tokens
        try await saveAuthData(response)

        return response
    }

    func logout() async throws {
        // Call logout endpoint (best effort - don't fail if it errors)
        try? await apiService.logout()

        // Clear local data
        await clearAuthData()
    }

    func deleteAccount() async throws {
        #if DEBUG
            print("[AUTH] Starting account deletion")
        #endif

        do {
            try await apiService.deleteAccount()

            #if DEBUG
                print("[SUCCESS] Account deletion successful")
            #endif
            await clearAuthData()
        } catch {
            #if DEBUG
                print("[ERROR] Account deletion failed: \(error)")
            #endif
            throw AuthError.accountDeletionFailed(underlying: error)
        }
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
                print("[WARN] [AuthService] Storage error in getAccessToken: \(error)")
            #endif
            return nil
        }
    }

    // MARK: - Private Methods

    private func saveAuthData(_ response: AuthResponse) async throws {
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

            // Step 3: Only update middleware tokens and in-memory state after successful saves
            await apiService.setTokens(
                accessToken: response.accessToken,
                refreshToken: response.refreshToken
            )
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
                    print("[WARN] Auth rollback failed: \(rollbackError)")
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

    private func clearAuthData() async {
        // Remove tokens from keychain
        do {
            try secureStorage.deleteAll()
            #if DEBUG
                print("[SUCCESS] [AuthService] Successfully cleared secure storage")
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
                print("[ERROR] [AuthService] Storage error during clearAuthData: \(error)")
                print("   WARNING: Tokens may still exist in secure storage!")
            #endif
        }

        // Clear middleware tokens
        await apiService.clearTokens()

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
