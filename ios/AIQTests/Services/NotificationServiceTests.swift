import AIQAPIClient
import Combine
import XCTest

@testable import AIQ

/// Tests for NotificationService push notification API operations
///
/// This test suite validates the NotificationService implementation which handles
/// device token registration, unregistration, and notification preference management
/// via the backend API. Tests cover:
/// - Device token registration with success and error scenarios
/// - Device token unregistration
/// - Notification preferences get/update operations
/// - Input validation (empty and whitespace-only tokens)
/// - Thread safety under concurrent operations
/// - Sequential operation flows
/// - Edge cases: long tokens, special characters, unicode, rapid state transitions
final class NotificationServiceTests: XCTestCase {
    var sut: NotificationService!
    var mockService: MockOpenAPIService!

    override func setUp() async throws {
        try await super.setUp()
        mockService = MockOpenAPIService()
        sut = NotificationService(apiService: mockService)
    }

    // MARK: - Register Device Token Tests

    func testRegisterDeviceToken_Success() async throws {
        // Given
        let deviceToken = "test_device_token_123"

        // When
        try await sut.registerDeviceToken(deviceToken)

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        let lastToken = await mockService.lastRegisterDeviceToken

        XCTAssertTrue(registerDeviceCalled, "registerDevice should be called")
        XCTAssertEqual(lastToken, deviceToken, "Should pass correct device token")
    }

    func testRegisterDeviceToken_NetworkError() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        mockService.registerDeviceError = networkError

        // When/Then
        do {
            try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testRegisterDeviceToken_UnauthorizedError() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let unauthorizedError = APIError.unauthorized(message: "Invalid or expired token")

        mockService.registerDeviceError = unauthorizedError

        // When/Then
        do {
            try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testRegisterDeviceToken_ServerError() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let serverError = APIError.serverError(statusCode: 500, message: "Internal server error")

        mockService.registerDeviceError = serverError

        // When/Then
        do {
            try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw server error")
        } catch {
            assertAPIError(error, is: serverError)
        }
    }

    func testRegisterDeviceToken_EmptyToken_ThrowsError() async throws {
        // Given
        let deviceToken = ""

        // When/Then - Should throw NotificationError.emptyDeviceToken before API call
        do {
            try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw emptyDeviceToken error")
        } catch let error as NotificationError {
            XCTAssertEqual(error, .emptyDeviceToken, "Should throw emptyDeviceToken error")
        } catch {
            XCTFail("Should throw NotificationError, got \(error)")
        }

        // Verify API was NOT called
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertFalse(registerDeviceCalled, "Should not call API with empty token")
    }

    func testRegisterDeviceToken_WhitespaceOnlyToken_ThrowsError() async throws {
        // Given
        let deviceToken = "   \n\t  "

        // When/Then - Should throw NotificationError.emptyDeviceToken for whitespace-only tokens
        do {
            try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw emptyDeviceToken error")
        } catch let error as NotificationError {
            XCTAssertEqual(error, .emptyDeviceToken, "Should throw emptyDeviceToken error for whitespace-only token")
        } catch {
            XCTFail("Should throw NotificationError, got \(error)")
        }

        // Verify API was NOT called
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertFalse(registerDeviceCalled, "Should not call API with whitespace-only token")
    }

    // MARK: - Unregister Device Token Tests

    func testUnregisterDeviceToken_Success() async throws {
        // When
        try await sut.unregisterDeviceToken()

        // Then
        let unregisterDeviceCalled = await mockService.unregisterDeviceCalled
        XCTAssertTrue(unregisterDeviceCalled, "unregisterDevice should be called")
    }

    func testUnregisterDeviceToken_NetworkError() async throws {
        // Given
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        mockService.unregisterDeviceError = networkError

        // When/Then
        do {
            try await sut.unregisterDeviceToken()
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testUnregisterDeviceToken_UnauthorizedError() async throws {
        // Given
        let unauthorizedError = APIError.unauthorized(message: "Invalid or expired token")

        mockService.unregisterDeviceError = unauthorizedError

        // When/Then
        do {
            try await sut.unregisterDeviceToken()
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testUnregisterDeviceToken_NotFoundError() async throws {
        // Given
        let notFoundError = APIError.notFound(message: "Device token not found")

        mockService.unregisterDeviceError = notFoundError

        // When/Then
        do {
            try await sut.unregisterDeviceToken()
            XCTFail("Should throw not found error")
        } catch {
            assertAPIError(error, is: notFoundError)
        }
    }

    // MARK: - Update Notification Preferences Tests

    func testUpdateNotificationPreferences_EnableSuccess() async throws {
        // Given
        let enabled = true

        // When
        try await sut.updateNotificationPreferences(enabled: enabled)

        // Then
        let updateNotificationPreferencesCalled = await mockService.updateNotificationPreferencesCalled
        let lastEnabled = await mockService.lastUpdateNotificationPreferencesEnabled

        XCTAssertTrue(updateNotificationPreferencesCalled, "updateNotificationPreferences should be called")
        XCTAssertEqual(lastEnabled, enabled, "Should pass correct enabled value")
    }

    func testUpdateNotificationPreferences_DisableSuccess() async throws {
        // Given
        let enabled = false

        // When
        try await sut.updateNotificationPreferences(enabled: enabled)

        // Then
        let updateNotificationPreferencesCalled = await mockService.updateNotificationPreferencesCalled
        let lastEnabled = await mockService.lastUpdateNotificationPreferencesEnabled

        XCTAssertTrue(updateNotificationPreferencesCalled, "updateNotificationPreferences should be called")
        XCTAssertEqual(lastEnabled, enabled, "Should pass correct enabled value")
    }

    func testUpdateNotificationPreferences_NetworkError() async throws {
        // Given
        let enabled = true
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        mockService.updateNotificationPreferencesError = networkError

        // When/Then
        do {
            try await sut.updateNotificationPreferences(enabled: enabled)
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testUpdateNotificationPreferences_UnauthorizedError() async throws {
        // Given
        let enabled = true
        let unauthorizedError = APIError.unauthorized(message: "Invalid or expired token")

        mockService.updateNotificationPreferencesError = unauthorizedError

        // When/Then
        do {
            try await sut.updateNotificationPreferences(enabled: enabled)
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testUpdateNotificationPreferences_ServerError() async throws {
        // Given
        let enabled = true
        let serverError = APIError.serverError(statusCode: 500, message: "Internal server error")

        mockService.updateNotificationPreferencesError = serverError

        // When/Then
        do {
            try await sut.updateNotificationPreferences(enabled: enabled)
            XCTFail("Should throw server error")
        } catch {
            assertAPIError(error, is: serverError)
        }
    }

    // MARK: - Get Notification Preferences Tests

    func testGetNotificationPreferences_Success_Enabled() async throws {
        // Given
        let mockResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: true)
        mockService.getNotificationPreferencesResponse = mockResponse

        // When
        let result = try await sut.getNotificationPreferences()

        // Then
        let getNotificationPreferencesCalled = await mockService.getNotificationPreferencesCalled
        XCTAssertTrue(getNotificationPreferencesCalled, "getNotificationPreferences should be called")
        XCTAssertTrue(result, "Notifications should be enabled")
    }

    func testGetNotificationPreferences_Success_Disabled() async throws {
        // Given
        let mockResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: false)
        mockService.getNotificationPreferencesResponse = mockResponse

        // When
        let result = try await sut.getNotificationPreferences()

        // Then
        let getNotificationPreferencesCalled = await mockService.getNotificationPreferencesCalled
        XCTAssertTrue(getNotificationPreferencesCalled, "getNotificationPreferences should be called")
        XCTAssertFalse(result, "Notifications should be disabled")
    }

    func testGetNotificationPreferences_NetworkError() async throws {
        // Given
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        mockService.getNotificationPreferencesError = networkError

        // When/Then
        do {
            _ = try await sut.getNotificationPreferences()
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testGetNotificationPreferences_UnauthorizedError() async throws {
        // Given
        let unauthorizedError = APIError.unauthorized(message: "Invalid or expired token")

        mockService.getNotificationPreferencesError = unauthorizedError

        // When/Then
        do {
            _ = try await sut.getNotificationPreferences()
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testGetNotificationPreferences_NotFoundError() async throws {
        // Given
        let notFoundError = APIError.notFound(message: "Preferences not found")

        mockService.getNotificationPreferencesError = notFoundError

        // When/Then
        do {
            _ = try await sut.getNotificationPreferences()
            XCTFail("Should throw not found error")
        } catch {
            assertAPIError(error, is: notFoundError)
        }
    }

    // MARK: - Concurrent Operations Tests

    func testConcurrentRegisterDeviceToken_ThreadSafety() async throws {
        // Given
        let deviceToken = "concurrent_device_token"

        // When - Perform multiple concurrent register operations
        async let register1: Void = sut.registerDeviceToken(deviceToken)
        async let register2: Void = sut.registerDeviceToken(deviceToken)
        async let register3: Void = sut.registerDeviceToken(deviceToken)

        // Then - All should succeed without race conditions
        _ = try await (register1, register2, register3)

        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "registerDevice should be called")
    }

    func testConcurrentUpdatePreferences_ThreadSafety() async throws {
        // When - Perform multiple concurrent update operations
        async let update1: Void = sut.updateNotificationPreferences(enabled: true)
        async let update2: Void = sut.updateNotificationPreferences(enabled: true)
        async let update3: Void = sut.updateNotificationPreferences(enabled: true)

        // Then - All should succeed without race conditions
        _ = try await (update1, update2, update3)

        let updateNotificationPreferencesCalled = await mockService.updateNotificationPreferencesCalled
        XCTAssertTrue(updateNotificationPreferencesCalled, "updateNotificationPreferences should be called")
    }

    func testConcurrentGetPreferences_ThreadSafety() async throws {
        // Given
        let mockResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: true)
        mockService.getNotificationPreferencesResponse = mockResponse

        // When - Perform multiple concurrent get operations
        async let get1 = sut.getNotificationPreferences()
        async let get2 = sut.getNotificationPreferences()
        async let get3 = sut.getNotificationPreferences()

        // Then - All should succeed without race conditions
        let results = try await [get1, get2, get3]

        XCTAssertEqual(results.count, 3, "All concurrent gets should complete")
        for result in results {
            XCTAssertTrue(result, "All results should be true")
        }
    }

    // MARK: - Sequential Operations Tests

    func testRegisterThenUnregister_SequentialSuccess() async throws {
        // Given
        let deviceToken = "test_device_token_123"

        // When - Register device token
        try await sut.registerDeviceToken(deviceToken)

        // Verify register was called
        var registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "registerDevice should be called")

        // Reset the mock to track unregister call
        await mockService.reset()

        // When - Unregister device token
        try await sut.unregisterDeviceToken()

        // Then - Verify unregister was called
        let unregisterDeviceCalled = await mockService.unregisterDeviceCalled
        XCTAssertTrue(unregisterDeviceCalled, "unregisterDevice should be called")
    }

    func testUpdatePreferencesThenGet_SequentialSuccess() async throws {
        // When - Update preferences
        try await sut.updateNotificationPreferences(enabled: true)

        // Verify update was called
        var updateNotificationPreferencesCalled = await mockService.updateNotificationPreferencesCalled
        XCTAssertTrue(updateNotificationPreferencesCalled, "updateNotificationPreferences should be called")

        // Reset the mock and set response for get
        await mockService.reset()
        let getResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: true)
        mockService.getNotificationPreferencesResponse = getResponse

        // When - Get preferences
        let getResult = try await sut.getNotificationPreferences()

        // Then
        XCTAssertTrue(getResult, "Preferences should be enabled")

        let getNotificationPreferencesCalled = await mockService.getNotificationPreferencesCalled
        XCTAssertTrue(getNotificationPreferencesCalled, "getNotificationPreferences should be called")
    }

    // MARK: - Edge Case Tests: Very Long Device Tokens

    func testRegisterDeviceToken_VeryLongToken_Success() async throws {
        // Given - APNs tokens are typically 64 hex characters, but test with an extremely long token
        let veryLongToken = String(repeating: "a", count: 1000)

        // When
        try await sut.registerDeviceToken(veryLongToken)

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        let lastToken = await mockService.lastRegisterDeviceToken

        XCTAssertTrue(registerDeviceCalled, "registerDevice should be called for very long token")
        XCTAssertEqual(lastToken, veryLongToken, "Should pass correct token")
    }

    func testRegisterDeviceToken_MaxLengthToken_Success() async throws {
        // Given - Test with a token at a plausible maximum length (e.g., 4096 characters)
        let maxLengthToken = String(repeating: "f", count: 4096)

        // When
        try await sut.registerDeviceToken(maxLengthToken)

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "Should successfully register max-length token")
    }

    // MARK: - Edge Case Tests: Special Characters in Tokens

    func testRegisterDeviceToken_SpecialCharactersInToken_Success() async throws {
        // Given - Token with various special characters
        let specialCharToken = "token_with-special.chars!@#$%^&*()+={}[]|\\:\";<>,?/"

        // When
        try await sut.registerDeviceToken(specialCharToken)

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "Should successfully register token with special characters")
    }

    func testRegisterDeviceToken_UnicodeCharactersInToken_Success() async throws {
        // Given - Token with unicode characters
        let unicodeToken = "token_with_unicode_🔔_通知_émojis_αβγ"

        // When
        try await sut.registerDeviceToken(unicodeToken)

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "Should successfully register token with unicode characters")
    }

    func testRegisterDeviceToken_NewlinesInToken_Success() async throws {
        // Given - Token with embedded newlines (should still be valid after trimming check)
        let tokenWithNewlines = "token_prefix\ntoken_middle\rtoken_suffix"

        // When
        try await sut.registerDeviceToken(tokenWithNewlines)

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "Should successfully register token with embedded newlines")
    }

    func testRegisterDeviceToken_LeadingTrailingWhitespace_Success() async throws {
        // Given - Token with leading/trailing whitespace (content still present after trim)
        let tokenWithWhitespace = "   valid_token_content   "

        // When
        try await sut.registerDeviceToken(tokenWithWhitespace)

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "Should successfully register token with leading/trailing whitespace")
    }

    // MARK: - Edge Case Tests: Rapid State Transitions

    func testRapidPreferenceToggles_Success() async throws {
        // When - Rapidly toggle preferences multiple times
        for i in 0 ..< 10 {
            let enabled = i % 2 == 0
            try await sut.updateNotificationPreferences(enabled: enabled)
        }

        // Then - All operations should complete
        let updateNotificationPreferencesCalled = await mockService.updateNotificationPreferencesCalled
        XCTAssertTrue(updateNotificationPreferencesCalled, "All rapid toggles should complete")
    }

    func testRapidRegisterUnregisterCycles_Success() async throws {
        // When - Rapidly register/unregister multiple times
        for _ in 0 ..< 5 {
            try await sut.registerDeviceToken("test_token")
            try await sut.unregisterDeviceToken()
        }

        // Then - Verify all operations completed (test passes if no crashes/hangs)
        let registerDeviceCalled = await mockService.registerDeviceCalled
        let unregisterDeviceCalled = await mockService.unregisterDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "registerDevice should be called")
        XCTAssertTrue(unregisterDeviceCalled, "unregisterDevice should be called")
    }

    func testRapidGetPreferencesCalls_Success() async throws {
        // Given
        let mockResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: true)
        mockService.getNotificationPreferencesResponse = mockResponse

        // When - Make many rapid sequential get calls
        var results: [Bool] = []
        for _ in 0 ..< 20 {
            let response = try await sut.getNotificationPreferences()
            results.append(response)
        }

        // Then
        XCTAssertEqual(results.count, 20, "All rapid get calls should complete")
        for result in results {
            XCTAssertTrue(result, "All results should be true")
        }
    }

    // MARK: - Edge Case Tests: Mixed Concurrent Operations

    func testMixedConcurrentOperations_RegisterAndGetPreferences() async throws {
        // Given
        let prefsResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: true)
        mockService.getNotificationPreferencesResponse = prefsResponse

        // When - Perform register and get preferences concurrently
        async let registerResult: Void = sut.registerDeviceToken("concurrent_token")
        async let prefsResult = sut.getNotificationPreferences()

        // Then - Both should succeed
        let (_, prefs) = try await (registerResult, prefsResult)

        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "Registration should succeed")
        XCTAssertTrue(prefs, "Get preferences should succeed")
    }

    func testMixedConcurrentOperations_AllOperationsAtOnce() async throws {
        // Given
        let prefsResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: true)
        mockService.getNotificationPreferencesResponse = prefsResponse

        // When - Perform all four operations concurrently
        async let register: Void = sut.registerDeviceToken("token1")
        async let unregister: Void = sut.unregisterDeviceToken()
        async let updatePrefs: Void = sut.updateNotificationPreferences(enabled: true)
        async let getPrefs = sut.getNotificationPreferences()

        // Then - All should complete without issues
        let (_, _, _, prefsResult) = try await (register, unregister, updatePrefs, getPrefs)

        let registerDeviceCalled = await mockService.registerDeviceCalled
        let unregisterDeviceCalled = await mockService.unregisterDeviceCalled
        let updateNotificationPreferencesCalled = await mockService.updateNotificationPreferencesCalled

        XCTAssertTrue(registerDeviceCalled, "Register should succeed")
        XCTAssertTrue(unregisterDeviceCalled, "Unregister should succeed")
        XCTAssertTrue(updateNotificationPreferencesCalled, "Update preferences should succeed")
        XCTAssertTrue(prefsResult, "Get preferences should succeed")
    }

    func testMixedConcurrentOperations_MultipleTokensSimultaneously() async throws {
        // When - Register multiple different tokens concurrently
        let tokens = ["token_a", "token_b", "token_c", "token_d", "token_e"]

        try await withThrowingTaskGroup(of: Void.self) { group in
            for token in tokens {
                group.addTask {
                    try await self.sut.registerDeviceToken(token)
                }
            }

            try await group.waitForAll()
        }

        // Then
        let registerDeviceCalled = await mockService.registerDeviceCalled
        XCTAssertTrue(registerDeviceCalled, "All concurrent registrations should complete")
    }

    func testMixedConcurrentOperations_UpdateAndGetPreferencesRace() async throws {
        // Given - Test potential race condition between update and get
        let enabledResponse = Components.Schemas.NotificationPreferencesResponse(message: "Success", notificationEnabled: true)
        mockService.getNotificationPreferencesResponse = enabledResponse

        // When - Interleave updates and gets
        var getResults: [Bool] = []

        for i in 0 ..< 5 {
            let shouldEnable = i % 2 == 0

            // Perform update and get concurrently
            async let update: Void = sut.updateNotificationPreferences(enabled: shouldEnable)
            async let get = sut.getNotificationPreferences()

            let (_, getResult) = try await (update, get)
            getResults.append(getResult)
        }

        // Then - All operations should complete
        XCTAssertEqual(getResults.count, 5, "All gets should complete")

        let updateNotificationPreferencesCalled = await mockService.updateNotificationPreferencesCalled
        XCTAssertTrue(updateNotificationPreferencesCalled, "All updates should complete")
    }
}
