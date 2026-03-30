import Foundation
import HTTPTypes
import OpenAPIRuntime

/// A middleware that adds authentication tokens to outgoing requests.
///
/// This middleware injects Bearer tokens into request headers for authenticated endpoints.
/// It supports both access tokens (for regular requests) and refresh tokens (for token refresh).
///
/// ## Usage
/// ```swift
/// let authMiddleware = AuthenticationMiddleware()
/// let client = Client(
///     serverURL: serverURL,
///     transport: URLSessionTransport(),
///     middlewares: [authMiddleware]
/// )
///
/// // Set the access token after login
/// await authMiddleware.setAccessToken("eyJhbG...")
/// ```
public actor AuthenticationMiddleware: ClientMiddleware {
    /// The current access token, if any
    private var accessToken: String?

    /// The current refresh token, if any (used only for token refresh endpoint)
    private var refreshToken: String?

    /// Creates a new authentication middleware
    /// - Parameters:
    ///   - accessToken: Initial access token (optional)
    ///   - refreshToken: Initial refresh token (optional)
    public init(accessToken: String? = nil, refreshToken: String? = nil) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
    }

    /// Sets the access token for authenticated requests
    /// - Parameter token: The JWT access token, or nil to clear
    public func setAccessToken(_ token: String?) {
        accessToken = token
    }

    /// Sets the refresh token for token refresh operations
    /// - Parameter token: The JWT refresh token, or nil to clear
    public func setRefreshToken(_ token: String?) {
        refreshToken = token
    }

    /// Sets both tokens at once (convenience method for login/register responses)
    /// - Parameters:
    ///   - accessToken: The JWT access token
    ///   - refreshToken: The JWT refresh token
    public func setTokens(accessToken: String, refreshToken: String) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
    }

    /// Clears both tokens (for logout)
    public func clearTokens() {
        accessToken = nil
        refreshToken = nil
    }

    /// Whether the middleware has a valid access token
    public var hasAccessToken: Bool {
        accessToken != nil
    }

    /// The current access token (for external access if needed)
    public func getAccessToken() -> String? {
        accessToken
    }

    // MARK: - ClientMiddleware

    public func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        var modifiedRequest = request

        // Check if this is the token refresh endpoint
        let isRefreshEndpoint = operationID == "refresh_access_token_v1_auth_refresh_post"

        // Add Authorization header based on endpoint type
        if isRefreshEndpoint, let refreshToken {
            modifiedRequest.headerFields[.authorization] = "Bearer \(refreshToken)"
        } else if let accessToken {
            modifiedRequest.headerFields[.authorization] = "Bearer \(accessToken)"
        }

        return try await next(modifiedRequest, body, baseURL)
    }
}
