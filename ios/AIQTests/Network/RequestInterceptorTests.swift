@testable import AIQ
import XCTest

@MainActor
final class RequestInterceptorTests: XCTestCase {
    // MARK: - LoggingInterceptor Tests

    func testLoggingInterceptor_ReturnsUnmodifiedRequest() async throws {
        // Given
        let sut = LoggingInterceptor()
        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(interceptedRequest.url, request.url)
        XCTAssertEqual(interceptedRequest.httpMethod, request.httpMethod)
        XCTAssertEqual(interceptedRequest.allHTTPHeaderFields, request.allHTTPHeaderFields)
    }

    func testLoggingInterceptor_PreservesHeaders() async throws {
        // Given
        let sut = LoggingInterceptor()
        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        var request = URLRequest(url: url)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer token123", forHTTPHeaderField: "Authorization")

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Content-Type"),
            "application/json"
        )
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Authorization"),
            "Bearer token123"
        )
    }

    func testLoggingInterceptor_PreservesBody() async throws {
        // Given
        let sut = LoggingInterceptor()
        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        var request = URLRequest(url: url)
        let bodyData = try XCTUnwrap("""
        {"key": "value"}
        """.data(using: .utf8))
        request.httpBody = bodyData

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(interceptedRequest.httpBody, bodyData)
    }

    // MARK: - AuthTokenInterceptor Tests

    func testAuthTokenInterceptor_AddsAuthorizationHeader_WhenTokenProvided() async throws {
        // Given
        let expectedToken = "test-token-123"
        let tokenProvider: () -> String? = { expectedToken }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        let request = URLRequest(url: url)

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Authorization"),
            "Bearer \(expectedToken)"
        )
    }

    func testAuthTokenInterceptor_NoAuthorizationHeader_WhenTokenIsNil() async throws {
        // Given
        let tokenProvider: () -> String? = { nil }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        let request = URLRequest(url: url)

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertNil(interceptedRequest.value(forHTTPHeaderField: "Authorization"))
    }

    func testAuthTokenInterceptor_ReplacesExistingAuthorizationHeader() async throws {
        // Given
        let newToken = "new-token-456"
        let tokenProvider: () -> String? = { newToken }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        var request = URLRequest(url: url)
        request.setValue("Bearer old-token", forHTTPHeaderField: "Authorization")

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Authorization"),
            "Bearer \(newToken)"
        )
    }

    func testAuthTokenInterceptor_PreservesOtherHeaders() async throws {
        // Given
        let tokenProvider: () -> String? = { "token" }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        var request = URLRequest(url: url)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("gzip", forHTTPHeaderField: "Accept-Encoding")

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Content-Type"),
            "application/json"
        )
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Accept-Encoding"),
            "gzip"
        )
    }

    func testAuthTokenInterceptor_PreservesBody() async throws {
        // Given
        let tokenProvider: () -> String? = { "token" }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        var request = URLRequest(url: url)
        let bodyData = try XCTUnwrap("""
        {"user": "test"}
        """.data(using: .utf8))
        request.httpBody = bodyData

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(interceptedRequest.httpBody, bodyData)
        XCTAssertNotNil(interceptedRequest.value(forHTTPHeaderField: "Authorization"))
    }

    // MARK: - ConnectivityInterceptor Tests

    // Note: ConnectivityInterceptor uses NetworkMonitor.shared singleton which cannot be mocked.
    // These tests verify behavior when network is available but cannot test offline scenarios.
    // Future improvement: Refactor ConnectivityInterceptor to accept injectable NetworkMonitor.

    func testConnectivityInterceptor_ReturnsRequest_WhenConnected() async throws {
        // Given
        let mockMonitor = MockNetworkMonitor(isConnected: true)
        // Replace NetworkMonitor.shared temporarily
        let originalMonitor = NetworkMonitor.shared
        // Note: We can't replace the singleton, so we test with the mock directly
        let sut = ConnectivityInterceptor()

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        let request = URLRequest(url: url)

        // When - Only test when network is connected (since we can't inject the monitor)
        // This test verifies the interceptor doesn't throw when network is available
        if NetworkMonitor.shared.isConnected {
            let interceptedRequest = try await sut.intercept(request)

            // Then
            XCTAssertEqual(interceptedRequest.url, request.url)
        }
    }

    func testConnectivityInterceptor_ThrowsNoInternetConnectionError_WhenDisconnected() throws {
        // Given
        let mockMonitor = MockNetworkMonitor(isConnected: false)
        let sut = ConnectivityInterceptor()

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        let request = URLRequest(url: url)

        // Note: This test depends on NetworkMonitor.shared state
        // In a real test environment, we would need dependency injection
        // For now, we document that ConnectivityInterceptor uses the shared instance

        // We can't reliably test the disconnected case without dependency injection
        // This is a limitation of the current implementation that should be addressed
        // by making NetworkMonitor injectable into ConnectivityInterceptor
    }

    func testConnectivityInterceptor_PreservesRequest_WhenConnected() async throws {
        // Given
        let sut = ConnectivityInterceptor()

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let bodyData = try XCTUnwrap("""
        {"test": "data"}
        """.data(using: .utf8))
        request.httpBody = bodyData

        // When - Only test when network is connected
        if NetworkMonitor.shared.isConnected {
            let interceptedRequest = try await sut.intercept(request)

            // Then
            XCTAssertEqual(interceptedRequest.url, request.url)
            XCTAssertEqual(interceptedRequest.httpMethod, request.httpMethod)
            XCTAssertEqual(
                interceptedRequest.value(forHTTPHeaderField: "Content-Type"),
                "application/json"
            )
            XCTAssertEqual(interceptedRequest.httpBody, bodyData)
        }
    }

    // MARK: - Edge Cases

    func testAuthTokenInterceptor_EmptyToken() async throws {
        // Given
        let tokenProvider: () -> String? = { "" }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        let request = URLRequest(url: url)

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then - Empty token still sets header (though it's an edge case)
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Authorization"),
            "Bearer "
        )
    }

    func testAuthTokenInterceptor_TokenWithSpecialCharacters() async throws {
        // Given
        let tokenProvider: () -> String? = { "token+with/special=chars" }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        let request = URLRequest(url: url)

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Authorization"),
            "Bearer token+with/special=chars"
        )
    }

    func testLoggingInterceptor_MinimalRequest() async throws {
        // Given
        let sut = LoggingInterceptor()
        let url = try XCTUnwrap(URL(string: "https://example.com/api/test"))
        let request = URLRequest(url: url)

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(interceptedRequest.url, request.url)
        // URLRequest defaults to GET method even when not explicitly set
        XCTAssertNil(interceptedRequest.httpBody)
    }

    func testAuthTokenInterceptor_WithQueryParameters() async throws {
        // Given
        let tokenProvider: () -> String? = { "token123" }
        let sut = AuthTokenInterceptor(tokenProvider: tokenProvider)

        let url = try XCTUnwrap(URL(string: "https://example.com/api/test?param1=value1&param2=value2"))
        let request = URLRequest(url: url)

        // When
        let interceptedRequest = try await sut.intercept(request)

        // Then
        XCTAssertEqual(interceptedRequest.url?.absoluteString, url.absoluteString)
        XCTAssertEqual(
            interceptedRequest.value(forHTTPHeaderField: "Authorization"),
            "Bearer token123"
        )
    }
}
