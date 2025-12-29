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

    func testRegisterDeviceToken_EmptyToken() async throws {
        // Given
        let deviceToken = ""
        let mockResponse = DeviceTokenResponse(
            success: true,
            message: "Device token registered"
        )

        await mockAPIClient.setResponse(mockResponse, for: .notificationRegisterDevice)

        // When
        let response = try await sut.registerDeviceToken(deviceToken)

        // Then - Should still call API (server will validate)
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "Should call API even with empty token")
        XCTAssertTrue(response.success)
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
}
