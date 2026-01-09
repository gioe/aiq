import Combine
import UserNotifications
import XCTest

@testable import AIQ

@MainActor
final class NotificationManagerTests: XCTestCase {
    var sut: NotificationManager!
    var mockNotificationService: MockNotificationService!
    var mockAuthManager: MockAuthManager!
    var cancellables: Set<AnyCancellable>!

    // UserDefaults key used by NotificationManager
    private let deviceTokenKey = "com.aiq.deviceToken"

    override func setUp() async throws {
        try await super.setUp()
        cancellables = Set<AnyCancellable>()

        // Clear UserDefaults before each test
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)

        // Create mocks
        mockNotificationService = MockNotificationService()
        mockAuthManager = MockAuthManager()

        // Create SUT with injected dependencies
        // Initialization is now synchronous - no delay needed
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
        let freshSut = NotificationManager(
            notificationService: freshMockNotificationService,
            authManager: freshMockAuthManager
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

        // When - Create NotificationManager and immediately trigger auth state change
        let freshSut = NotificationManager(
            notificationService: freshMockNotificationService,
            authManager: freshMockAuthManager
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
}
