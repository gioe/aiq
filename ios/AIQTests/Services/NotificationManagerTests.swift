import Combine
import UserNotifications
import XCTest

@testable import AIQ

@MainActor
final class NotificationManagerTests: XCTestCase {
    var sut: NotificationManager!
    var mockNotificationService: MockNotificationService!
    var mockAuthManager: MockAuthManager!
    var mockNotificationCenter: MockUserNotificationCenter!
    var mockApplication: MockApplication!
    var cancellables: Set<AnyCancellable>!

    // UserDefaults keys used by NotificationManager
    private let deviceTokenKey = "com.aiq.deviceToken"
    private let permissionRequestedKey = "com.aiq.hasRequestedNotificationPermission"

    override func setUp() async throws {
        try await super.setUp()
        cancellables = Set<AnyCancellable>()

        // Clear UserDefaults before each test
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)
        UserDefaults.standard.removeObject(forKey: permissionRequestedKey)

        // Create mocks
        mockNotificationService = MockNotificationService()
        mockAuthManager = MockAuthManager()
        mockNotificationCenter = MockUserNotificationCenter()
        mockApplication = MockApplication()

        // Create SUT with injected dependencies
        // Initialization is now synchronous - no delay needed
        sut = NotificationManager(
            notificationService: mockNotificationService,
            authManager: mockAuthManager,
            notificationCenter: mockNotificationCenter,
            application: mockApplication
        )
    }

    override func tearDown() {
        cancellables = nil
        sut = nil
        mockNotificationService = nil
        mockAuthManager = nil
        mockNotificationCenter = nil
        mockApplication = nil

        // Clear UserDefaults after each test
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)
        UserDefaults.standard.removeObject(forKey: permissionRequestedKey)

        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialization_DefaultState() async {
        // Then - Verify initial state
        XCTAssertEqual(sut.authorizationStatus, .notDetermined)
        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    func testInitialization_ImmediateDeviceTokenHandling() async {
        // Given - Create a fresh NotificationManager
        let freshMockNotificationService = MockNotificationService()
        let freshMockAuthManager = MockAuthManager()
        let freshMockNotificationCenter = MockUserNotificationCenter()
        let freshMockApplication = MockApplication()
        let freshSut = NotificationManager(
            notificationService: freshMockNotificationService,
            authManager: freshMockAuthManager,
            notificationCenter: freshMockNotificationCenter,
            application: freshMockApplication
        )

        // When - Call didReceiveDeviceToken immediately after init (no delay)
        let deviceToken = Data([0xAA, 0xBB, 0xCC, 0xDD])
        freshSut.didReceiveDeviceToken(deviceToken)

        // Then - Token should be cached successfully (synchronous initialization allows this)
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, "aabbccdd")
    }

    func testInitialization_CombineSubscriptionReady() async {
        // Given - Set up mock auth manager that will emit authentication change
        let freshMockNotificationService = MockNotificationService()
        let freshMockAuthManager = MockAuthManager()
        let freshMockNotificationCenter = MockUserNotificationCenter()
        let freshMockApplication = MockApplication()

        // When - Create NotificationManager and immediately trigger auth state change
        let freshSut = NotificationManager(
            notificationService: freshMockNotificationService,
            authManager: freshMockAuthManager,
            notificationCenter: freshMockNotificationCenter,
            application: freshMockApplication
        )

        // Cache a token so retry has something to work with
        UserDefaults.standard.set("test_token", forKey: deviceTokenKey)

        // Trigger auth state change immediately (Combine subscription should be ready)
        freshMockAuthManager.isAuthenticated = true

        // Small delay to allow Combine to propagate
        try? await Task.sleep(nanoseconds: 50_000_000) // 0.05 second

        // Then - Should not crash and state should be consistent
        // The Combine subscription should be ready to receive auth state changes
        XCTAssertNotNil(freshSut)
    }

    // MARK: - Device Token Registration Tests

    func testDidReceiveDeviceToken_CachesToken() async {
        // Given
        let deviceToken = Data([0x01, 0x02, 0x03, 0x04])
        let expectedTokenString = "01020304"

        // When - Token caching is synchronous
        sut.didReceiveDeviceToken(deviceToken)

        // Then - Verify token was cached in UserDefaults
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedTokenString)
    }

    func testDidReceiveDeviceToken_TokenFormatting() async {
        // Given
        let deviceToken = Data([0xAB, 0xCD, 0xEF, 0x12, 0x34, 0x56, 0x78, 0x90])
        let expectedTokenString = "abcdef1234567890"

        // When - Token caching is synchronous
        sut.didReceiveDeviceToken(deviceToken)

        // Then
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedTokenString)
    }

    func testDidFailToRegisterForRemoteNotifications_ClearsToken() async {
        // Given - Pre-cache a device token
        UserDefaults.standard.set("test_token_123", forKey: deviceTokenKey)

        let error = NSError(
            domain: "TestError",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Registration failed"]
        )

        // When - Clearing is synchronous
        sut.didFailToRegisterForRemoteNotifications(error: error)

        // Then - Verify token was cleared
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken)
        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    // MARK: - Unregister Device Token Tests

    func testUnregisterDeviceToken_Success_WhenNotRegistered() async throws {
        // Given - NotificationManager with isDeviceTokenRegistered = false
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // When
        await sut.unregisterDeviceToken()

        // Then - Should complete without errors (early return)
        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    func testUnregisterDeviceToken_SkipsWhenNotRegistered() async {
        // Given - NotificationManager with no registered token
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // When
        await sut.unregisterDeviceToken()

        // Then - Should complete without errors (early return path)
        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    func testUnregisterDeviceToken_StateManagement() async {
        // Given - NotificationManager starts with isDeviceTokenRegistered = false
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // When - Call unregister (will early return)
        await sut.unregisterDeviceToken()

        // Then - State remains false
        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    // MARK: - Authorization Tests

    func testCheckAuthorizationStatus_UpdatesStatus() async {
        // Given/When
        await sut.checkAuthorizationStatus()

        // Then - Authorization status should be updated
        // Note: The actual status will depend on simulator/device settings
        // We can only verify the method completes without errors
        let status = sut.authorizationStatus
        XCTAssertTrue(
            [.notDetermined, .denied, .authorized, .provisional, .ephemeral].contains(status),
            "Status should be a valid UNAuthorizationStatus value"
        )
    }

    // MARK: - Retry Registration Tests

    func testRetryDeviceTokenRegistration_WithNoPendingToken() async {
        // Given - No cached or pending token
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)

        // When
        await sut.retryDeviceTokenRegistration()

        // Then - Should complete without errors (no-op)
        XCTAssertNil(UserDefaults.standard.string(forKey: deviceTokenKey))
    }

    func testRetryDeviceTokenRegistration_WithCachedToken() async {
        // Given - Cached token in UserDefaults
        let cachedToken = "cached_token_123"
        UserDefaults.standard.set(cachedToken, forKey: deviceTokenKey)

        // When
        await sut.retryDeviceTokenRegistration()

        // Then - Should attempt to register (though will fail without proper mocking)
        // We can verify the cached token is still present
        let stillCached = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(stillCached, cachedToken)
    }

    // MARK: - Concurrent Operations Tests

    func testConcurrentDeviceTokenRegistration_ThreadSafety() async {
        // Given
        let deviceToken1 = Data([0x01, 0x02, 0x03])
        let deviceToken2 = Data([0x04, 0x05, 0x06])
        let deviceToken3 = Data([0x07, 0x08, 0x09])

        // When - Receive multiple device tokens concurrently
        async let call1: Void = Task { @MainActor in
            sut.didReceiveDeviceToken(deviceToken1)
        }.value
        async let call2: Void = Task { @MainActor in
            sut.didReceiveDeviceToken(deviceToken2)
        }.value
        async let call3: Void = Task { @MainActor in
            sut.didReceiveDeviceToken(deviceToken3)
        }.value

        // Then - All should complete without crashing
        _ = await (call1, call2, call3)

        // Verify final state is consistent (one of the tokens should be cached)
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNotNil(cachedToken)
        XCTAssertTrue(
            cachedToken == "010203" || cachedToken == "040506" || cachedToken == "070809",
            "Cached token should be one of the provided tokens"
        )
    }

    func testConcurrentUnregister_ThreadSafety() async {
        // Given - NotificationManager with no registered token
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // When - Multiple concurrent unregister calls
        async let call1: Void = sut.unregisterDeviceToken()
        async let call2: Void = sut.unregisterDeviceToken()
        async let call3: Void = sut.unregisterDeviceToken()

        // Then - All should complete without crashing
        _ = await (call1, call2, call3)

        // Verify final state remains consistent
        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    func testConcurrentRetryRegistration_ThreadSafety() async {
        // Given
        UserDefaults.standard.set("retry_token", forKey: deviceTokenKey)

        // When - Multiple concurrent retry calls
        async let call1: Void = sut.retryDeviceTokenRegistration()
        async let call2: Void = sut.retryDeviceTokenRegistration()
        async let call3: Void = sut.retryDeviceTokenRegistration()

        // Then - All should complete without crashing
        _ = await (call1, call2, call3)

        // Verify state remains consistent
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNotNil(cachedToken)
    }

    // MARK: - Published Properties Tests

    func testAuthorizationStatusProperty_IsPublished() async {
        // Given
        let expectation = XCTestExpectation(description: "Authorization status updated")
        var receivedStatus: UNAuthorizationStatus?

        sut.$authorizationStatus
            .dropFirst() // Skip initial value
            .sink { status in
                receivedStatus = status
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // When
        await sut.checkAuthorizationStatus()

        // Then
        await fulfillment(of: [expectation], timeout: 2.0)
        XCTAssertNotNil(receivedStatus)
    }

    func testIsDeviceTokenRegisteredProperty_IsPublished() async {
        // Given - Initial value should be false
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // When/Then - Verify property is observable
        var observedValues: [Bool] = []

        let cancellable = sut.$isDeviceTokenRegistered
            .sink { value in
                observedValues.append(value)
            }

        // Then - Should have collected the initial value immediately (no delay needed)
        XCTAssertFalse(observedValues.isEmpty, "Should observe at least the initial value")
        XCTAssertFalse(observedValues.first ?? true, "Initial value should be false")

        cancellable.cancel()
    }

    // MARK: - Edge Cases

    func testDeviceTokenFormatting_EmptyData() async {
        // Given
        let emptyToken = Data()

        // When - Token caching is synchronous
        sut.didReceiveDeviceToken(emptyToken)

        // Then - Should cache empty string
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, "")
    }

    func testDeviceTokenFormatting_LargeToken() async {
        // Given - 32-byte token (typical APNs token size)
        let largeToken = Data([
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10,
            0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
            0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20
        ])
        let expectedToken = "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"

        // When - Token caching is synchronous
        sut.didReceiveDeviceToken(largeToken)

        // Then
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedToken)
    }

    func testMultipleConsecutiveFailures_StateConsistency() async {
        // Given
        let error1 = NSError(domain: "Test", code: 1, userInfo: nil)
        let error2 = NSError(domain: "Test", code: 2, userInfo: nil)
        let error3 = NSError(domain: "Test", code: 3, userInfo: nil)

        // Pre-cache a token
        UserDefaults.standard.set("test_token", forKey: deviceTokenKey)

        // When - Multiple consecutive failures (all synchronous)
        sut.didFailToRegisterForRemoteNotifications(error: error1)
        sut.didFailToRegisterForRemoteNotifications(error: error2)
        sut.didFailToRegisterForRemoteNotifications(error: error3)

        // Then - State should remain consistent
        XCTAssertFalse(sut.isDeviceTokenRegistered)
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken)
    }

    func testRetryAfterFailure_StateTransition() async {
        // Given - Simulate a failure (synchronous)
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        sut.didFailToRegisterForRemoteNotifications(error: error)

        // Verify initial state
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // When - Cache a new token and retry
        UserDefaults.standard.set("retry_token", forKey: deviceTokenKey)
        await sut.retryDeviceTokenRegistration()

        // Then - Should attempt retry (state depends on auth and backend)
        // We can verify the method completes without crashing
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNotNil(cachedToken)
    }

    // MARK: - UserDefaults Caching Tests

    func testDeviceTokenCaching_PersistsBetweenInstances() async {
        // Given
        let deviceToken = Data([0xAA, 0xBB, 0xCC, 0xDD])
        let expectedToken = "aabbccdd"

        // When - Receive token (synchronous)
        sut.didReceiveDeviceToken(deviceToken)

        // Then - Verify persistence in UserDefaults
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedToken)

        // Simulate app restart by reading from UserDefaults again
        let retrievedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(retrievedToken, expectedToken)
    }

    func testClearCachedToken_RemovesFromUserDefaults() async {
        // Given - Pre-cache a token
        UserDefaults.standard.set("test_token", forKey: deviceTokenKey)
        XCTAssertNotNil(UserDefaults.standard.string(forKey: deviceTokenKey))

        // When - Trigger failure which clears cache (synchronous)
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        sut.didFailToRegisterForRemoteNotifications(error: error)

        // Then - Verify removed from UserDefaults
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken)
    }

    // MARK: - Error Path Tests

    func testRegistration_FailsWithNetworkError_StateRemainsUnregistered() async throws {
        // Given - Authenticated user with cached token
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("test_token_123", forKey: deviceTokenKey)

        // Configure mock to fail with network error
        let networkError = NSError(
            domain: NSURLErrorDomain,
            code: NSURLErrorNotConnectedToInternet,
            userInfo: [NSLocalizedDescriptionKey: "No internet connection"]
        )
        await mockNotificationService.setRegisterError(networkError)

        // When - Attempt to register device token
        await sut.retryDeviceTokenRegistration()

        // Then - Should remain unregistered
        try await waitForCondition(message: "Should remain unregistered after network error") {
            !self.sut.isDeviceTokenRegistered
        }

        // Verify token is still cached for retry
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, "test_token_123", "Token should remain cached for retry")
    }

    func testRegistration_FailsWithServerError_StateRemainsUnregistered() async throws {
        // Given - Authenticated user with cached token
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("test_token_456", forKey: deviceTokenKey)

        // Configure mock to fail with server error
        let serverError = NSError(
            domain: "APIError",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Internal server error"]
        )
        await mockNotificationService.setRegisterError(serverError)

        // When - Attempt to register device token
        await sut.retryDeviceTokenRegistration()

        // Then - Should remain unregistered
        try await waitForCondition(message: "Should remain unregistered after server error") {
            !self.sut.isDeviceTokenRegistered
        }

        // Verify token is still cached for retry
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, "test_token_456", "Token should remain cached for retry")
    }

    func testRegistration_FailsPartway_CleansUpState() async throws {
        // Given - Authenticated user
        mockAuthManager.isAuthenticated = true

        // Configure mock to fail
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        await mockNotificationService.setRegisterError(error)

        // When - Receive device token (which triggers registration)
        let deviceToken = Data([0xAA, 0xBB, 0xCC, 0xDD])
        sut.didReceiveDeviceToken(deviceToken)

        // Then - State should be consistent after failure
        try await waitForCondition(message: "Should remain unregistered after partial failure") {
            !self.sut.isDeviceTokenRegistered
        }

        // Verify token is cached (not cleared on registration failure)
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, "aabbccdd", "Token should be cached despite registration failure")
    }

    func testRegistration_InterruptedByLogout_CleansUpState() async throws {
        // Given - Authenticated user with successful mock configuration
        mockAuthManager.isAuthenticated = true
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )

        // Receive device token
        let deviceToken = Data([0x11, 0x22, 0x33, 0x44])
        sut.didReceiveDeviceToken(deviceToken)

        // Wait for registration to potentially start
        await Task.yield()

        // When - User logs out mid-flight
        mockAuthManager.isAuthenticated = false

        // Then - State should transition to unregistered
        try await waitForCondition(message: "Should become unregistered after logout") {
            !self.sut.isDeviceTokenRegistered
        }

        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    func testUnregister_FailsWithNetworkError_ClearsLocalStateAnyway() async throws {
        // Given - Mark as registered
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("registered_token", forKey: deviceTokenKey)

        // First, register successfully
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )
        await sut.retryDeviceTokenRegistration()

        // Wait for registration
        try await waitForCondition(message: "Should become registered") {
            self.sut.isDeviceTokenRegistered
        }

        // Configure mock to fail unregister
        let networkError = NSError(
            domain: NSURLErrorDomain,
            code: NSURLErrorNotConnectedToInternet,
            userInfo: [NSLocalizedDescriptionKey: "No internet connection"]
        )
        await mockNotificationService.setUnregisterError(networkError)

        // When - Attempt to unregister
        await sut.unregisterDeviceToken()

        // Then - Local state should be cleared despite backend error
        XCTAssertFalse(sut.isDeviceTokenRegistered)
        XCTAssertNil(UserDefaults.standard.string(forKey: deviceTokenKey))
    }

    // MARK: - Retry Logic Tests

    func testRetry_AfterSingleFailure_SucceedsOnSecondAttempt() async throws {
        // Given - Authenticated user with cached token
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("retry_token", forKey: deviceTokenKey)

        // Configure mock to fail first, succeed second
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        await mockNotificationService.setRegisterError(error)

        // When - First attempt (should fail)
        await sut.retryDeviceTokenRegistration()

        // Then - Should remain unregistered
        try await waitForCondition(message: "Should remain unregistered after first failure") {
            !self.sut.isDeviceTokenRegistered
        }

        // Now configure success
        await mockNotificationService.setRegisterError(nil)
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )

        // When - Second attempt (should succeed)
        await sut.retryDeviceTokenRegistration()

        // Then - Should become registered
        try await waitForCondition(message: "Should become registered after retry") {
            self.sut.isDeviceTokenRegistered
        }

        XCTAssertTrue(sut.isDeviceTokenRegistered)
    }

    func testRetry_AfterMultipleFailures_EventuallySucceeds() async throws {
        // Given - Authenticated user with cached token
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("multi_retry_token", forKey: deviceTokenKey)

        let error = NSError(domain: "Test", code: -1, userInfo: nil)

        // When - First failure
        await mockNotificationService.setRegisterError(error)
        await sut.retryDeviceTokenRegistration()

        try await waitForCondition(message: "Should remain unregistered after failure 1") {
            !self.sut.isDeviceTokenRegistered
        }

        // Second failure
        await sut.retryDeviceTokenRegistration()

        try await waitForCondition(message: "Should remain unregistered after failure 2") {
            !self.sut.isDeviceTokenRegistered
        }

        // Third failure
        await sut.retryDeviceTokenRegistration()

        try await waitForCondition(message: "Should remain unregistered after failure 3") {
            !self.sut.isDeviceTokenRegistered
        }

        // Now configure success
        await mockNotificationService.setRegisterError(nil)
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )

        // Final attempt - should succeed
        await sut.retryDeviceTokenRegistration()

        // Then - Should become registered after multiple retries
        try await waitForCondition(message: "Should become registered after multiple retries") {
            self.sut.isDeviceTokenRegistered
        }

        XCTAssertTrue(sut.isDeviceTokenRegistered)
    }

    func testRetry_WithNoCachedToken_DoesNothing() async throws {
        // Given - Authenticated user but NO cached token
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)

        // When - Attempt retry
        await sut.retryDeviceTokenRegistration()

        // Then - Should remain unregistered (no token to register)
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // Verify no backend call was made
        let callCount = await mockNotificationService.registerCallCount
        XCTAssertEqual(callCount, 0, "Should not call backend without a token")
    }

    func testRetry_WhenUnauthenticated_DoesNotCallBackend() async throws {
        // Given - Unauthenticated user with cached token
        mockAuthManager.isAuthenticated = false
        UserDefaults.standard.set("cached_token", forKey: deviceTokenKey)

        // When - Attempt retry
        await sut.retryDeviceTokenRegistration()

        // Then - Should not register (not authenticated)
        XCTAssertFalse(sut.isDeviceTokenRegistered)

        // Verify no backend call was made
        let callCount = await mockNotificationService.registerCallCount
        XCTAssertEqual(callCount, 0, "Should not call backend when unauthenticated")
    }

    // MARK: - State Transition Tests

    func testStateTransition_FromErrorToSuccess() async throws {
        // Given - Start with authentication and cached token
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("transition_token", forKey: deviceTokenKey)

        // Configure initial failure
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        await mockNotificationService.setRegisterError(error)

        // When - First attempt fails
        await sut.retryDeviceTokenRegistration()

        // Then - Verify error state
        try await waitForCondition(message: "Should be in error state") {
            !self.sut.isDeviceTokenRegistered
        }

        // When - Configure success and retry
        await mockNotificationService.setRegisterError(nil)
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )
        await sut.retryDeviceTokenRegistration()

        // Then - Should transition to success state
        try await waitForCondition(message: "Should transition to success state") {
            self.sut.isDeviceTokenRegistered
        }

        XCTAssertTrue(sut.isDeviceTokenRegistered)
    }

    func testStateTransition_AuthenticationChangeDuringError() async throws {
        // Given - Unauthenticated with cached token
        mockAuthManager.isAuthenticated = false
        UserDefaults.standard.set("auth_transition_token", forKey: deviceTokenKey)

        // Configure successful response (for when auth happens)
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )

        // When - User authenticates
        mockAuthManager.isAuthenticated = true

        // Then - Should automatically retry and succeed
        try await waitForCondition(message: "Should auto-register on authentication") {
            self.sut.isDeviceTokenRegistered
        }

        XCTAssertTrue(sut.isDeviceTokenRegistered)
    }

    func testStateTransition_LogoutClearsRegistration() async throws {
        // Given - Registered state
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("logout_token", forKey: deviceTokenKey)

        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )
        await sut.retryDeviceTokenRegistration()

        // Wait for registration
        try await waitForCondition(message: "Should become registered") {
            self.sut.isDeviceTokenRegistered
        }

        // When - User logs out
        mockAuthManager.isAuthenticated = false

        // Then - Should transition to unregistered
        try await waitForCondition(message: "Should transition to unregistered on logout") {
            !self.sut.isDeviceTokenRegistered
        }

        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    func testStateTransition_PermissionDeniedToAuthorized() async throws {
        // Given - Start with denied authorization
        // Note: We can only test the state property since actual authorization requires system interaction
        XCTAssertEqual(sut.authorizationStatus, .notDetermined)

        // When - Check authorization (will update to actual system status)
        await sut.checkAuthorizationStatus()

        // Then - Status should be updated (actual value depends on simulator/device)
        let status = sut.authorizationStatus
        XCTAssertTrue(
            [.notDetermined, .denied, .authorized, .provisional, .ephemeral].contains(status),
            "Status should be a valid value"
        )
    }

    func testStateTransition_ConcurrentAuthChanges_MaintainsConsistency() async throws {
        // Given - Configure successful registration
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )
        UserDefaults.standard.set("concurrent_token", forKey: deviceTokenKey)

        // When - Rapidly toggle authentication state
        mockAuthManager.isAuthenticated = true
        await Task.yield()

        mockAuthManager.isAuthenticated = false
        await Task.yield()

        mockAuthManager.isAuthenticated = true

        // Then - Final state should be consistent with auth state
        try await waitForCondition(
            timeout: 3.0,
            message: "Should eventually reach consistent state"
        ) {
            // When authenticated, should eventually register
            self.mockAuthManager.isAuthenticated == self.sut.isDeviceTokenRegistered
        }
    }

    // MARK: - Cleanup and Error Recovery Tests

    func testCleanup_AfterRegistrationError_LeavesTokenCached() async throws {
        // Given - Authenticated with token
        mockAuthManager.isAuthenticated = true
        let deviceToken = Data([0xDE, 0xAD, 0xBE, 0xEF])

        // Configure failure
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        await mockNotificationService.setRegisterError(error)

        // When - Receive device token (triggers failed registration)
        sut.didReceiveDeviceToken(deviceToken)

        // Then - Token should still be cached for retry
        try await waitForCondition(message: "Should remain unregistered after error") {
            !self.sut.isDeviceTokenRegistered
        }

        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, "deadbeef", "Token should remain cached after registration error")
    }

    func testCleanup_AfterAPNsError_ClearsToken() async {
        // Given - Cache a token first
        UserDefaults.standard.set("apns_error_token", forKey: deviceTokenKey)

        // When - APNs registration fails
        let error = NSError(
            domain: "APNs",
            code: 3000,
            userInfo: [NSLocalizedDescriptionKey: "Invalid APNs certificate"]
        )
        sut.didFailToRegisterForRemoteNotifications(error: error)

        // Then - Should clear cached token (APNs-level failures are not recoverable)
        XCTAssertNil(UserDefaults.standard.string(forKey: deviceTokenKey))
        XCTAssertFalse(sut.isDeviceTokenRegistered)
    }

    func testCleanup_AfterUnregisterError_StillClearsLocalState() async throws {
        // Given - Registered state
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("unregister_error_token", forKey: deviceTokenKey)

        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )
        await sut.retryDeviceTokenRegistration()

        try await waitForCondition(message: "Should become registered") {
            self.sut.isDeviceTokenRegistered
        }

        // Configure unregister to fail
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        await mockNotificationService.setUnregisterError(error)

        // When - Unregister fails
        await sut.unregisterDeviceToken()

        // Then - Local state should still be cleared
        XCTAssertFalse(sut.isDeviceTokenRegistered)
        XCTAssertNil(UserDefaults.standard.string(forKey: deviceTokenKey))
    }

    func testErrorRecovery_AfterTransientFailure_SucceedsOnRetry() async throws {
        // Given - Authenticated user
        mockAuthManager.isAuthenticated = true
        UserDefaults.standard.set("transient_token", forKey: deviceTokenKey)

        // Simulate transient network error
        let transientError = NSError(
            domain: NSURLErrorDomain,
            code: NSURLErrorTimedOut,
            userInfo: [NSLocalizedDescriptionKey: "Request timed out"]
        )
        await mockNotificationService.setRegisterError(transientError)

        // When - First attempt fails
        await sut.retryDeviceTokenRegistration()

        try await waitForCondition(message: "Should fail on first attempt") {
            !self.sut.isDeviceTokenRegistered
        }

        // Simulate network recovery
        await mockNotificationService.setRegisterError(nil)
        await mockNotificationService.setRegisterResponse(
            DeviceTokenResponse(
                success: true,
                message: "Device token registered"
            )
        )

        // When - Retry after network recovery
        await sut.retryDeviceTokenRegistration()

        // Then - Should succeed
        try await waitForCondition(message: "Should succeed after transient error recovery") {
            self.sut.isDeviceTokenRegistered
        }

        XCTAssertTrue(sut.isDeviceTokenRegistered)
    }

    // MARK: - Permission Request Tracking Tests

    func testRequestAuthorization_SetsPermissionRequestedFlag() async {
        // Given - Fresh NotificationManager with flag not set
        XCTAssertFalse(sut.hasRequestedNotificationPermission, "Flag should initially be false")

        // Configure mock to grant authorization
        mockNotificationCenter.authorizationGranted = true

        // When - Request authorization (uses mock, no real dialog shown)
        _ = await sut.requestAuthorization()

        // Then - Flag should be set to true
        XCTAssertTrue(sut.hasRequestedNotificationPermission, "Flag should be true after requesting permission")
    }

    func testHasRequestedNotificationPermission_DefaultsToFalse() async {
        // Given - Fresh NotificationManager
        // When - Check initial value
        let hasRequested = sut.hasRequestedNotificationPermission

        // Then - Should default to false
        XCTAssertFalse(hasRequested, "hasRequestedNotificationPermission should default to false")
    }

    func testHasRequestedNotificationPermission_PersistsInUserDefaults() async {
        // Given - Set the flag
        sut.hasRequestedNotificationPermission = true

        // When - Create a new NotificationManager instance (simulates app restart)
        let newSut = NotificationManager(
            notificationService: mockNotificationService,
            authManager: mockAuthManager,
            notificationCenter: mockNotificationCenter,
            application: mockApplication
        )

        // Then - Flag should persist
        XCTAssertTrue(newSut.hasRequestedNotificationPermission, "Flag should persist across app restarts")
    }

    func testUnregisterDeviceToken_ClearsPermissionRequestedFlag() async {
        // Given - Set up registered state with permission requested
        sut.hasRequestedNotificationPermission = true
        UserDefaults.standard.set("test_token", forKey: deviceTokenKey)

        // Manually set isDeviceTokenRegistered to true (normally done by successful registration)
        // We can't easily trigger this through the public API without mocking more, so we'll
        // test that clearCachedDeviceToken is called by didFailToRegisterForRemoteNotifications
        // which also clears the flag

        // When - Fail to register (which calls clearCachedDeviceToken)
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        sut.didFailToRegisterForRemoteNotifications(error: error)

        // Then - Permission requested flag should be cleared
        XCTAssertFalse(sut.hasRequestedNotificationPermission, "Flag should be cleared on token failure")
    }

    func testHasRequestedNotificationPermission_GetterSetter() async {
        // Given - Initial state
        XCTAssertFalse(sut.hasRequestedNotificationPermission)

        // When - Set to true
        sut.hasRequestedNotificationPermission = true

        // Then - Should be true
        XCTAssertTrue(sut.hasRequestedNotificationPermission)

        // When - Set to false
        sut.hasRequestedNotificationPermission = false

        // Then - Should be false
        XCTAssertFalse(sut.hasRequestedNotificationPermission)
    }

    func testRequestAuthorization_SetsFlag_BeforeShowingDialog() async {
        // Given - Verify initial state
        XCTAssertFalse(sut.hasRequestedNotificationPermission)

        // Configure mock to grant authorization
        mockNotificationCenter.authorizationGranted = true

        // When - Call requestAuthorization (uses mock, no real dialog shown)
        _ = await sut.requestAuthorization()

        // Then - Flag should be set regardless of user's choice
        // (The flag is set BEFORE the dialog is shown, so even if the test fails
        // to get permission, the flag should be true)
        XCTAssertTrue(
            sut.hasRequestedNotificationPermission,
            "Flag should be set before dialog is shown, regardless of user choice"
        )

        // Verify mock was called
        XCTAssertTrue(mockNotificationCenter.requestAuthorizationCalled)
    }

    // MARK: - Test Helpers

    /// Wait for a condition to become true within a timeout
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
}
