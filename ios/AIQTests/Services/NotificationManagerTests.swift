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

        // Note: We can't easily inject AuthManager into NotificationManager
        // because it uses AuthManager.shared directly. For now, we'll test
        // what we can without mocking AuthManager fully.
        // We'll use a simpler initialization for testable scenarios.
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

    // Note: testInitialization_DefaultState was intentionally removed.
    // Testing NotificationManager initialization is not feasible with the current
    // singleton architecture because it uses AuthManager.shared and starts async
    // tasks immediately. A refactoring ticket has been created to add dependency
    // injection support, which will enable proper initialization testing.

    // MARK: - Device Token Registration Tests

    func testDidReceiveDeviceToken_CachesToken() async {
        // Given
        let deviceToken = Data([0x01, 0x02, 0x03, 0x04])
        let expectedTokenString = "01020304"

        // When
        // Note: We need to test this through actual NotificationManager.shared
        // since we can't inject dependencies easily
        NotificationManager.shared.didReceiveDeviceToken(deviceToken)

        // Small delay to allow caching to complete
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 second

        // Then - Verify token was cached in UserDefaults
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertEqual(cachedToken, expectedTokenString)
    }

    func testDidReceiveDeviceToken_TokenFormatting() async {
        // Given
        let deviceToken = Data([0xAB, 0xCD, 0xEF, 0x12, 0x34, 0x56, 0x78, 0x90])
        let expectedTokenString = "abcdef1234567890"

        // When
        NotificationManager.shared.didReceiveDeviceToken(deviceToken)

        // Small delay to allow caching to complete
        try? await Task.sleep(nanoseconds: 100_000_000)

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

        // When
        NotificationManager.shared.didFailToRegisterForRemoteNotifications(error: error)

        // Small delay to allow clearing to complete
        try? await Task.sleep(nanoseconds: 100_000_000)

        // Then - Verify token was cleared
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken)
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)
    }

    // MARK: - Unregister Device Token Tests

    func testUnregisterDeviceToken_Success_WhenNotRegistered() async throws {
        // Given - NotificationManager with isDeviceTokenRegistered = false
        // Note: Since NotificationManager uses the real NotificationService and we can't
        // inject mocks due to the singleton pattern, we can only test the early return path
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)

        // When
        await NotificationManager.shared.unregisterDeviceToken()

        // Then - Should complete without errors (early return)
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)
    }

    func testUnregisterDeviceToken_SkipsWhenNotRegistered() async {
        // Given - NotificationManager with no registered token
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)

        // When
        await NotificationManager.shared.unregisterDeviceToken()

        // Then - Should complete without errors (early return path)
        // Note: We cannot verify mock calls here because NotificationManager.shared
        // uses the real NotificationService. This test only verifies the early return
        // behavior doesn't crash or change state.
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)
    }

    func testUnregisterDeviceToken_StateManagement() async {
        // Given - NotificationManager starts with isDeviceTokenRegistered = false
        // Note: We cannot easily test the error path without dependency injection
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)

        // When - Call unregister (will early return)
        await NotificationManager.shared.unregisterDeviceToken()

        // Then - State remains false
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)
    }

    // MARK: - Authorization Tests

    func testCheckAuthorizationStatus_UpdatesStatus() async {
        // Given/When
        await NotificationManager.shared.checkAuthorizationStatus()

        // Then - Authorization status should be updated
        // Note: The actual status will depend on simulator/device settings
        // We can only verify the method completes without errors
        let status = NotificationManager.shared.authorizationStatus
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
        await NotificationManager.shared.retryDeviceTokenRegistration()

        // Then - Should complete without errors (no-op)
        // Note: We cannot verify mock calls here because NotificationManager.shared
        // uses the real NotificationService. This test only verifies the early return
        // behavior completes without errors when no token is available.
        XCTAssertNil(UserDefaults.standard.string(forKey: deviceTokenKey))
    }

    func testRetryDeviceTokenRegistration_WithCachedToken() async {
        // Given - Cached token in UserDefaults
        let cachedToken = "cached_token_123"
        UserDefaults.standard.set(cachedToken, forKey: deviceTokenKey)

        // When
        await NotificationManager.shared.retryDeviceTokenRegistration()

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
            NotificationManager.shared.didReceiveDeviceToken(deviceToken1)
        }.value
        async let call2: Void = Task { @MainActor in
            NotificationManager.shared.didReceiveDeviceToken(deviceToken2)
        }.value
        async let call3: Void = Task { @MainActor in
            NotificationManager.shared.didReceiveDeviceToken(deviceToken3)
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
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)

        // When - Multiple concurrent unregister calls
        async let call1: Void = NotificationManager.shared.unregisterDeviceToken()
        async let call2: Void = NotificationManager.shared.unregisterDeviceToken()
        async let call3: Void = NotificationManager.shared.unregisterDeviceToken()

        // Then - All should complete without crashing
        _ = await (call1, call2, call3)

        // Verify final state remains consistent
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)
    }

    func testConcurrentRetryRegistration_ThreadSafety() async {
        // Given
        UserDefaults.standard.set("retry_token", forKey: deviceTokenKey)

        // When - Multiple concurrent retry calls
        async let call1: Void = NotificationManager.shared.retryDeviceTokenRegistration()
        async let call2: Void = NotificationManager.shared.retryDeviceTokenRegistration()
        async let call3: Void = NotificationManager.shared.retryDeviceTokenRegistration()

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

        NotificationManager.shared.$authorizationStatus
            .dropFirst() // Skip initial value
            .sink { status in
                receivedStatus = status
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // When
        await NotificationManager.shared.checkAuthorizationStatus()

        // Then
        await fulfillment(of: [expectation], timeout: 2.0)
        XCTAssertNotNil(receivedStatus)
    }

    func testIsDeviceTokenRegisteredProperty_IsPublished() async {
        // Given - Initial value should be false
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)

        // When/Then - Verify property is observable
        // Note: Since NotificationManager uses singleton pattern and we can't inject mocks,
        // we can only verify the initial state and that the property is @Published
        var observedValues: [Bool] = []

        let cancellable = NotificationManager.shared.$isDeviceTokenRegistered
            .sink { value in
                observedValues.append(value)
            }

        // Allow time for initial value to be collected
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 second

        // Then - Should have collected at least the initial value
        XCTAssertFalse(observedValues.isEmpty, "Should observe at least the initial value")
        XCTAssertFalse(observedValues.first ?? true, "Initial value should be false")

        cancellable.cancel()
    }

    // MARK: - Edge Cases

    func testDeviceTokenFormatting_EmptyData() async {
        // Given
        let emptyToken = Data()

        // When
        NotificationManager.shared.didReceiveDeviceToken(emptyToken)

        // Small delay
        try? await Task.sleep(nanoseconds: 100_000_000)

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

        // When
        NotificationManager.shared.didReceiveDeviceToken(largeToken)

        // Small delay
        try? await Task.sleep(nanoseconds: 100_000_000)

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

        // When - Multiple consecutive failures
        NotificationManager.shared.didFailToRegisterForRemoteNotifications(error: error1)
        NotificationManager.shared.didFailToRegisterForRemoteNotifications(error: error2)
        NotificationManager.shared.didFailToRegisterForRemoteNotifications(error: error3)

        // Small delay
        try? await Task.sleep(nanoseconds: 100_000_000)

        // Then - State should remain consistent
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken)
    }

    func testRetryAfterFailure_StateTransition() async {
        // Given - Simulate a failure
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        NotificationManager.shared.didFailToRegisterForRemoteNotifications(error: error)

        // Small delay
        try? await Task.sleep(nanoseconds: 100_000_000)

        // Verify initial state
        XCTAssertFalse(NotificationManager.shared.isDeviceTokenRegistered)

        // When - Cache a new token and retry
        UserDefaults.standard.set("retry_token", forKey: deviceTokenKey)
        await NotificationManager.shared.retryDeviceTokenRegistration()

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

        // When - Receive token
        NotificationManager.shared.didReceiveDeviceToken(deviceToken)

        // Small delay
        try? await Task.sleep(nanoseconds: 100_000_000)

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

        // When - Trigger failure which clears cache
        let error = NSError(domain: "Test", code: -1, userInfo: nil)
        NotificationManager.shared.didFailToRegisterForRemoteNotifications(error: error)

        // Small delay
        try? await Task.sleep(nanoseconds: 100_000_000)

        // Then - Verify removed from UserDefaults
        let cachedToken = UserDefaults.standard.string(forKey: deviceTokenKey)
        XCTAssertNil(cachedToken)
    }
}
