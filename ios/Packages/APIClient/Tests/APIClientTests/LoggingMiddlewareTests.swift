import APIClient
import Foundation
import HTTPTypes
import OpenAPIRuntime
import XCTest

// MARK: - LoggingMiddlewareTests

//
// LoggingMiddleware is a public struct and Sendable; regular import is sufficient.
// These tests focus on behavioral contracts: pass-through correctness and the
// URL construction logic identified as a must_fix in the PR review.

final class LoggingMiddlewareTests: XCTestCase {
    // MARK: - Helpers

    private func makeBaseURL() -> URL {
        URL(string: "https://api.example.com")!
    }

    // MARK: - Pass-through tests

    func testInterceptPassesThroughRequestIntact() async throws {
        // Given
        let middleware = LoggingMiddleware(logLevel: .info)
        let baseURL = makeBaseURL()
        let request = HTTPRequest(method: .get, scheme: nil, authority: nil, path: "/v1/users/me")
        var capturedMethod: HTTPRequest.Method?
        var capturedPath: String?

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_user_v1_users_get"
        ) { req, _, _ in
            capturedMethod = req.method
            capturedPath = req.path
            return (HTTPResponse(status: .ok), nil)
        }

        // Then — middleware must not mutate the request
        XCTAssertEqual(capturedMethod, .get)
        XCTAssertEqual(capturedPath, "/v1/users/me")
    }

    func testInterceptPassesThroughResponseIntact() async throws {
        // Given
        let middleware = LoggingMiddleware(logLevel: .info)
        let baseURL = makeBaseURL()
        let request = HTTPRequest(method: .get, scheme: nil, authority: nil, path: "/v1/users/me")

        // When
        let (response, body) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_user_v1_users_get"
        ) { _, _, _ in
            (HTTPResponse(status: .created), nil)
        }

        // Then — the exact response from `next` must be returned unmodified
        XCTAssertEqual(response.status, .created)
        XCTAssertNil(body)
    }

    // MARK: - URL construction test (must_fix from PR review)

    /// Validates the URL construction logic used inside LoggingMiddleware:
    ///   URL(string: request.path ?? "", relativeTo: baseURL)?.absoluteURL
    /// This must preserve query parameters so logs show the full URL.
    func testURLConstructionWithQueryParams() async throws {
        // Given — a path that includes query parameters
        let path = "/v1/users?limit=10&offset=0"
        let baseURL = makeBaseURL()

        // When — apply the same construction logic the middleware uses
        let constructedURL = URL(string: path, relativeTo: baseURL)?.absoluteURL

        // Then — query parameters must survive the URL construction
        XCTAssertNotNil(constructedURL, "URL construction should not return nil for a valid path")
        XCTAssertEqual(
            constructedURL?.query,
            "limit=10&offset=0",
            "Query parameters must be preserved in the constructed URL"
        )
        XCTAssertEqual(
            constructedURL?.path,
            "/v1/users",
            "Path must be preserved in the constructed URL"
        )

        // Also verify the middleware itself does not break when the path contains query params
        let middleware = LoggingMiddleware(logLevel: .info)
        let request = HTTPRequest(method: .get, scheme: nil, authority: nil, path: path)
        var nextWasCalled = false

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "list_users"
        ) { _, _, _ in
            nextWasCalled = true
            return (HTTPResponse(status: .ok), nil)
        }

        XCTAssertTrue(nextWasCalled, "next must be called even when path contains query parameters")
    }

    // MARK: - Log level tests

    func testInterceptWithLogLevelNoneSkipsLoggingButCallsNext() async throws {
        // Given — .none level means no logging; next must still be called
        let middleware = LoggingMiddleware(logLevel: .none)
        let baseURL = makeBaseURL()
        let request = HTTPRequest(method: .post, scheme: nil, authority: nil, path: "/v1/auth/login")
        var nextWasCalled = false

        // When
        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "login_v1_auth_login_post"
        ) { _, _, _ in
            nextWasCalled = true
            return (HTTPResponse(status: .ok), nil)
        }

        // Then
        XCTAssertTrue(nextWasCalled, "next must be called regardless of log level")
        XCTAssertEqual(response.status, .ok)
    }

    func testInterceptWithLogLevelDebugCallsNext() async throws {
        // Given
        let middleware = LoggingMiddleware(logLevel: .debug)
        let baseURL = makeBaseURL()
        let request = HTTPRequest(method: .get, scheme: nil, authority: nil, path: "/v1/health")
        var nextWasCalled = false

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "health_check_v1_health_get"
        ) { _, _, _ in
            nextWasCalled = true
            return (HTTPResponse(status: .ok), nil)
        }

        // Then
        XCTAssertTrue(nextWasCalled)
    }

    // MARK: - Error propagation test

    func testInterceptRethrowsErrorsFromNext() async throws {
        // Given
        let middleware = LoggingMiddleware(logLevel: .error)
        let baseURL = makeBaseURL()
        let request = HTTPRequest(method: .get, scheme: nil, authority: nil, path: "/v1/users/me")

        struct NetworkError: Error {}

        // When / Then
        do {
            _ = try await middleware.intercept(
                request,
                body: nil,
                baseURL: baseURL,
                operationID: "get_user_v1_users_get"
            ) { _, _, _ in
                throw NetworkError()
            }
            XCTFail("Expected an error to be thrown")
        } catch is NetworkError {
            // Success — error was correctly propagated
        }
    }
}
