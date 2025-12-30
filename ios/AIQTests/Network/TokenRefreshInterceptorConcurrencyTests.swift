@testable import AIQ
import XCTest

/// Concurrency stress tests for TokenRefreshInterceptor
///
/// This test suite focuses on high-concurrency scenarios to verify that the actor-based
/// implementation correctly handles race conditions and ensures thread-safety.
///
/// See Also: BTS-55 - Create concurrency stress tests for TokenRefreshInterceptor
///
/// Key Tests:
/// - 10+ concurrent requests triggering 401s
/// - Single token refresh during concurrent requests
/// - No race condition errors
/// - All requests succeed (receive shouldRetryRequest error)
///
/// Thread Safety:
/// TokenRefreshInterceptor is implemented as an actor, providing automatic serialization
/// of all state access. These stress tests verify that this actor isolation prevents
/// race conditions even under extreme concurrency.

/// Thread-safe counter for collecting test results across concurrent tasks
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

/// Thread-safe counter for tracking counts across concurrent tasks
private actor Counter {
    private var value: Int = 0

    func increment() {
        value += 1
    }

    func getValue() -> Int {
        value
    }
}

final class TokenRefreshInterceptorConcurrencyTests: XCTestCase {
    var sut: TokenRefreshInterceptor!
    var mockAuthService: TokenRefreshMockAuthService!

    override func setUp() async throws {
        try await super.setUp()
        mockAuthService = TokenRefreshMockAuthService()
        sut = TokenRefreshInterceptor()
        await sut.setAuthService(mockAuthService)
    }

    override func tearDown() {
        sut = nil
        mockAuthService = nil
        super.tearDown()
    }

    // MARK: - Stress Tests (10+ Concurrent Requests)

    /// BTS-55: Test that 10+ concurrent 401 responses share a single token refresh
    func testStress_TenConcurrent401s_SharesSingleRefresh() async throws {
        // Given - Configure successful refresh with delay to ensure overlap
        let mockUser = createMockUser()
        let mockResponse = AuthResponse(
            accessToken: "new_token",
            refreshToken: "new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(0.2) // 200ms delay to ensure all 10 overlap

        let response = create401Response()

        // When - Fire 10 concurrent requests
        let requestCount = 10
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
        XCTAssertEqual(errors.count, requestCount, "All 10 requests should complete")
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

        // Then - Verify only one refresh occurred (BTS-55 requirement)
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            refreshCallCount,
            1,
            "BTS-55: Should share single refresh for 10 concurrent requests"
        )
    }

    /// BTS-55: Test that 20 concurrent 401 responses share a single token refresh
    func testStress_TwentyConcurrent401s_SharesSingleRefresh() async throws {
        // Given
        let mockUser = createMockUser()
        let mockResponse = AuthResponse(
            accessToken: "new_token_20",
            refreshToken: "new_refresh_20",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(0.3) // Longer delay for more requests

        let response = create401Response()

        // When - Fire 20 concurrent requests
        let requestCount = 20
        let expectation = expectation(description: "All 20 requests complete")
        expectation.expectedFulfillmentCount = requestCount

        let successCounter = Counter()

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                } catch let error as TokenRefreshError {
                    if case .shouldRetryRequest = error {
                        await successCounter.increment()
                    }
                } catch {
                    // Unexpected error
                }
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        // Then - Verify all requests completed successfully
        let successCount = await successCounter.getValue()
        XCTAssertEqual(
            successCount,
            requestCount,
            "BTS-55: All 20 requests should succeed with shouldRetryRequest"
        )

        // Then - Verify only one refresh occurred
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            refreshCallCount,
            1,
            "BTS-55: Should share single refresh for 20 concurrent requests"
        )
    }

    /// BTS-55: Test extreme concurrency (50 requests) to verify no race conditions
    func testStress_FiftyConcurrent401s_NoRaceConditions() async throws {
        // Given
        let mockUser = createMockUser()
        let mockResponse = AuthResponse(
            accessToken: "new_token_50",
            refreshToken: "new_refresh_50",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(0.3) // Delay to maximize overlap

        let response = create401Response()

        // When - Fire 50 concurrent requests to stress test
        let requestCount = 50
        let expectation = expectation(description: "All 50 requests complete")
        expectation.expectedFulfillmentCount = requestCount

        let completedCounter = Counter()
        let raceConditionCounter = Counter()

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                    // Should not succeed without error
                } catch let error as TokenRefreshError {
                    await completedCounter.increment()
                } catch {
                    // Any other error indicates a race condition
                    await raceConditionCounter.increment()
                }
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 15.0)

        // Then - Verify no race condition errors (BTS-55 requirement)
        let raceConditionErrors = await raceConditionCounter.getValue()
        XCTAssertEqual(
            raceConditionErrors,
            0,
            "BTS-55: Should have no race condition errors with 50 concurrent requests"
        )

        // Then - Verify all requests completed
        let completedCount = await completedCounter.getValue()
        XCTAssertEqual(
            completedCount,
            requestCount,
            "BTS-55: All 50 requests should complete successfully"
        )

        // Then - Verify only one refresh occurred
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            refreshCallCount,
            1,
            "BTS-55: Should share single refresh even with 50 concurrent requests"
        )
    }

    /// BTS-55: Test that all concurrent requests receive the new token (via shouldRetryRequest)
    func testStress_ConcurrentRequests_AllReceiveNewToken() async throws {
        // Given
        let mockUser = createMockUser()
        let mockResponse = AuthResponse(
            accessToken: "brand_new_token",
            refreshToken: "brand_new_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(0.2)

        let response = create401Response()

        // When - Fire 15 concurrent requests
        let requestCount = 15
        let expectation = expectation(description: "All 15 requests complete")
        expectation.expectedFulfillmentCount = requestCount

        let shouldRetryCounter = Counter()

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                    XCTFail("Should throw shouldRetryRequest")
                } catch let error as TokenRefreshError {
                    if case .shouldRetryRequest = error {
                        // This error signals the client should retry with new token
                        await shouldRetryCounter.increment()
                    }
                } catch {
                    // Unexpected error
                }
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        // Then - Verify all requests received shouldRetryRequest (BTS-55 requirement)
        let shouldRetryCount = await shouldRetryCounter.getValue()
        XCTAssertEqual(
            shouldRetryCount,
            requestCount,
            "BTS-55: All requests should receive shouldRetryRequest to retry with new token"
        )

        // Then - Verify single refresh
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(refreshCallCount, 1, "Should only refresh once")
    }

    // MARK: - Error Handling Under Concurrency

    /// BTS-55: Test that refresh failures are safely propagated to all concurrent requests
    func testStress_ConcurrentRequestsWithRefreshFailure_AllReceiveError() async throws {
        // Given
        let refreshError = APIError.unauthorized(message: "Invalid refresh token")
        await mockAuthService.setRefreshError(refreshError)
        await mockAuthService.setRefreshDelay(0.2) // Delay to ensure overlap

        let response = create401Response()

        // When - Fire 12 concurrent requests
        let requestCount = 12
        let expectation = expectation(description: "All requests fail gracefully")
        expectation.expectedFulfillmentCount = requestCount

        let refreshFailedCounter = Counter()
        let unexpectedErrorsCounter = Counter()

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                    XCTFail("Should throw error")
                } catch let error as TokenRefreshError {
                    if case .refreshFailed = error {
                        await refreshFailedCounter.increment()
                    }
                } catch {
                    await unexpectedErrorsCounter.increment()
                }
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        // Then - Verify all requests received refreshFailed error
        let refreshFailedCount = await refreshFailedCounter.getValue()
        XCTAssertEqual(
            refreshFailedCount,
            requestCount,
            "BTS-55: All requests should receive refreshFailed error"
        )

        let unexpectedErrors = await unexpectedErrorsCounter.getValue()
        XCTAssertEqual(unexpectedErrors, 0, "Should have no unexpected errors")

        // Then - Verify logout was called once (not 12 times)
        let logoutCallCount = await mockAuthService.logoutCallCount
        XCTAssertEqual(
            logoutCallCount,
            1,
            "BTS-55: Should call logout once even with 12 concurrent failures"
        )
    }

    // MARK: - Sequential vs Concurrent Behavior

    /// BTS-55: Test that sequential requests trigger separate refreshes (baseline comparison)
    func testStress_SequentialRequests_AllowMultipleRefreshes() async throws {
        // Given
        let mockUser = createMockUser()
        let mockResponse = AuthResponse(
            accessToken: "sequential_token",
            refreshToken: "sequential_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)

        let response = create401Response()

        // When - Make 10 sequential requests (not concurrent)
        for _ in 0 ..< 10 {
            do {
                _ = try await sut.intercept(response: response, data: Data())
            } catch {
                // Expected error
            }
        }

        // Then - Each sequential request should trigger a new refresh
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            refreshCallCount,
            10,
            "Sequential requests should each trigger a refresh (not share a task)"
        )
    }

    /// BTS-55: Test mixed concurrent and sequential requests
    func testStress_MixedConcurrentAndSequential_CorrectRefreshCounts() async throws {
        // Given
        let mockUser = createMockUser()
        let mockResponse = AuthResponse(
            accessToken: "mixed_token",
            refreshToken: "mixed_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(0.2)

        let response = create401Response()

        // When - First batch: 10 concurrent requests
        let firstBatchCount = 10
        let firstExpectation = expectation(description: "First batch completes")
        firstExpectation.expectedFulfillmentCount = firstBatchCount

        for _ in 0 ..< firstBatchCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                } catch {
                    // Expected
                }
                firstExpectation.fulfill()
            }
        }

        await fulfillment(of: [firstExpectation], timeout: 5.0)

        // When - Second batch: 10 more concurrent requests (after first batch completes)
        let secondBatchCount = 10
        let secondExpectation = expectation(description: "Second batch completes")
        secondExpectation.expectedFulfillmentCount = secondBatchCount

        for _ in 0 ..< secondBatchCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                } catch {
                    // Expected
                }
                secondExpectation.fulfill()
            }
        }

        await fulfillment(of: [secondExpectation], timeout: 5.0)

        // Then - Should have 2 refreshes (one per batch)
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(
            refreshCallCount,
            2,
            "Should have 2 refreshes (one per concurrent batch)"
        )
    }

    // MARK: - Performance Under Stress

    /// BTS-55: Test that high concurrency completes in reasonable time
    func testStress_HighConcurrency_CompletesInReasonableTime() async throws {
        // Given
        let mockUser = createMockUser()
        let mockResponse = AuthResponse(
            accessToken: "perf_token",
            refreshToken: "perf_refresh",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAuthService.setRefreshResponse(mockResponse)
        await mockAuthService.setRefreshDelay(0.1) // 100ms refresh time

        let response = create401Response()
        let requestCount = 30

        // When - Measure time for 30 concurrent requests
        let startTime = Date()
        let expectation = expectation(description: "All requests complete")
        expectation.expectedFulfillmentCount = requestCount

        for _ in 0 ..< requestCount {
            Task {
                do {
                    _ = try await sut.intercept(response: response, data: Data())
                } catch {
                    // Expected
                }
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 10.0)
        let elapsedTime = Date().timeIntervalSince(startTime)

        // Then - Should complete in reasonable time
        // With proper sharing, should take ~100ms (one refresh) + overhead
        // Without sharing, would take 30 * 100ms = 3000ms
        XCTAssertLessThan(
            elapsedTime,
            1.0,
            "BTS-55: 30 concurrent requests should complete quickly (shared refresh)"
        )

        // Verify single refresh
        let refreshCallCount = await mockAuthService.refreshTokenCallCount
        XCTAssertEqual(refreshCallCount, 1, "Should share single refresh")
    }

    // MARK: - Helper Methods

    private func createMockUser() -> User {
        User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
    }

    private func create401Response() -> HTTPURLResponse {
        HTTPURLResponse(
            url: URL(string: "https://api.example.com/test")!,
            statusCode: 401,
            httpVersion: nil,
            headerFields: nil
        )!
    }
}
