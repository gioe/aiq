import Foundation
import OpenAPIRuntime
import OpenAPIURLSession

/// Factory for creating configured OpenAPI client instances.
///
/// This factory provides a convenient way to create API clients with proper
/// middleware configuration including authentication and logging.
///
/// ## Usage
/// ```swift
/// // Create a client with default configuration
/// let factory = AIQAPIClientFactory(serverURL: URL(string: "https://api.example.com")!)
/// let client = factory.makeClient()
///
/// // Use the client
/// let response = try await client.loginUserV1AuthLoginPost(
///     body: .json(.init(email: "user@example.com", password: "secret"))
/// )
///
/// // Set tokens after login
/// if case .ok(let loginResponse) = response,
///    case .json(let token) = loginResponse.body {
///     await factory.authMiddleware.setTokens(
///         accessToken: token.accessToken,
///         refreshToken: token.refreshToken
///     )
/// }
/// ```
public final class AIQAPIClientFactory {
    /// The server URL for API requests
    public let serverURL: URL

    /// The authentication middleware (accessible for token management)
    public let authMiddleware: AuthenticationMiddleware

    /// The logging middleware
    public let loggingMiddleware: LoggingMiddleware

    /// Creates a new API client factory
    /// - Parameters:
    ///   - serverURL: The base URL for API requests
    ///   - logLevel: The logging level (defaults to `.debug` in DEBUG, `.error` otherwise)
    public init(
        serverURL: URL,
        logLevel: LoggingMiddleware.LogLevel? = nil
    ) {
        self.serverURL = serverURL
        authMiddleware = AuthenticationMiddleware()
        loggingMiddleware = LoggingMiddleware(logLevel: logLevel)
    }

    /// Creates a new configured API client
    /// - Returns: A Client instance configured with auth and logging middlewares
    public func makeClient() -> Client {
        Client(
            serverURL: serverURL,
            transport: URLSessionTransport(),
            middlewares: [
                authMiddleware,
                loggingMiddleware
            ]
        )
    }
}
