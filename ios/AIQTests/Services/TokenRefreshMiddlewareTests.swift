@testable import AIQ
import HTTPTypes
import OpenAPIRuntime
import XCTest

// MARK: - Helpers

/// Thread-safe call counter for use in `@Sendable` test closures.
private actor CallCounter {
    private(set) var value = 0

    /// Atomically increments and returns the new value.
    @discardableResult
    func increment() -> Int {
        value += 1
        return value
    }
}

/// Blocks async callers until `unblock()` is called, then allows all waiters to proceed.
private actor Blocker {
    private var waiters: [CheckedContinuation<Void, Never>] = []
    private var isUnblocked = false

    func wait() async {
        guard !isUnblocked else { return }
        await withCheckedContinuation { cont in
            waiters.append(cont)
        }
    }

    func unblock() {
        isUnblocked = true
        waiters.forEach { $0.resume() }
        waiters = []
    }
}

// MARK: - Tests

final class TokenRefreshMiddlewareTests: XCTestCase {
    private let baseURL = URL(string: "https://example.com")!

    private func makeRequest(path: String = "/api/data") -> HTTPRequest {
        HTTPRequest(method: .get, url: URL(string: "https://example.com\(path)")!)
    }

    // MARK: - 401 Retry Path

    /// A 401 response should trigger exactly one refresh and then retry the original request.
    func testIntercept_401Response_TriggersRefreshAndRetry() async throws {
        // Arrange
        let refreshCounter = CallCounter()
        let nextCounter = CallCounter()
        let middleware = TokenRefreshMiddleware {
            await refreshCounter.increment()
        }

        let request = makeRequest()
        let next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?) = { _, _, _ in
            let n = await nextCounter.increment()
            // First call returns 401; retry returns 200.
            return n == 1
                ? (HTTPResponse(status: .unauthorized), nil)
                : (HTTPResponse(status: .ok), nil)
        }

        // Act
        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_data",
            next: next
        )

        // Assert
        let refreshCount = await refreshCounter.value
        let nextCount = await nextCounter.value
        XCTAssertEqual(response.status, .ok, "Retry should return the second (200) response")
        XCTAssertEqual(refreshCount, 1, "Refresh handler should be called exactly once")
        XCTAssertEqual(nextCount, 2, "next() should be called twice: initial request + retry")
    }

    // MARK: - Non-401 Pass-through

    /// A successful response should be returned directly without touching the refresh handler.
    func testIntercept_SuccessResponse_PassesThroughWithoutRefresh() async throws {
        // Arrange
        let refreshCounter = CallCounter()
        let middleware = TokenRefreshMiddleware {
            await refreshCounter.increment()
        }

        let request = makeRequest()

        // Act
        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_data",
            next: { _, _, _ in (HTTPResponse(status: .ok), nil) }
        )

        // Assert
        let refreshCount = await refreshCounter.value
        XCTAssertEqual(response.status, .ok)
        XCTAssertEqual(refreshCount, 0, "Refresh should not be called for non-401 responses")
    }

    // MARK: - Concurrent Refresh Coalescing

    /// Multiple concurrent 401 responses should coalesce into a single refresh call.
    ///
    /// The test holds the refresh handler open via a `Blocker` so that both concurrent requests
    /// can pile up on the same in-flight refresh `Task` before it completes.  After the blocker
    /// is released both requests retry independently and should both succeed.
    func testIntercept_Concurrent401s_CoalescesRefreshToSingleCall() async throws {
        // Arrange
        let refreshCounter = CallCounter()
        let nextCounter = CallCounter()
        let blocker = Blocker()

        let middleware = TokenRefreshMiddleware {
            await refreshCounter.increment()
            // Hold the refresh open so the second concurrent request sees the in-flight Task.
            await blocker.wait()
        }

        let request = makeRequest()

        // Calls 1 and 2 are the two concurrent initial requests, both returning 401.
        // Calls 3 and 4 are the retries after the refresh completes, both returning 200.
        let next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?) = { _, _, _ in
            let n = await nextCounter.increment()
            return n <= 2
                ? (HTTPResponse(status: .unauthorized), nil)
                : (HTTPResponse(status: .ok), nil)
        }

        // Act: launch two concurrent intercept calls
        async let result1 = middleware.intercept(
            request, body: nil, baseURL: baseURL, operationID: "op_a", next: next
        )
        async let result2 = middleware.intercept(
            request, body: nil, baseURL: baseURL, operationID: "op_b", next: next
        )

        // Give both tasks time to reach the blocked refresh handler before releasing it.
        try await Task.sleep(nanoseconds: 150_000_000) // 150 ms
        await blocker.unblock()

        let ((r1, _), (r2, _)) = try await (result1, result2)

        // Assert
        let refreshCount = await refreshCounter.value
        XCTAssertEqual(r1.status, .ok)
        XCTAssertEqual(r2.status, .ok)
        XCTAssertEqual(refreshCount, 1, "Concurrent 401s should trigger exactly one refresh, not two")
    }

    // MARK: - Reentrancy Guard

    /// A 401 from the refresh endpoint itself must throw `APIError.unauthorized` immediately
    /// without invoking the refresh handler (to prevent an infinite refresh loop).
    func testIntercept_401FromRefreshEndpoint_ThrowsUnauthorizedWithoutRefreshing() async throws {
        // Arrange
        let refreshCounter = CallCounter()
        let middleware = TokenRefreshMiddleware {
            await refreshCounter.increment()
        }

        let request = makeRequest(path: "/v1/auth/refresh")
        // Operation ID matches the constant inside TokenRefreshMiddleware.
        let refreshOperationID = "refresh_access_token_v1_auth_refresh_post"

        // Act & Assert
        do {
            _ = try await middleware.intercept(
                request,
                body: nil,
                baseURL: baseURL,
                operationID: refreshOperationID,
                next: { _, _, _ in (HTTPResponse(status: .unauthorized), nil) }
            )
            XCTFail("Expected APIError.unauthorized to be thrown")
        } catch let error as APIError {
            if case .unauthorized = error {
                // Expected — reentrancy guard fired correctly.
            } else {
                XCTFail("Expected APIError.unauthorized, got \(error)")
            }
        }

        let refreshCount = await refreshCounter.value
        XCTAssertEqual(
            refreshCount,
            0,
            "Refresh handler must not be called when the refresh endpoint itself returns 401"
        )
    }
}
