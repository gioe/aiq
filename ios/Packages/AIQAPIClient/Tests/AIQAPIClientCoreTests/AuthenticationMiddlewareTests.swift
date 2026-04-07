@testable import AIQAPIClientCore
import Foundation
import HTTPTypes
import OpenAPIRuntime
import XCTest

// MARK: - AuthenticationMiddlewareTests

//
// VERIFIED: AuthenticationMiddleware is declared as `actor`, so all concurrent
// property accesses (accessToken, refreshToken) are serialized by the actor's
// executor. Async tests are valid here and correctly model real usage.

final class AuthenticationMiddlewareTests: XCTestCase {
    // MARK: - Helpers

    private func makeRequest(path: String = "/v1/test") -> HTTPRequest {
        HTTPRequest(method: .get, scheme: nil, authority: nil, path: path)
    }

    private func makeBaseURL() -> URL {
        URL(string: "https://api.example.com")!
    }

    // MARK: - Tests

    func testRefreshTokenSentToRefreshEndpoint() async throws {
        // Given
        let accessToken = "access-abc"
        let refreshToken = "refresh-xyz"
        let middleware = AuthenticationMiddleware(
            accessToken: accessToken,
            refreshToken: refreshToken
        )
        let baseURL = makeBaseURL()
        let request = makeRequest(path: "/v1/auth/refresh")
        // Use a class-based box so the @Sendable closure can capture and mutate it
        // without triggering Swift 6 sendable-capture warnings on a local var.
        let box = CaptureBox<HTTPRequest>()

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "refresh_access_token_v1_auth_refresh_post"
        ) { req, _, _ in
            box.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Then — the refresh token, not the access token, must be in Authorization
        let authHeader = box.value?.headerFields[.authorization]
        XCTAssertEqual(authHeader, "Bearer \(refreshToken)")
        XCTAssertNotEqual(authHeader, "Bearer \(accessToken)")
    }

    func testAccessTokenSentToOtherEndpoints() async throws {
        // Given
        let accessToken = "access-abc"
        let refreshToken = "refresh-xyz"
        let middleware = AuthenticationMiddleware(
            accessToken: accessToken,
            refreshToken: refreshToken
        )
        let baseURL = makeBaseURL()
        let request = makeRequest(path: "/v1/users/me")
        let box = CaptureBox<HTTPRequest>()

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_user_v1_users_get"
        ) { req, _, _ in
            box.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Then — the access token must be used for non-refresh endpoints
        XCTAssertEqual(box.value?.headerFields[.authorization], "Bearer \(accessToken)")
    }

    func testClearTokensRemovesBothTokens() async throws {
        // Given — tokens set then cleared
        let middleware = AuthenticationMiddleware(
            accessToken: "access-abc",
            refreshToken: "refresh-xyz"
        )
        await middleware.clearTokens()

        let baseURL = makeBaseURL()
        let request = makeRequest(path: "/v1/users/me")
        let box = CaptureBox<HTTPRequest>()

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_user_v1_users_get"
        ) { req, _, _ in
            box.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Then — no Authorization header after clearing tokens
        XCTAssertNil(box.value?.headerFields[.authorization])
    }

    func testNoAuthHeaderWhenNoTokenSet() async throws {
        // Given — middleware created with no tokens
        let middleware = AuthenticationMiddleware()
        let baseURL = makeBaseURL()
        let request = makeRequest(path: "/v1/users/me")
        let box = CaptureBox<HTTPRequest>()

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_user_v1_users_get"
        ) { req, _, _ in
            box.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Then
        XCTAssertNil(box.value?.headerFields[.authorization])
    }

    func testSetTokensSetsAccessTokenHeader() async throws {
        // Given — middleware starts with no tokens, then setTokens is called
        let accessToken = "access-new"
        let refreshToken = "refresh-new"
        let middleware = AuthenticationMiddleware()
        await middleware.setTokens(accessToken: accessToken, refreshToken: refreshToken)

        let baseURL = makeBaseURL()
        let regularBox = CaptureBox<HTTPRequest>()
        let refreshBox = CaptureBox<HTTPRequest>()

        // When — non-refresh endpoint
        _ = try await middleware.intercept(
            makeRequest(path: "/v1/users/me"),
            body: nil,
            baseURL: baseURL,
            operationID: "get_user_v1_users_get"
        ) { req, _, _ in
            regularBox.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // When — refresh endpoint
        _ = try await middleware.intercept(
            makeRequest(path: "/v1/auth/refresh"),
            body: nil,
            baseURL: baseURL,
            operationID: "refresh_access_token_v1_auth_refresh_post"
        ) { req, _, _ in
            refreshBox.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Then — both tokens set by setTokens are used for their respective endpoints
        XCTAssertEqual(regularBox.value?.headerFields[.authorization], "Bearer \(accessToken)")
        XCTAssertEqual(refreshBox.value?.headerFields[.authorization], "Bearer \(refreshToken)")
    }

    func testSetAccessTokenNilClearsAccessHeader() async throws {
        // Given — middleware has tokens, then access token is cleared
        let middleware = AuthenticationMiddleware(
            accessToken: "access-abc",
            refreshToken: "refresh-xyz"
        )
        await middleware.setAccessToken(nil)

        let baseURL = makeBaseURL()
        let request = makeRequest(path: "/v1/users/me")
        let box = CaptureBox<HTTPRequest>()

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "get_user_v1_users_get"
        ) { req, _, _ in
            box.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Then — no Authorization header after clearing access token
        XCTAssertNil(box.value?.headerFields[.authorization])
    }

    func testSetRefreshTokenUpdatesRefreshEndpointToken() async throws {
        // Given — middleware has tokens, then refresh token is replaced
        let newRefreshToken = "refresh-updated"
        let middleware = AuthenticationMiddleware(
            accessToken: "access-abc",
            refreshToken: "refresh-old"
        )
        await middleware.setRefreshToken(newRefreshToken)

        let baseURL = makeBaseURL()
        let request = makeRequest(path: "/v1/auth/refresh")
        let box = CaptureBox<HTTPRequest>()

        // When
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: baseURL,
            operationID: "refresh_access_token_v1_auth_refresh_post"
        ) { req, _, _ in
            box.value = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Then — the new refresh token is used for the refresh endpoint
        XCTAssertEqual(box.value?.headerFields[.authorization], "Bearer \(newRefreshToken)")
    }
}

// MARK: - CaptureBox

/// A reference-type wrapper that allows `@Sendable` closures to store a captured
/// value without requiring `inout` (which cannot be captured by escaping closures)
/// or triggering Swift 6 sendable-capture warnings on mutable local variables.
///
/// Safety: `@unchecked Sendable` is safe here because XCTest async tests execute
/// on a single cooperative thread — the write (inside the `next` closure) always
/// completes before the `await` returns, so the subsequent read in the test body
/// is always sequenced after it with no concurrent access.
private final class CaptureBox<T>: @unchecked Sendable {
    var value: T?
}
