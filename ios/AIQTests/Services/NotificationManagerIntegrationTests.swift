import Combine
import UserNotifications
import XCTest

@testable import AIQ

/// Integration tests for NotificationManager
///
/// These tests verify NotificationManager correctly interacts with its dependencies:
/// - AuthManager for authentication state changes
/// - NotificationService for backend API calls
/// - UserDefaults for token persistence
///
/// Integration tests differ from unit tests by:
/// 1. Testing interactions between NotificationManager and its dependencies
/// 2. Verifying data flows across service boundaries
/// 3. Testing complex, multi-step scenarios
/// 4. Using mocks to simulate realistic service responses
@MainActor
final class NotificationManagerIntegrationTests: XCTestCase {
    var sut: NotificationManager!
    var mockNotificationService: MockNotificationService!
    var mockAuthManager: MockAuthManager!
    var cancellables: Set<AnyCancellable>!

    // UserDefaults key used by NotificationManager
    private let deviceTokenKey = "com.aiq.deviceToken"

    // MARK: - Async Test Helpers

    /// Wait for a condition to become true with timeout
    /// - Parameters:
    ///   - condition: The condition to wait for
    ///   - timeout: Maximum time to wait (default 2.0 seconds)
    ///   - message: Failure message if timeout is reached
    private func waitForCondition(
        timeout: TimeInterval = 2.0,
        message: String = "Condition not met within timeout",
        _ condition: @escaping () async -> Bool
    ) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while await !condition() {
            if Date() > deadline {
                XCTFail(message)
                return
            }
            await Task.yield()
        }
    }

    /// Wait for mock service to receive a register call
    private func waitForRegisterCall(timeout: TimeInterval = 2.0) async throws {
        try await waitForCondition(timeout: timeout, message: "registerDeviceToken was not called within timeout") {
            await mockNotificationService.registerDeviceTokenCalled
        }
    }

    /// Wait for device token registration state to change
    private func waitForRegistrationState(_ expected: Bool, timeout: TimeInterval = 2.0) async throws {
        try await waitForCondition(timeout: timeout, message: "isDeviceTokenRegistered did not become \(expected) within timeout") {
            sut.isDeviceTokenRegistered == expected
        }
    }

    override func setUp() async throws {
        try await super.setUp()
        cancellables = Set<AnyCancellable>()

        // Clear UserDefaults before each test
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)

        // Create mocks
        mockNotificationService = MockNotificationService()
        mockAuthManager = MockAuthManager()

        // Create SUT with injected dependencies
        sut = NotificationManager(
            notificationService: mockNotificationService,
            authManager: mockAuthManager
        )
    }

    override func tearDown() {
        cancellables = nil
        sut = nil
        mockNotificationService = nil
        mockAuthManager = nil

        // Clear UserDefaults after each test
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)

        super.tearDown()
    }

    // MARK: - Auth State Integration Tests

    func testAuthStateChange_UnauthenticatedToAuthenticated_TriggersRegistration() async throws {
        // Given - User is unauthenticated with a cached device token
        XCTAssertFalse(mockAuthManager.isAuthenticated, "Should start unauthenticated")

        let deviceToken = "test_token_123"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Configure mock service to succeed
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        // When - User authenticates
        mockAuthManager.isAuthenticated = true

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        // Then - Should call notificationService.registerDeviceToken
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        let lastToken = await mockNotificationService.lastRegisteredToken
        let registerCount = await mockNotificationService.registerCallCount

        XCTAssertTrue(registerCalled, "Should call registerDeviceToken on auth state change")
        XCTAssertEqual(lastToken, deviceToken, "Should register correct token, got \(lastToken ?? "nil")")
        XCTAssertEqual(registerCount, 1, "Should call register exactly once, got \(registerCount)")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should update isDeviceTokenRegistered to true")
    }

    func testAuthStateChange_AuthenticatedToUnauthenticated_ClearsRegistrationState() async throws {
        // Given - User is authenticated with registered token
        mockAuthManager.isAuthenticated = true

        let deviceToken = "test_token_456"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Configure mock service for initial registration
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        // Trigger registration
        await sut.retryDeviceTokenRegistration()

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        // Verify registered
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered before logout")

        // When - User logs out
        mockAuthManager.isAuthenticated = false

        // Wait for state to clear
        try await waitForRegistrationState(false)

        // Then - Should clear registration state but NOT clear cached token
        // Note: Logout only clears isDeviceTokenRegistered; it does NOT call unregisterDeviceToken()
        // on the backend. The token is kept cached for re-registration on next login.
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should clear isDeviceTokenRegistered on logout")

        // Token should still be cached for next login
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, deviceToken, "Should keep token cached for next login")
    }

    // MARK: - Device Token Registration Flow Tests

    func testDeviceTokenRegistration_WhenAuthenticated_RegistersWithBackend() async throws {
        // Given - User is authenticated
        mockAuthManager.isAuthenticated = true

        let deviceToken = Data([0xAB, 0xCD, 0xEF, 0x12])
        let expectedTokenString = "abcdef12"

        // Configure mock service to succeed
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        // When - Device token is received
        sut.didReceiveDeviceToken(deviceToken)

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        // Then - Should register with backend
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        let lastToken = await mockNotificationService.lastRegisteredToken
        let registerCount = await mockNotificationService.registerCallCount

        XCTAssertTrue(registerCalled, "Should call registerDeviceToken")
        XCTAssertEqual(lastToken, expectedTokenString, "Should register correct token, got \(lastToken ?? "nil")")
        XCTAssertEqual(registerCount, 1, "Should call register exactly once, got \(registerCount)")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should update isDeviceTokenRegistered to true")

        // Verify token was cached
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedTokenString, "Should cache token in UserDefaults")
    }

    func testDeviceTokenRegistration_WhenUnauthenticated_CachesForLater() async throws {
        // Given - User is NOT authenticated
        XCTAssertFalse(mockAuthManager.isAuthenticated, "Should start unauthenticated")

        let deviceToken = Data([0x01, 0x02, 0x03, 0x04])
        let expectedTokenString = "01020304"

        // When - Device token is received
        sut.didReceiveDeviceToken(deviceToken)

        // Wait for token to be cached (poll for UserDefaults update)
        try await waitForCondition(message: "Token should be cached in UserDefaults") {
            UserDefaults.standard.string(forKey: self.deviceTokenKey) == expectedTokenString
        }

        // Then - Should cache token but NOT register with backend
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        let registerCount = await mockNotificationService.registerCallCount

        XCTAssertFalse(registerCalled, "Should NOT call registerDeviceToken when unauthenticated")
        XCTAssertEqual(registerCount, 0, "Should not call register, got \(registerCount) calls")
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should NOT update isDeviceTokenRegistered")

        // Verify token was cached for later
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedTokenString, "Should cache token for later registration")
    }

    func testDeviceTokenRegistration_BackendError_KeepsTokenForRetry() async {
        // Given - User is authenticated
        mockAuthManager.isAuthenticated = true

        let deviceToken = "error_token_789"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Configure mock service to fail
        let mockError = NSError(
            domain: "TestError",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Backend error"]
        )
        await mockNotificationService.setRegisterError(mockError)

        // When - Attempt to register
        await sut.retryDeviceTokenRegistration()

        // Then - Should call backend but keep token for retry
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        let registerCount = await mockNotificationService.registerCallCount

        XCTAssertTrue(registerCalled, "Should attempt to call registerDeviceToken")
        XCTAssertEqual(registerCount, 1, "Should call register once, got \(registerCount)")
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should NOT update isDeviceTokenRegistered on error")

        // Token should still be cached for retry
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, deviceToken, "Should keep token cached for retry after error")
    }

    // MARK: - Device Token Unregistration Flow Tests

    func testDeviceTokenUnregistration_WhenRegistered_UnregistersWithBackend() async throws {
        // Given - Token is registered with backend
        mockAuthManager.isAuthenticated = true

        let deviceToken = "unregister_token_123"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Register first
        let registerResponse = DeviceTokenResponse(
            success: true,
            message: "Registered"
        )
        await mockNotificationService.setRegisterResponse(registerResponse)
        await sut.retryDeviceTokenRegistration()

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered before unregister")

        // Reset mock to track unregister calls
        await mockNotificationService.reset()

        // Configure unregister response
        let unregisterResponse = DeviceTokenResponse(
            success: true,
            message: "Unregistered"
        )
        await mockNotificationService.setUnregisterResponse(unregisterResponse)

        // When - Unregister is called
        await sut.unregisterDeviceToken()

        // Then - Should call backend and clear state
        let unregisterCalled = await mockNotificationService.unregisterDeviceTokenCalled
        let unregisterCount = await mockNotificationService.unregisterCallCount

        XCTAssertTrue(unregisterCalled, "Should call unregisterDeviceToken")
        XCTAssertEqual(unregisterCount, 1, "Should call unregister exactly once, got \(unregisterCount)")
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should clear isDeviceTokenRegistered")

        // Token should be cleared from cache
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken, "Should clear cached token after unregister")
    }

    func testDeviceTokenUnregistration_WhenNotRegistered_SkipsBackendCall() async {
        // Given - No registered token
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should not be registered initially")

        // When - Unregister is called
        await sut.unregisterDeviceToken()

        // Then - Should NOT call backend (early return)
        let unregisterCalled = await mockNotificationService.unregisterDeviceTokenCalled
        let unregisterCount = await mockNotificationService.unregisterCallCount

        XCTAssertFalse(unregisterCalled, "Should NOT call unregisterDeviceToken when not registered")
        XCTAssertEqual(unregisterCount, 0, "Should not call unregister, got \(unregisterCount) calls")
    }

    func testDeviceTokenUnregistration_BackendError_ClearsLocalStateAnyway() async throws {
        // Given - Token is registered
        mockAuthManager.isAuthenticated = true

        let deviceToken = "error_unregister_token"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Register first
        let registerResponse = DeviceTokenResponse(
            success: true,
            message: "Registered"
        )
        await mockNotificationService.setRegisterResponse(registerResponse)
        await sut.retryDeviceTokenRegistration()

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered before unregister")

        // Reset mock
        await mockNotificationService.reset()

        // Configure unregister to fail
        let mockError = NSError(
            domain: "TestError",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Backend error"]
        )
        await mockNotificationService.setUnregisterError(mockError)

        // When - Unregister is called and backend fails
        await sut.unregisterDeviceToken()

        // Then - Should still clear local state
        let unregisterCalled = await mockNotificationService.unregisterDeviceTokenCalled
        XCTAssertTrue(unregisterCalled, "Should attempt to call unregisterDeviceToken")
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should clear isDeviceTokenRegistered even on error")

        // Token should be cleared even though backend failed
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken, "Should clear cached token even on backend error")
    }

    // MARK: - Retry Registration Flow Tests

    func testRetryRegistration_WithCachedToken_CallsBackend() async {
        // Given - Authenticated user with cached token
        mockAuthManager.isAuthenticated = true

        let deviceToken = "retry_token_456"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Configure mock service
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Registered on retry"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        // When - Retry registration
        await sut.retryDeviceTokenRegistration()

        // Then - Should call backend
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        let lastToken = await mockNotificationService.lastRegisteredToken
        let registerCount = await mockNotificationService.registerCallCount

        XCTAssertTrue(registerCalled, "Should call registerDeviceToken on retry")
        XCTAssertEqual(lastToken, deviceToken, "Should register correct token, got \(lastToken ?? "nil")")
        XCTAssertEqual(registerCount, 1, "Should call register exactly once, got \(registerCount)")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should update isDeviceTokenRegistered on success")
    }

    func testRetryRegistration_WithoutToken_SkipsBackendCall() async {
        // Given - Authenticated user with NO cached token
        mockAuthManager.isAuthenticated = true
        XCTAssertNil(UserDefaults.standard.string(forKey: deviceTokenKey), "Should have no cached token")

        // When - Retry registration
        await sut.retryDeviceTokenRegistration()

        // Then - Should NOT call backend (no token to register)
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        let registerCount = await mockNotificationService.registerCallCount

        XCTAssertFalse(registerCalled, "Should NOT call registerDeviceToken without token")
        XCTAssertEqual(registerCount, 0, "Should not call register, got \(registerCount) calls")
    }

    func testRetryRegistration_WhenUnauthenticated_SkipsBackendCall() async {
        // Given - Unauthenticated user with cached token
        XCTAssertFalse(mockAuthManager.isAuthenticated, "Should be unauthenticated")

        let deviceToken = "unauthenticated_retry_token"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // When - Retry registration
        await sut.retryDeviceTokenRegistration()

        // Then - Should NOT call backend (not authenticated)
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        let registerCount = await mockNotificationService.registerCallCount

        XCTAssertFalse(registerCalled, "Should NOT call registerDeviceToken when unauthenticated")
        XCTAssertEqual(registerCount, 0, "Should not call register, got \(registerCount) calls")
    }

    // MARK: - Error Propagation Tests

    func testAPIError_PropagatesCorrectly() async {
        // Given - Authenticated user
        mockAuthManager.isAuthenticated = true

        let deviceToken = "api_error_token"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Configure mock to throw specific error
        let apiError = APIError.unauthorized(message: "Invalid token")
        await mockNotificationService.setRegisterError(apiError)

        // When - Attempt registration
        await sut.retryDeviceTokenRegistration()

        // Then - Should propagate error correctly
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        XCTAssertTrue(registerCalled, "Should attempt to call backend")
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should not mark as registered on error")
    }

    func testNetworkError_PropagatesCorrectly() async {
        // Given - Authenticated user
        mockAuthManager.isAuthenticated = true

        let deviceToken = "network_error_token"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Configure mock to throw network error
        let networkError = NSError(
            domain: NSURLErrorDomain,
            code: NSURLErrorNotConnectedToInternet,
            userInfo: [NSLocalizedDescriptionKey: "No internet connection"]
        )
        await mockNotificationService.setRegisterError(networkError)

        // When - Attempt registration
        await sut.retryDeviceTokenRegistration()

        // Then - Should handle network error
        let registerCalled = await mockNotificationService.registerDeviceTokenCalled
        XCTAssertTrue(registerCalled, "Should attempt to call backend")
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should not mark as registered on network error")

        // Token should be kept for retry
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, deviceToken, "Should keep token for retry after network error")
    }

    // MARK: - Complex Scenario Tests

    func testCompleteFlow_LoginRegisterLogout() async throws {
        // Scenario: User logs in, receives device token, registers, then logs out

        // Given - User logs in
        mockAuthManager.isAuthenticated = true

        // Configure mock service
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Registered"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        let unregisterResponse = DeviceTokenResponse(
            success: true,
            message: "Unregistered"
        )
        await mockNotificationService.setUnregisterResponse(unregisterResponse)

        // When - Device token received
        let tokenData = Data([0xAA, 0xBB, 0xCC, 0xDD])
        sut.didReceiveDeviceToken(tokenData)

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        // Then - Should be registered
        var registerCount = await mockNotificationService.registerCallCount
        XCTAssertEqual(registerCount, 1, "Should call register once, got \(registerCount)")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered after login and token receipt")

        // When - User logs out
        // Note: Reset mock to track subsequent calls after logout
        await mockNotificationService.reset()
        mockAuthManager.isAuthenticated = false

        // Wait for state to clear
        // Note: Logout only clears isDeviceTokenRegistered locally; it does NOT call
        // unregisterDeviceToken() on the backend. The token remains cached for re-registration.
        try await waitForRegistrationState(false)

        // Then - Should clear registration state
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should clear registration state after logout")

        // When - User logs back in
        // Re-configure mock service for re-registration
        await mockNotificationService.setRegisterResponse(mockResponse)
        mockAuthManager.isAuthenticated = true

        // Wait for re-registration
        try await waitForRegistrationState(true)

        // Then - Should re-register with cached token
        registerCount = await mockNotificationService.registerCallCount
        let lastToken = await mockNotificationService.lastRegisteredToken

        XCTAssertEqual(registerCount, 1, "Should call register again after re-login, got \(registerCount)")
        XCTAssertEqual(lastToken, "aabbccdd", "Should re-register with cached token, got \(lastToken ?? "nil")")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered after re-login")
    }

    func testCompleteFlow_ReceiveTokenBeforeLogin() async throws {
        // Scenario: User receives device token before logging in

        // Given - User is NOT authenticated
        XCTAssertFalse(mockAuthManager.isAuthenticated, "Should start unauthenticated")

        let deviceToken = Data([0x11, 0x22, 0x33, 0x44])
        let expectedTokenString = "11223344"

        // When - Device token received before login
        sut.didReceiveDeviceToken(deviceToken)

        // Wait for token to be cached
        try await waitForCondition(message: "Token should be cached in UserDefaults") {
            UserDefaults.standard.string(forKey: self.deviceTokenKey) == expectedTokenString
        }

        // Then - Should cache token but NOT register
        var registerCount = await mockNotificationService.registerCallCount
        XCTAssertEqual(registerCount, 0, "Should not call register before login, got \(registerCount)")

        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedTokenString, "Should cache token before login")

        // When - User logs in
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Registered after login"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        mockAuthManager.isAuthenticated = true

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        // Then - Should register cached token
        registerCount = await mockNotificationService.registerCallCount
        let lastToken = await mockNotificationService.lastRegisteredToken

        XCTAssertEqual(registerCount, 1, "Should call register after login, got \(registerCount)")
        XCTAssertEqual(lastToken, expectedTokenString, "Should register cached token, got \(lastToken ?? "nil")")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered after login")
    }

    func testCompleteFlow_RegistrationFailureAndRetry() async {
        // Scenario: Registration fails, then succeeds on retry

        // Given - User is authenticated
        mockAuthManager.isAuthenticated = true

        let deviceToken = "retry_flow_token"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        // Configure mock to fail first time
        let mockError = NSError(
            domain: "TestError",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        await mockNotificationService.setRegisterError(mockError)

        // When - First registration attempt fails
        await sut.retryDeviceTokenRegistration()

        // Then - Should not be registered
        var registerCount = await mockNotificationService.registerCallCount
        XCTAssertEqual(registerCount, 1, "Should attempt to register, got \(registerCount)")
        XCTAssertFalse(sut.isDeviceTokenRegistered, "Should not be registered after error")

        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, deviceToken, "Should keep token for retry")

        // Reset mock for retry
        await mockNotificationService.reset()

        // Configure mock to succeed
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Registered on retry"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        // When - Retry registration
        await sut.retryDeviceTokenRegistration()

        // Then - Should succeed
        registerCount = await mockNotificationService.registerCallCount
        let lastToken = await mockNotificationService.lastRegisteredToken

        XCTAssertEqual(registerCount, 1, "Should call register on retry, got \(registerCount)")
        XCTAssertEqual(lastToken, deviceToken, "Should register correct token, got \(lastToken ?? "nil")")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered after successful retry")
    }

    // MARK: - State Consistency Tests

    func testStateConsistency_AfterMultipleAuthStateChanges() async throws {
        // Scenario: Rapid auth state changes should maintain consistency

        // Configure mock service
        let deviceToken = "consistency_token"
        UserDefaults.standard.set(deviceToken, forKey: deviceTokenKey)

        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Registered"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        // When - Rapid auth state changes
        mockAuthManager.isAuthenticated = true
        await Task.yield() // Allow Combine to propagate

        mockAuthManager.isAuthenticated = false
        await Task.yield() // Allow Combine to propagate

        mockAuthManager.isAuthenticated = true

        // Wait for final registration state to stabilize
        try await waitForRegistrationState(true)

        // Then - Final state should be consistent
        let registerCount = await mockNotificationService.registerCallCount
        XCTAssertGreaterThanOrEqual(registerCount, 1, "Should call register at least once, got \(registerCount)")
        XCTAssertTrue(sut.isDeviceTokenRegistered, "Should be registered after final auth state = true")

        // Token should still be cached
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, deviceToken, "Should maintain cached token")
    }

    func testStateConsistency_BetweenNotificationManagerInstances() async throws {
        // Scenario: Token should persist across NotificationManager instances

        // Given - First instance registers token
        mockAuthManager.isAuthenticated = true

        let tokenData = Data([0xFF, 0xEE, 0xDD, 0xCC])

        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Registered"
        )
        await mockNotificationService.setRegisterResponse(mockResponse)

        sut.didReceiveDeviceToken(tokenData)

        // Wait for registration to complete
        try await waitForRegistrationState(true)

        XCTAssertTrue(sut.isDeviceTokenRegistered, "First instance should be registered")

        // When - Create new instance (simulating app restart)
        let newMockNotificationService = MockNotificationService()
        let newMockAuthManager = MockAuthManager()
        newMockAuthManager.isAuthenticated = true

        await newMockNotificationService.setRegisterResponse(mockResponse)

        let newSut = NotificationManager(
            notificationService: newMockNotificationService,
            authManager: newMockAuthManager
        )

        // Wait for new instance to register with cached token
        try await waitForCondition(message: "New instance should call register with cached token") {
            await newMockNotificationService.registerDeviceTokenCalled
        }

        // Then - New instance should load cached token and register
        let registerCalled = await newMockNotificationService.registerDeviceTokenCalled
        let lastToken = await newMockNotificationService.lastRegisteredToken

        XCTAssertTrue(registerCalled, "New instance should call register with cached token")
        XCTAssertEqual(lastToken, "ffeeddcc", "New instance should register cached token, got \(lastToken ?? "nil")")

        // Cleanup
        _ = newSut // Keep reference until assertions complete
    }
}
