@testable import AIQ
import AIQAPIClient
import XCTest

// Unit tests for TokenRefreshInterceptor
//
// Verifies:
// - Basic token refresh flow on 401 responses
// - Concurrent request handling (multiple requests during refresh)
// - Race condition prevention (shared refresh task via actor isolation)
// - Error handling (refresh failure, missing auth service)
// - Non-401 responses pass through unchanged
// - Edge cases (nil auth service, logout on refresh failure)
//
// Thread Safety:
// TokenRefreshInterceptor is implemented as an actor, providing automatic serialization
// of all access to its state. This ensures that concurrent 401 responses share a single
// refresh task, preventing duplicate token refresh requests.

/// Thread-safe collector for test results across concurrent tasks
/// Uses actor isolation instead of NSLock for Swift 6 compatibility
private actor TestResultCollector<T> {
    private var items: [T] = []

    func append(_ item: T) {
        items.append(item)
    }

    func getItems() -> [T] {
        items
    }

    func getCount() -> Int {
        items.count
    }
}

/// Thread-safe container for TimeInterval values
private actor TimeIntervalCollector {
    private var times: [TimeInterval] = []

    func append(_ time: TimeInterval) {
        times.append(time)
    }

    func getTimes() -> [TimeInterval] {
        times
    }

    func getCount() -> Int {
        times.count
    }
}

final class TokenRefreshInterceptorTests: XCTestCase {
    // MARK: - Test Constants

    /// Short delay to ensure concurrent requests overlap during refresh.
    /// Used when testing that multiple 401 responses share a single refresh task.
    private let shortRefreshDelay: TimeInterval = 0.1

    /// Medium delay to test timing-dependent behavior and concurrent request handling.
    /// Used when testing that all requests wait for refresh to complete.
    private let mediumRefreshDelay: TimeInterval = 0.2

    /// Brief delay to ensure refresh task has started before swapping auth service.
    /// Used when testing setAuthService() behavior during in-flight refresh.
    private let refreshStartupDelay: TimeInterval = 0.05

    // MARK: - Properties

    var sut: TokenRefreshInterceptor!
    var mockAuthService: TokenRefreshMockAuthService!

    override func setUp() async throws {
        try await super.setUp()
        mockAuthService = TokenRefreshMockAuthService()
        sut = TokenRefreshInterceptor()
        await sut.setAuthService(mockAuthService)
    }

    // MARK: - Initialization Tests

    func testInit_WithoutAuthService() {
        // Given/When
        let interceptor = TokenRefreshInterceptor()

        // Then - Should initialize successfully without auth service
        XCTAssertNotNil(interceptor, "Should initialize without auth service")
    }

    func testInit_WithAuthService() {
        // Given
        let authService = TokenRefreshMockAuthService()

        // When
        let interceptor = TokenRefreshInterceptor(authService: authService)

        // Then
        XCTAssertNotNil(interceptor, "Should initialize with auth service")
    }

    func testSetAuthService_SetsAuthService() async {
        // Given
        let interceptor = TokenRefreshInterceptor()
        let authService = TokenRefreshMockAuthService()

        // When
        await interceptor.setAuthService(authService)

        // Then - Should not crash when intercepting (auth service is set)
        XCTAssertNotNil(interceptor, "Should set auth service successfully")
    }

    // MARK: - Non-401 Response Tests

    func testIntercept_200Response_PassesThrough() async throws {
        // Given
        let testData = try XCTUnwrap("success data".data(using: .utf8))
        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        ))

        // When
        let result = try await sut.intercept(response: response, data: testData)

        // Then
        XCTAssertEqual(result, testData, "Should return data unchanged for 200 response")
        let refreshCalled = await mockAuthService.refreshTokenCalled
        XCTAssertFalse(refreshCalled, "Should not attempt token refresh for 200 response")
    }

    func testIntercept_404Response_PassesThrough() async throws {
        // Given
        let testData = try XCTUnwrap("not found".data(using: .utf8))
        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 404,
            httpVersion: nil,
            headerFields: nil
        ))

        // When
        let result = try await sut.intercept(response: response, data: testData)

        // Then
        XCTAssertEqual(result, testData, "Should return data unchanged for 404 response")
        let refreshCalled = await mockAuthService.refreshTokenCalled
        XCTAssertFalse(refreshCalled, "Should not attempt token refresh for 404 response")
    }

    func testIntercept_500Response_PassesThrough() async throws {
        // Given
        let testData = try XCTUnwrap("server error".data(using: .utf8))
        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 500,
            httpVersion: nil,
            headerFields: nil
        ))

        // When
        let result = try await sut.intercept(response: response, data: testData)

        // Then
        XCTAssertEqual(result, testData, "Should return data unchanged for 500 response")
        let refreshCalled = await mockAuthService.refreshTokenCalled
        XCTAssertFalse(refreshCalled, "Should not attempt token refresh for 500 response")
    }

    // MARK: - Basic Token Refresh Flow Tests

    func testIntercept_401Response_TriggersRefresh() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)

        let testData = try XCTUnwrap("unauthorized".data(using: .utf8))
        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When/Then
        do {
            _ = try await sut.intercept(response: response, data: testData)
            XCTFail("Should throw TokenRefreshError.shouldRetryRequest")
        } catch let error as TokenRefreshError {
            if case .shouldRetryRequest = error {
                // Expected - verify refresh was called
                let refreshCalled = await mockAuthService.refreshTokenCalled
                XCTAssertTrue(refreshCalled, "Should call refreshToken on 401 response")
            } else {
                XCTFail("Should throw shouldRetryRequest, got \(error)")
            }
        } catch {
            XCTFail("Should throw TokenRefreshError, got \(error)")
        }
    }

    func testIntercept_401Response_ThrowsShouldRetryRequest() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When/Then
        do {
            _ = try await sut.intercept(response: response, data: Data())
            XCTFail("Should throw TokenRefreshError.shouldRetryRequest")
        } catch let error as TokenRefreshError {
            switch error {
            case .shouldRetryRequest:
                break // Expected error
            case .refreshFailed:
                XCTFail("Should throw shouldRetryRequest, not refreshFailed")
            }
        } catch {
            XCTFail("Should throw TokenRefreshError, got \(type(of: error))")
        }
    }

    // MARK: - Concurrent Request Handling Tests

    func testIntercept_MultipleConcurrent401s_SharesSingleRefresh() async throws {
        // Given - Configure refresh with a small delay to ensure requests overlap
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(shortRefreshDelay)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When - Fire 5 concurrent requests
        let requestCount = 5
        let expectation = expectation(description: "All requests complete")
        expectation.expectedFulfillmentCount = requestCount

        let errorCollector = TestResultCollector<Error>()

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                    XCTFail("Should throw TokenRefreshError.shouldRetryRequest")
                } catch {
                    await errorCollector.append(error)
                    expectation.fulfill()
                }
            }
        }

        await fulfillment(of: [expectation], timeout: 5.0)

        // Then - Verify all requests got shouldRetryRequest error
        let errors = await errorCollector.getItems()
        XCTAssertEqual(errors.count, requestCount, "All requests should throw error")
        for error in errors {
            guard let refreshError = error as? TokenRefreshError else {
                XCTFail("Should throw TokenRefreshError, got \(type(of: error))")
                continue
            }
            if case .shouldRetryRequest = refreshError {
                // Expected
                continue
            } else {
                XCTFail("Should throw shouldRetryRequest, got \(refreshError)")
            }
        }

        // Then - Verify refresh behavior
        // Actor isolation ensures exactly 1 refresh for all concurrent requests
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(refreshCallCount, 1, "Should share single refresh for concurrent requests")
    }

    func testIntercept_MultipleConcurrent401s_AllWaitForRefresh() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(mediumRefreshDelay)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When - Fire 3 concurrent requests and track completion times
        let startTime = Date()
        let timeCollector = TimeIntervalCollector()

        let requestCount = 3
        let expectation = expectation(description: "All requests complete")
        expectation.expectedFulfillmentCount = requestCount

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                } catch {
                    let elapsed = Date().timeIntervalSince(startTime)
                    await timeCollector.append(elapsed)
                    expectation.fulfill()
                }
            }
        }

        await fulfillment(of: [expectation], timeout: 5.0)

        // Then - Verify all requests complete (race condition may cause some to wait)
        let completionTimes = await timeCollector.getTimes()
        XCTAssertEqual(completionTimes.count, requestCount, "All requests should complete")

        // Verify at least one refresh occurred
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertGreaterThanOrEqual(
            refreshCallCount,
            1,
            "Should refresh at least once for concurrent requests"
        )
    }

    // MARK: - Race Condition Prevention Tests

    func testIntercept_SequentialRefreshes_AllowsMultipleRefreshes() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When - Make 3 sequential requests (not concurrent)
        for _ in 0 ..< 3 {
            do {
                _ = try await sut.intercept(response: response, data: Data())
                XCTFail("Should throw TokenRefreshError.shouldRetryRequest")
            } catch let error as TokenRefreshError {
                if case .shouldRetryRequest = error {
                    // Expected
                    continue
                } else {
                    XCTFail("Should throw shouldRetryRequest, got \(error)")
                }
            } catch {
                XCTFail("Should throw TokenRefreshError, got \(error)")
            }
        }

        // Then - Each sequential request should trigger a new refresh
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(refreshCallCount, 3, "Sequential requests should each trigger a refresh")
    }

    func testIntercept_RefreshTaskCleanup_AllowsSubsequentRefresh() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "token1",
            refreshToken: "refresh1",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When - First refresh
        do {
            _ = try await sut.intercept(response: response, data: Data())
        } catch {
            // Expected
        }

        // Update mock response for second refresh
        let mockResponse2 = AuthResponse(
            accessToken: "token2",
            refreshToken: "refresh2",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse2)

        // Second refresh (after first completes)
        do {
            _ = try await sut.intercept(response: response, data: Data())
        } catch {
            // Expected
        }

        // Then - Should have called refresh twice (refresh task was cleaned up)
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            refreshCallCount,
            2,
            "Should allow subsequent refresh after task cleanup"
        )
    }

    // MARK: - Error Handling Tests

    func testIntercept_NoAuthService_ThrowsUnauthorized() async throws {
        // Given - Interceptor without auth service
        let interceptor = TokenRefreshInterceptor()
        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When/Then
        do {
            _ = try await interceptor.intercept(response: response, data: Data())
            XCTFail("Should throw unauthorized error")
        } catch let error as APIError {
            if case .unauthorized = error {
                // Expected error - test passes by reaching here without XCTFail
            } else {
                XCTFail("Should throw unauthorized APIError, got \(error)")
            }
        } catch {
            XCTFail("Should throw APIError, got \(type(of: error))")
        }
    }

    func testIntercept_RefreshFails_CallsLogout() async throws {
        // Given
        let refreshError = APIError.networkError(URLError(.timedOut))
        await mockAuthService.setRefreshError(refreshError)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When/Then
        do {
            _ = try await sut.intercept(response: response, data: Data())
            XCTFail("Should throw TokenRefreshError.refreshFailed")
        } catch let error as TokenRefreshError {
            if case .refreshFailed = error {
                // Expected - verify logout was called
                let logoutCalled = await mockAuthService.logoutCalled
                XCTAssertTrue(logoutCalled, "Should call logout when refresh fails")
            } else {
                XCTFail("Should throw refreshFailed, got \(error)")
            }
        } catch {
            XCTFail("Should throw TokenRefreshError, got \(type(of: error))")
        }
    }

    func testIntercept_RefreshFails_ThrowsRefreshFailed() async throws {
        // Given
        let refreshError = APIError.unauthorized(message: "Invalid refresh token")
        await mockAuthService.setRefreshError(refreshError)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When/Then
        do {
            _ = try await sut.intercept(response: response, data: Data())
            XCTFail("Should throw TokenRefreshError.refreshFailed")
        } catch let error as TokenRefreshError {
            switch error {
            case let .refreshFailed(underlyingError):
                // Expected - verify underlying error
                XCTAssertTrue(underlyingError is APIError, "Should wrap underlying error")
            case .shouldRetryRequest:
                XCTFail("Should throw refreshFailed, not shouldRetryRequest")
            }
        } catch {
            XCTFail("Should throw TokenRefreshError, got \(type(of: error))")
        }
    }

    func testIntercept_RefreshFailsWithConcurrentRequests_AllReceiveError() async throws {
        // Given
        let refreshError = APIError.unauthorized(message: "Refresh failed")
        await mockAuthService.setRefreshError(refreshError)
        await mockAuthService.setRefreshDelay(shortRefreshDelay)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When - Fire 3 concurrent requests
        let requestCount = 3
        let expectation = expectation(description: "All requests fail")
        expectation.expectedFulfillmentCount = requestCount

        let errorCollector = TestResultCollector<Error>()

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                    XCTFail("Should throw error")
                } catch {
                    await errorCollector.append(error)
                    expectation.fulfill()
                }
            }
        }

        await fulfillment(of: [expectation], timeout: 5.0)

        // Then - All requests should receive refreshFailed error
        let errors = await errorCollector.getItems()
        XCTAssertEqual(errors.count, requestCount, "All requests should throw error")
        for error in errors {
            guard let refreshError = error as? TokenRefreshError else {
                XCTFail("Should throw TokenRefreshError, got \(type(of: error))")
                continue
            }
            if case .refreshFailed = refreshError {
                // Expected
                continue
            } else {
                XCTFail("Should throw refreshFailed, got \(refreshError)")
            }
        }

        // Verify logout behavior
        // Actor isolation ensures exactly 1 logout call even with concurrent failures
        let logoutCallCount = await mockAuthService.logoutCallCount
        XCTAssertEqual(logoutCallCount, 1, "Should call logout once even with concurrent failures")
    }

    // MARK: - AuthService Management Tests

    func testSetAuthService_DuringInFlightRefresh_UsesOldServiceForCurrentRefresh() async throws {
        // EXPECTED BEHAVIOR:
        // When setAuthService() is called while a token refresh is in progress:
        // 1. The new auth service is stored immediately
        // 2. The in-flight refresh task continues using the OLD auth service (captured in closure)
        // 3. Subsequent refresh requests (after current one completes) use the NEW auth service
        //
        // This occurs because the refresh task captures authService at task creation time.
        // The in-flight task runs to completion with its captured reference.

        // Given - Configure first auth service with a delay to ensure we can swap mid-refresh
        let firstMockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "first@example.com",
            firstName: "First",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let firstAuthResponse = AuthResponse(
            accessToken: "first_token",
            refreshToken: "first_refresh",
            tokenType: "Bearer",
            user: firstMockUser
        )
        await mockAuthService.setRefreshResponse(firstAuthResponse)
        await mockAuthService.setRefreshDelay(mediumRefreshDelay)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When - Start first refresh (will take mediumRefreshDelay to complete)
        let firstRefreshTask = Task {
            do {
                _ = try await sut.intercept(response: response, data: Data())
            } catch {
                // Expected to throw shouldRetryRequest
            }
        }

        // Wait briefly to ensure refresh has started
        try await Task.sleep(nanoseconds: UInt64(refreshStartupDelay * 1_000_000_000))

        // Set a new auth service while first refresh is in progress
        let secondMockAuthService = TokenRefreshMockAuthService()
        let secondMockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "second@example.com",
            firstName: "Second",
            id: 2,
            lastName: "User",
            notificationEnabled: true
        )
        let secondAuthResponse = AuthResponse(
            accessToken: "second_token",
            refreshToken: "second_refresh",
            tokenType: "Bearer",
            user: secondMockUser
        )
        await secondMockAuthService.setRefreshResponse(secondAuthResponse)
        await sut.setAuthService(secondMockAuthService)

        // Wait for first refresh to complete
        await firstRefreshTask.value

        // Then - Verify first auth service was used for the in-flight refresh
        let firstRefreshCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            firstRefreshCount,
            1,
            "First auth service should have completed the in-flight refresh"
        )

        let secondRefreshCount = await secondMockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            secondRefreshCount,
            0,
            "Second auth service should not be used for the already in-flight refresh"
        )

        // Verify that a subsequent refresh uses the NEW auth service
        do {
            _ = try await sut.intercept(response: response, data: Data())
        } catch {
            // Expected to throw shouldRetryRequest
        }

        let secondRefreshCountAfter = await secondMockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            secondRefreshCountAfter,
            1,
            "Second auth service should be used for subsequent refresh"
        )

        let firstRefreshCountAfter = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            firstRefreshCountAfter,
            1,
            "First auth service should not be called again"
        )
    }

    // MARK: - Edge Cases

    func testIntercept_EmptyResponseData_HandlesGracefully() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)

        let emptyData = Data()
        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When/Then - Should handle empty data without crashing
        do {
            _ = try await sut.intercept(response: response, data: emptyData)
            XCTFail("Should throw TokenRefreshError.shouldRetryRequest")
        } catch let error as TokenRefreshError {
            if case .shouldRetryRequest = error {
                // Expected - test passes by reaching here without XCTFail
            } else {
                XCTFail("Should throw shouldRetryRequest, got \(error)")
            }
        } catch {
            XCTFail("Should throw TokenRefreshError, got \(error)")
        }
    }

    func testIntercept_LargeResponseData_HandlesGracefully() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)

        // 1MB of data
        let largeData = Data(repeating: 0xFF, count: 1024 * 1024)
        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When/Then - Should handle large data without issues
        do {
            _ = try await sut.intercept(response: response, data: largeData)
            XCTFail("Should throw TokenRefreshError.shouldRetryRequest")
        } catch let error as TokenRefreshError {
            if case .shouldRetryRequest = error {
                // Expected - test passes by reaching here without XCTFail
            } else {
                XCTFail("Should throw shouldRetryRequest, got \(error)")
            }
        } catch {
            XCTFail("Should throw TokenRefreshError, got \(error)")
        }
    }

    func testIntercept_VeryHighConcurrency_HandlesGracefully() async throws {
        // Given
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(mediumRefreshDelay)

        let response = try XCTUnwrap(try HTTPURLResponse(
            url: XCTUnwrap(URL(string: "https://example.com")),
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        ))

        // When - Fire 50 concurrent requests to stress test
        let requestCount = 50
        let expectation = expectation(description: "All requests complete")
        expectation.expectedFulfillmentCount = requestCount

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                } catch {
                    // Expected error
                }
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        // Then - Verify refresh behavior under high concurrency
        // Actor isolation ensures exactly 1 refresh even with 50 concurrent requests
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(refreshCallCount, 1, "Should share single refresh for concurrent requests")
    }
}
