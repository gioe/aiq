@testable import AIQAPIClient
import Foundation
import HTTPTypes
import OpenAPIRuntime
import Testing

@Suite("AuthenticationMiddleware Tests")
struct AuthenticationMiddlewareTests {
    // MARK: - Token Injection Tests

    @Test("Injects access token into regular requests")
    func injectsAccessTokenForRegularRequests() async throws {
        let middleware = AuthenticationMiddleware(accessToken: "test-access-token")
        var capturedRequest: HTTPRequest?

        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/users/me")

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "get_current_user_v1_users_me_get"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == "Bearer test-access-token")
    }

    @Test("No token injected when access token is nil")
    func noTokenWhenAccessTokenNil() async throws {
        let middleware = AuthenticationMiddleware()
        var capturedRequest: HTTPRequest?

        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/users/me")

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "get_current_user_v1_users_me_get"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == nil)
    }

    // MARK: - Refresh Token Tests

    @Test("Injects refresh token for refresh endpoint")
    func injectsRefreshTokenForRefreshEndpoint() async throws {
        let middleware = AuthenticationMiddleware(
            accessToken: "test-access-token",
            refreshToken: "test-refresh-token"
        )
        var capturedRequest: HTTPRequest?

        let request = HTTPRequest(
            method: .post,
            scheme: "https",
            authority: "api.example.com",
            path: "/v1/auth/refresh"
        )

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "refresh_access_token_v1_auth_refresh_post"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == "Bearer test-refresh-token")
    }

    @Test("Uses access token for non-refresh endpoints even when refresh token available")
    func usesAccessTokenForNonRefreshEndpoints() async throws {
        let middleware = AuthenticationMiddleware(
            accessToken: "test-access-token",
            refreshToken: "test-refresh-token"
        )
        var capturedRequest: HTTPRequest?

        let request = HTTPRequest(
            method: .get,
            scheme: "https",
            authority: "api.example.com",
            path: "/v1/users/me"
        )

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "get_current_user_v1_users_me_get"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == "Bearer test-access-token")
    }

    @Test("Uses access token for refresh endpoint when no refresh token available")
    func usesAccessTokenWhenNoRefreshToken() async throws {
        let middleware = AuthenticationMiddleware(accessToken: "test-access-token")
        var capturedRequest: HTTPRequest?

        let request = HTTPRequest(
            method: .post,
            scheme: "https",
            authority: "api.example.com",
            path: "/v1/auth/refresh"
        )

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "refresh_access_token_v1_auth_refresh_post"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        // When refresh token is nil but access token is set, it falls back to access token
        #expect(capturedRequest?.headerFields[.authorization] == "Bearer test-access-token")
    }

    // MARK: - Token Management Tests

    @Test("setAccessToken updates the token")
    func setAccessTokenUpdatesToken() async throws {
        let middleware = AuthenticationMiddleware()
        var capturedRequest: HTTPRequest?

        // First request - no token
        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == nil)

        // Set token
        await middleware.setAccessToken("new-token")

        // Second request - with token
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == "Bearer new-token")
    }

    @Test("setTokens sets both tokens")
    func setTokensSetsBoth() async {
        let middleware = AuthenticationMiddleware()

        await middleware.setTokens(accessToken: "access", refreshToken: "refresh")

        let hasToken = await middleware.hasAccessToken
        #expect(hasToken == true)

        let token = await middleware.getAccessToken()
        #expect(token == "access")
    }

    @Test("setRefreshToken updates the refresh token independently")
    func setRefreshTokenUpdatesRefreshToken() async throws {
        let middleware = AuthenticationMiddleware(accessToken: "access")

        await middleware.setRefreshToken("refresh")

        // Verify refresh token is used for refresh endpoint
        let request = HTTPRequest(
            method: .post,
            scheme: "https",
            authority: "api.example.com",
            path: "/v1/auth/refresh"
        )
        var capturedRequest: HTTPRequest?

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "refresh_access_token_v1_auth_refresh_post"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == "Bearer refresh")
    }

    @Test("clearTokens removes both tokens and prevents header injection")
    func clearTokensRemovesBoth() async throws {
        let middleware = AuthenticationMiddleware(
            accessToken: "access",
            refreshToken: "refresh"
        )

        await middleware.clearTokens()

        let hasToken = await middleware.hasAccessToken
        #expect(hasToken == false)

        let token = await middleware.getAccessToken()
        #expect(token == nil)

        // Verify no token is injected after clearing
        var capturedRequest: HTTPRequest?
        let request = HTTPRequest(
            method: .get,
            scheme: "https",
            authority: "api.example.com",
            path: "/v1/test"
        )
        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        #expect(capturedRequest?.headerFields[.authorization] == nil)
    }

    @Test("hasAccessToken returns correct value")
    func hasAccessTokenReturnsCorrectValue() async {
        let middlewareWithToken = AuthenticationMiddleware(accessToken: "token")
        let middlewareWithoutToken = AuthenticationMiddleware()

        let hasToken = await middlewareWithToken.hasAccessToken
        let noToken = await middlewareWithoutToken.hasAccessToken

        #expect(hasToken == true)
        #expect(noToken == false)
    }

    // MARK: - Thread Safety Tests

    @Test("Concurrent token updates are thread-safe")
    func concurrentTokenUpdatesAreThreadSafe() async {
        let middleware = AuthenticationMiddleware()

        // Perform many concurrent token updates
        await withTaskGroup(of: Void.self) { group in
            for iteration in 0 ..< 100 {
                group.addTask {
                    await middleware.setAccessToken("token-\(iteration)")
                }
            }
        }

        // After all updates, hasAccessToken should still work correctly
        let hasToken = await middleware.hasAccessToken
        #expect(hasToken == true)
    }

    @Test("Concurrent requests with token updates are thread-safe")
    func concurrentRequestsWithTokenUpdatesAreThreadSafe() async {
        let middleware = AuthenticationMiddleware(accessToken: "initial-token")

        await withTaskGroup(of: Void.self) { group in
            // Add concurrent requests
            for _ in 0 ..< 50 {
                group.addTask {
                    let request = HTTPRequest(
                        method: .get,
                        scheme: "https",
                        authority: "api.example.com",
                        path: "/test"
                    )
                    _ = try? await middleware.intercept(
                        request,
                        body: nil,
                        baseURL: URL(string: "https://api.example.com")!,
                        operationID: "test"
                    ) { _, _, _ in
                        (HTTPResponse(status: .ok), nil)
                    }
                }
            }

            // Add concurrent token updates
            for iteration in 0 ..< 50 {
                group.addTask {
                    await middleware.setAccessToken("token-\(iteration)")
                }
            }
        }

        // Should complete without crashes or data races
        let hasToken = await middleware.hasAccessToken
        #expect(hasToken == true)
    }
}
