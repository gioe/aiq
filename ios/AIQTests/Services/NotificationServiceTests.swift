import Combine
import XCTest

@testable import AIQ

final class NotificationServiceTests: XCTestCase {
    var sut: NotificationService!
    var mockAPIClient: MockAPIClient!

    override func setUp() async throws {
        try await super.setUp()
        mockAPIClient = MockAPIClient()
        sut = NotificationService(apiClient: mockAPIClient)
    }

    override func tearDown() {
        sut = nil
        mockAPIClient = nil
        super.tearDown()
    }

    // MARK: - Register Device Token Tests

    func testRegisterDeviceToken_Success() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(deviceToken)

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .notificationRegisterDevice, "Should call notificationRegisterDevice endpoint")
        XCTAssertEqual(lastMethod, .post, "Should use POST method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for device token registration")
        XCTAssertTrue(response.success, "Response should indicate success")
        XCTAssertEqual(response.message, "Device token registered successfully")
    }

    func testRegisterDeviceToken_NetworkError() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        await mockAPIClient.setMockError(networkError)

        // When/Then
        do {
            _ = try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testRegisterDeviceToken_UnauthorizedError() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let unauthorizedError = APIError.unauthorized(message: "Invalid or expired token")

        await mockAPIClient.setMockError(unauthorizedError)

        // When/Then
        do {
            _ = try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testRegisterDeviceToken_ServerError() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let serverError = APIError.serverError(statusCode: 500, message: "Internal server error")

        await mockAPIClient.setMockError(serverError)

        // When/Then
        do {
            _ = try await sut.registerDeviceToken(deviceToken)
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
            _ = try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw emptyDeviceToken error")
        } catch let error as NotificationError {
            XCTAssertEqual(error, .emptyDeviceToken, "Should throw emptyDeviceToken error")
        } catch {
            XCTFail("Should throw NotificationError, got \(error)")
        }

        // Verify API was NOT called
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertFalse(requestCalled, "Should not call API with empty token")
    }

    func testRegisterDeviceToken_WhitespaceOnlyToken_ThrowsError() async throws {
        // Given
        let deviceToken = "   \n\t  "

        // When/Then - Should throw NotificationError.emptyDeviceToken for whitespace-only tokens
        do {
            _ = try await sut.registerDeviceToken(deviceToken)
            XCTFail("Should throw emptyDeviceToken error")
        } catch let error as NotificationError {
            XCTAssertEqual(error, .emptyDeviceToken, "Should throw emptyDeviceToken error for whitespace-only token")
        } catch {
            XCTFail("Should throw NotificationError, got \(error)")
        }

        // Verify API was NOT called
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertFalse(requestCalled, "Should not call API with whitespace-only token")
    }

    // MARK: - Unregister Device Token Tests

    func testUnregisterDeviceToken_Success() async throws {
        // Given
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token unregistered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.unregisterDeviceToken()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .notificationRegisterDevice, "Should call notificationRegisterDevice endpoint")
        XCTAssertEqual(lastMethod, .delete, "Should use DELETE method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for device token unregistration")
        XCTAssertTrue(response.success, "Response should indicate success")
        XCTAssertEqual(response.message, "Device token unregistered successfully")
    }

    func testUnregisterDeviceToken_NetworkError() async throws {
        // Given
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        await mockAPIClient.setMockError(networkError)

        // When/Then
        do {
            _ = try await sut.unregisterDeviceToken()
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testUnregisterDeviceToken_UnauthorizedError() async throws {
        // Given
        let unauthorizedError = APIError.unauthorized(message: "Invalid or expired token")

        await mockAPIClient.setMockError(unauthorizedError)

        // When/Then
        do {
            _ = try await sut.unregisterDeviceToken()
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testUnregisterDeviceToken_NotFoundError() async throws {
        // Given
        let notFoundError = APIError.notFound(message: "Device token not found")

        await mockAPIClient.setMockError(notFoundError)

        // When/Then
        do {
            _ = try await sut.unregisterDeviceToken()
            XCTFail("Should throw not found error")
        } catch {
            assertAPIError(error, is: notFoundError)
        }
    }

    // MARK: - Update Notification Preferences Tests

    func testUpdateNotificationPreferences_EnableSuccess() async throws {
        // Given
        let enabled = true
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Notification preferences updated"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationPreferences)

        // When
        let response = try await sut.updateNotificationPreferences(enabled: enabled)

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .notificationPreferences, "Should call notificationPreferences endpoint")
        XCTAssertEqual(lastMethod, .put, "Should use PUT method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for updating preferences")
        XCTAssertTrue(response.notificationEnabled, "Notifications should be enabled")
        XCTAssertEqual(response.message, "Notification preferences updated")
    }

    func testUpdateNotificationPreferences_DisableSuccess() async throws {
        // Given
        let enabled = false
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Notification preferences updated"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationPreferences)

        // When
        let response = try await sut.updateNotificationPreferences(enabled: enabled)

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .notificationPreferences, "Should call notificationPreferences endpoint")
        XCTAssertEqual(lastMethod, .put, "Should use PUT method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for updating preferences")
        XCTAssertFalse(response.notificationEnabled, "Notifications should be disabled")
        XCTAssertEqual(response.message, "Notification preferences updated")
    }

    func testUpdateNotificationPreferences_NetworkError() async throws {
        // Given
        let enabled = true
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        await mockAPIClient.setMockError(networkError)

        // When/Then
        do {
            _ = try await sut.updateNotificationPreferences(enabled: enabled)
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testUpdateNotificationPreferences_UnauthorizedError() async throws {
        // Given
        let enabled = true
        let unauthorizedError = APIError.unauthorized(message: "Invalid or expired token")

        await mockAPIClient.setMockError(unauthorizedError)

        // When/Then
        do {
            _ = try await sut.updateNotificationPreferences(enabled: enabled)
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testUpdateNotificationPreferences_ServerError() async throws {
        // Given
        let enabled = true
        let serverError = APIError.serverError(statusCode: 500, message: "Internal server error")

        await mockAPIClient.setMockError(serverError)

        // When/Then
        do {
            _ = try await sut.updateNotificationPreferences(enabled: enabled)
            XCTFail("Should throw server error")
        } catch {
            assertAPIError(error, is: serverError)
        }
    }

    // MARK: - Get Notification Preferences Tests

    func testGetNotificationPreferences_Success_Enabled() async throws {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Preferences retrieved successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationPreferences)

        // When
        let response = try await sut.getNotificationPreferences()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .notificationPreferences, "Should call notificationPreferences endpoint")
        XCTAssertEqual(lastMethod, .get, "Should use GET method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for getting preferences")
        XCTAssertTrue(response.notificationEnabled, "Notifications should be enabled")
        XCTAssertEqual(response.message, "Preferences retrieved successfully")
    }

    func testGetNotificationPreferences_Success_Disabled() async throws {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Preferences retrieved successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationPreferences)

        // When
        let response = try await sut.getNotificationPreferences()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .notificationPreferences, "Should call notificationPreferences endpoint")
        XCTAssertEqual(lastMethod, .get, "Should use GET method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for getting preferences")
        XCTAssertFalse(response.notificationEnabled, "Notifications should be disabled")
        XCTAssertEqual(response.message, "Preferences retrieved successfully")
    }

    func testGetNotificationPreferences_NetworkError() async throws {
        // Given
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        await mockAPIClient.setMockError(networkError)

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

        await mockAPIClient.setMockError(unauthorizedError)

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

        await mockAPIClient.setMockError(notFoundError)

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
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When - Perform multiple concurrent register operations
        async let register1 = sut.registerDeviceToken(deviceToken)
        async let register2 = sut.registerDeviceToken(deviceToken)
        async let register3 = sut.registerDeviceToken(deviceToken)

        // Then - All should succeed without race conditions
        let results = try await [register1, register2, register3]

        XCTAssertEqual(results.count, 3, "All concurrent registrations should complete")
        for result in results {
            XCTAssertTrue(result.success)
        }
    }

    func testConcurrentUpdatePreferences_ThreadSafety() async throws {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Notification preferences updated"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationPreferences)

        // When - Perform multiple concurrent update operations
        async let update1 = sut.updateNotificationPreferences(enabled: true)
        async let update2 = sut.updateNotificationPreferences(enabled: true)
        async let update3 = sut.updateNotificationPreferences(enabled: true)

        // Then - All should succeed without race conditions
        let results = try await [update1, update2, update3]

        XCTAssertEqual(results.count, 3, "All concurrent updates should complete")
        for result in results {
            XCTAssertTrue(result.notificationEnabled)
        }
    }

    func testConcurrentGetPreferences_ThreadSafety() async throws {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Preferences retrieved successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationPreferences)

        // When - Perform multiple concurrent get operations
        async let get1 = sut.getNotificationPreferences()
        async let get2 = sut.getNotificationPreferences()
        async let get3 = sut.getNotificationPreferences()

        // Then - All should succeed without race conditions
        let results = try await [get1, get2, get3]

        XCTAssertEqual(results.count, 3, "All concurrent gets should complete")
        for result in results {
            XCTAssertTrue(result.notificationEnabled)
        }
    }

    // MARK: - Sequential Operations Tests

    func testRegisterThenUnregister_SequentialSuccess() async throws {
        // Given
        let deviceToken = "test_device_token_123"
        let registerResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )
        let unregisterResponse = DeviceTokenResponse(
            success: true,
            message: "Device token unregistered successfully"
        )

        await mockAPIClient.setResponse(registerResponse, for: .notificationRegisterDevice)

        // When - Register device token
        let registerResult = try await sut.registerDeviceToken(deviceToken)
        XCTAssertTrue(registerResult.success)

        // Verify first call was POST
        let firstMethod = await mockAPIClient.lastMethod
        XCTAssertEqual(firstMethod, .post, "First call should be POST for registration")

        // When - Unregister device token (response is same endpoint, just different method)
        await mockAPIClient.setResponse(unregisterResponse, for: .notificationRegisterDevice)
        let unregisterResult = try await sut.unregisterDeviceToken()

        // Then
        XCTAssertTrue(unregisterResult.success)

        // Verify second call was DELETE
        let secondMethod = await mockAPIClient.lastMethod
        XCTAssertEqual(secondMethod, .delete, "Second call should be DELETE for unregistration")
    }

    func testUpdatePreferencesThenGet_SequentialSuccess() async throws {
        // Given
        let updateResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Notification preferences updated"
        )
        let getResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Preferences retrieved successfully"
        )

        await mockAPIClient.setResponse(updateResponse, for: .notificationPreferences)

        // When - Update preferences
        let updateResult = try await sut.updateNotificationPreferences(enabled: true)
        XCTAssertTrue(updateResult.notificationEnabled)

        // Verify first call was PUT
        let firstMethod = await mockAPIClient.lastMethod
        XCTAssertEqual(firstMethod, .put, "First call should be PUT for update")

        // When - Get preferences (response is same endpoint, just different method)
        await mockAPIClient.setResponse(getResponse, for: .notificationPreferences)
        let getResult = try await sut.getNotificationPreferences()

        // Then
        XCTAssertTrue(getResult.notificationEnabled)

        // Verify second call was GET
        let secondMethod = await mockAPIClient.lastMethod
        XCTAssertEqual(secondMethod, .get, "Second call should be GET for retrieval")
    }

    // MARK: - Edge Case Tests: Very Long Device Tokens

    func testRegisterDeviceToken_VeryLongToken_Success() async throws {
        // Given - APNs tokens are typically 64 hex characters, but test with an extremely long token
        let veryLongToken = String(repeating: "a", count: 1000)
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(veryLongToken)

        // Then
        XCTAssertTrue(response.success, "Should successfully register very long token")

        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "API request should be called for very long token")
    }

    func testRegisterDeviceToken_MaxLengthToken_Success() async throws {
        // Given - Test with a token at a plausible maximum length (e.g., 4096 characters)
        let maxLengthToken = String(repeating: "f", count: 4096)
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(maxLengthToken)

        // Then
        XCTAssertTrue(response.success, "Should successfully register max-length token")
    }

    // MARK: - Edge Case Tests: Special Characters in Tokens

    func testRegisterDeviceToken_SpecialCharactersInToken_Success() async throws {
        // Given - Token with various special characters
        let specialCharToken = "token_with-special.chars!@#$%^&*()+={}[]|\\:\";<>,?/"
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(specialCharToken)

        // Then
        XCTAssertTrue(response.success, "Should successfully register token with special characters")

        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "API request should be called")
    }

    func testRegisterDeviceToken_UnicodeCharactersInToken_Success() async throws {
        // Given - Token with unicode characters
        let unicodeToken = "token_with_unicode_🔔_通知_émojis_αβγ"
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(unicodeToken)

        // Then
        XCTAssertTrue(response.success, "Should successfully register token with unicode characters")
    }

    func testRegisterDeviceToken_NewlinesInToken_Success() async throws {
        // Given - Token with embedded newlines (should still be valid after trimming check)
        let tokenWithNewlines = "token_prefix\ntoken_middle\rtoken_suffix"
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(tokenWithNewlines)

        // Then
        XCTAssertTrue(response.success, "Should successfully register token with embedded newlines")
    }

    func testRegisterDeviceToken_LeadingTrailingWhitespace_Success() async throws {
        // Given - Token with leading/trailing whitespace (content still present after trim)
        let tokenWithWhitespace = "   valid_token_content   "
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered successfully"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(tokenWithWhitespace)

        // Then
        XCTAssertTrue(response.success, "Should successfully register token with leading/trailing whitespace")

        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "API request should be called when token has non-whitespace content")
    }

    // MARK: - Edge Case Tests: Rapid State Transitions

    func testRapidPreferenceToggles_Success() async throws {
        // Given
        let enabledResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Enabled"
        )
        let disabledResponse = NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Disabled"
        )

        // When - Rapidly toggle preferences multiple times
        var results: [Bool] = []

        for i in 0 ..< 10 {
            let enabled = i % 2 == 0
            if enabled {
                await mockAPIClient.setResponse(enabledResponse, for: .notificationPreferences)
            } else {
                await mockAPIClient.setResponse(disabledResponse, for: .notificationPreferences)
            }

            let response = try await sut.updateNotificationPreferences(enabled: enabled)
            results.append(response.notificationEnabled)
        }

        // Then
        XCTAssertEqual(results.count, 10, "All rapid toggles should complete")
        for (index, result) in results.enumerated() {
            let expectedEnabled = index % 2 == 0
            XCTAssertEqual(result, expectedEnabled, "Toggle \(index) should have correct state")
        }
    }

    func testRapidRegisterUnregisterCycles_Success() async throws {
        // Given
        let registerResponse = DeviceTokenResponse(
            success: true,
            message: "Registered"
        )
        let unregisterResponse = DeviceTokenResponse(
            success: true,
            message: "Unregistered"
        )

        // When - Rapidly register/unregister multiple times
        for _ in 0 ..< 5 {
            await mockAPIClient.setResponse(registerResponse, for: .notificationRegisterDevice)
            let regResult = try await sut.registerDeviceToken("test_token")
            XCTAssertTrue(regResult.success)

            await mockAPIClient.setResponse(unregisterResponse, for: .notificationRegisterDevice)
            let unregResult = try await sut.unregisterDeviceToken()
            XCTAssertTrue(unregResult.success)
        }

        // Then - Verify all operations completed (test passes if no crashes/hangs)
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled)
    }

    func testRapidGetPreferencesCalls_Success() async throws {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Retrieved"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationPreferences)

        // When - Make many rapid sequential get calls
        var results: [NotificationPreferencesResponse] = []
        for _ in 0 ..< 20 {
            let response = try await sut.getNotificationPreferences()
            results.append(response)
        }

        // Then
        XCTAssertEqual(results.count, 20, "All rapid get calls should complete")
        for result in results {
            XCTAssertTrue(result.notificationEnabled)
        }
    }

    // MARK: - Edge Case Tests: Mixed Concurrent Operations

    func testMixedConcurrentOperations_RegisterAndGetPreferences() async throws {
        // Given
        let tokenResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered"
        )
        let prefsResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Preferences retrieved"
        )

        await mockAPIClient.setResponse(tokenResponse, for: .notificationRegisterDevice)
        await mockAPIClient.setResponse(prefsResponse, for: .notificationPreferences)

        // When - Perform register and get preferences concurrently
        async let registerResult = sut.registerDeviceToken("concurrent_token")
        async let prefsResult = sut.getNotificationPreferences()

        // Then - Both should succeed
        let (register, prefs) = try await (registerResult, prefsResult)

        XCTAssertTrue(register.success, "Registration should succeed")
        XCTAssertTrue(prefs.notificationEnabled, "Get preferences should succeed")
    }

    func testMixedConcurrentOperations_AllOperationsAtOnce() async throws {
        // Given
        let tokenResponse = DeviceTokenResponse(
            success: true,
            message: "Token operation succeeded"
        )
        let prefsResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Preferences operation succeeded"
        )

        await mockAPIClient.setResponse(tokenResponse, for: .notificationRegisterDevice)
        await mockAPIClient.setResponse(prefsResponse, for: .notificationPreferences)

        // When - Perform all four operations concurrently
        async let register = sut.registerDeviceToken("token1")
        async let unregister = sut.unregisterDeviceToken()
        async let updatePrefs = sut.updateNotificationPreferences(enabled: true)
        async let getPrefs = sut.getNotificationPreferences()

        // Then - All should complete without issues
        let results = try await (register, unregister, updatePrefs, getPrefs)

        XCTAssertTrue(results.0.success, "Register should succeed")
        XCTAssertTrue(results.1.success, "Unregister should succeed")
        XCTAssertTrue(results.2.notificationEnabled, "Update preferences should succeed")
        XCTAssertTrue(results.3.notificationEnabled, "Get preferences should succeed")
    }

    func testMixedConcurrentOperations_MultipleTokensSimultaneously() async throws {
        // Given
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When - Register multiple different tokens concurrently
        let tokens = ["token_a", "token_b", "token_c", "token_d", "token_e"]

        let results = try await withThrowingTaskGroup(of: DeviceTokenResponse.self) { group in
            for token in tokens {
                group.addTask {
                    try await self.sut.registerDeviceToken(token)
                }
            }

            var responses: [DeviceTokenResponse] = []
            for try await response in group {
                responses.append(response)
            }
            return responses
        }

        // Then
        XCTAssertEqual(results.count, 5, "All concurrent registrations should complete")
        for result in results {
            XCTAssertTrue(result.success)
        }
    }

    func testMixedConcurrentOperations_UpdateAndGetPreferencesRace() async throws {
        // Given - Test potential race condition between update and get
        let enabledResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Enabled"
        )
        let disabledResponse = NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Disabled"
        )

        // When - Interleave updates and gets
        var updateResults: [Bool] = []
        var getResults: [Bool] = []

        for i in 0 ..< 5 {
            let shouldEnable = i % 2 == 0

            if shouldEnable {
                await mockAPIClient.setResponse(enabledResponse, for: .notificationPreferences)
            } else {
                await mockAPIClient.setResponse(disabledResponse, for: .notificationPreferences)
            }

            // Perform update and get concurrently
            async let update = sut.updateNotificationPreferences(enabled: shouldEnable)
            async let get = sut.getNotificationPreferences()

            let (updateResult, getResult) = try await (update, get)
            updateResults.append(updateResult.notificationEnabled)
            getResults.append(getResult.notificationEnabled)
        }

        // Then - All operations should complete
        XCTAssertEqual(updateResults.count, 5, "All updates should complete")
        XCTAssertEqual(getResults.count, 5, "All gets should complete")
    }
}
