import Foundation

/// Authentication service implementation
class AuthService: AuthServiceProtocol {
    static let shared = AuthService()

    private let apiClient: APIClientProtocol
    private let secureStorage: SecureStorageProtocol
    private var _currentUser: User?

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
        if let token = try? secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue) {
            apiClient.setAuthToken(token)
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
        print("🔐 Starting registration")
        #if DEBUG
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

            print("✅ Registration successful")
            #if DEBUG
                print("   - Access token length: \(response.accessToken.count)")
                print("   - User ID: \(response.user.id)")
                print("   - User email: \(response.user.email)")
            #endif

            // Save tokens and user
            try saveAuthData(response)

            return response
        } catch {
            print("❌ Registration failed with error: \(error)")
            throw error
        }
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        print("🔐 Starting login")
        #if DEBUG
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

            print("✅ Login successful")
            #if DEBUG
                print("   - Access token length: \(response.accessToken.count)")
                print("   - User ID: \(response.user.id)")
                print("   - User email: \(response.user.email)")
            #endif

            // Save tokens and user
            try saveAuthData(response)

            return response
        } catch {
            print("❌ Login failed with error: \(error)")
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
        print("🗑️ Starting account deletion")

        // Call delete account endpoint
        let _: String? = try? await apiClient.request(
            endpoint: .deleteAccount,
            method: .delete,
            body: String?.none,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )

        print("✅ Account deletion request completed")

        // Clear local data regardless of response (account is deleted on server)
        clearAuthData()
    }

    func getAccessToken() -> String? {
        try? secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
    }

    // MARK: - Private Methods

    private func saveAuthData(_ response: AuthResponse) throws {
        // Save tokens to keychain
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

        // Update API client with new token
        apiClient.setAuthToken(response.accessToken)

        // Store current user
        _currentUser = response.user
    }

    private func clearAuthData() {
        // Remove tokens from keychain
        try? secureStorage.deleteAll()

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

    var errorDescription: String? {
        switch self {
        case .noRefreshToken:
            NSLocalizedString("error.auth.no.refresh.token", comment: "")
        case .invalidCredentials:
            NSLocalizedString("error.auth.invalid.credentials", comment: "")
        case .sessionExpired:
            NSLocalizedString("error.auth.session.expired", comment: "")
        }
    }
}
