@testable import AIQ
import Foundation

/// Mock AuthService for testing token refresh scenarios in TokenRefreshInterceptor
actor TokenRefreshMockAuthService: AuthServiceProtocol {
    // MARK: - Tracking Properties

    var refreshTokenCalled = false
    var refreshTokenCallCount = 0
    var logoutCalled = false
    var logoutCallCount = 0

    // MARK: - Configuration Properties

    private var mockRefreshResponse: AuthResponse?
    private var mockRefreshError: Error?
    private var _mockAccessToken: String?
    /// Thread-safe storage for access token, protected by lock for cross-isolation access
    private let accessTokenLock = NSLock()
    private nonisolated(unsafe) var _unsafeAccessToken: String?
    private var mockCurrentUser: User?
    private var shouldThrowOnRefresh = false
    private var refreshDelay: TimeInterval = 0

    // MARK: - Computed Properties (required by protocol)

    nonisolated var isAuthenticated: Bool {
        // For testing, we'll assume authenticated if token exists
        true
    }

    nonisolated var currentUser: User? {
        // Not used in TokenRefreshInterceptor tests
        nil
    }

    // MARK: - Setup Methods

    func setRefreshResponse(_ response: AuthResponse) {
        mockRefreshResponse = response
        shouldThrowOnRefresh = false
    }

    func setRefreshError(_ error: Error) {
        mockRefreshError = error
        shouldThrowOnRefresh = true
    }

    func setAccessToken(_ token: String?) {
        _mockAccessToken = token
        // Also update the thread-safe storage
        accessTokenLock.lock()
        _unsafeAccessToken = token
        accessTokenLock.unlock()
    }

    func setRefreshDelay(_ delay: TimeInterval) {
        refreshDelay = delay
    }

    func reset() {
        refreshTokenCalled = false
        refreshTokenCallCount = 0
        logoutCalled = false
        logoutCallCount = 0
        mockRefreshResponse = nil
        mockRefreshError = nil
        shouldThrowOnRefresh = false
        refreshDelay = 0
    }

    // MARK: - AuthServiceProtocol Implementation

    func refreshToken() async throws -> AuthResponse {
        refreshTokenCalled = true
        refreshTokenCallCount += 1

        // Simulate network delay if configured
        if refreshDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(refreshDelay * 1_000_000_000))
        }

        if shouldThrowOnRefresh {
            throw mockRefreshError ?? APIError.unauthorized(message: "Refresh failed")
        }

        guard let response = mockRefreshResponse else {
            throw APIError.unauthorized(message: "No mock response configured")
        }

        return response
    }

    func logout() async throws {
        logoutCalled = true
        logoutCallCount += 1
        _mockAccessToken = nil
        // Update thread-safe storage with lock
        accessTokenLock.lock()
        _unsafeAccessToken = nil
        accessTokenLock.unlock()
    }

    nonisolated func getAccessToken() -> String? {
        // Use lock to safely read cross-isolation
        accessTokenLock.lock()
        defer { accessTokenLock.unlock() }
        return _unsafeAccessToken
    }

    // MARK: - Unused Protocol Methods (not tested in TokenRefreshInterceptor)

    func register(
        email _: String,
        password _: String,
        firstName _: String,
        lastName _: String,
        birthYear _: Int?,
        educationLevel _: EducationLevel?,
        country _: String?,
        region _: String?
    ) async throws -> AuthResponse {
        fatalError("Not implemented - not used in TokenRefreshInterceptor tests")
    }

    func login(email _: String, password _: String) async throws -> AuthResponse {
        fatalError("Not implemented - not used in TokenRefreshInterceptor tests")
    }

    func deleteAccount() async throws {
        fatalError("Not implemented - not used in TokenRefreshInterceptor tests")
    }
}
