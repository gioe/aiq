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
        lastName: String
    ) async throws -> AuthResponse {
        let request = RegisterRequest(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName
        )

        let response: AuthResponse = try await apiClient.request(
            endpoint: .register,
            method: .post,
            body: request,
            requiresAuth: false
        )

        // Save tokens and user
        try saveAuthData(response)

        return response
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        let request = LoginRequest(email: email, password: password)

        let response: AuthResponse = try await apiClient.request(
            endpoint: .login,
            method: .post,
            body: request,
            requiresAuth: false
        )

        // Save tokens and user
        try saveAuthData(response)

        return response
    }

    func refreshToken() async throws -> AuthResponse {
        guard let refreshToken = try secureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        ) else {
            throw AuthError.noRefreshToken
        }

        let request = RefreshTokenRequest(refreshToken: refreshToken)

        let response: AuthResponse = try await apiClient.request(
            endpoint: .refreshToken,
            method: .post,
            body: request,
            requiresAuth: false
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
            requiresAuth: true
        ) as String

        // Clear local data
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
            response.user.id,
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
            "No refresh token available"
        case .invalidCredentials:
            "Invalid email or password"
        case .sessionExpired:
            "Your session has expired. Please log in again."
        }
    }
}
