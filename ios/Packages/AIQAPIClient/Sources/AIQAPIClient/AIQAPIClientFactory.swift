import Foundation
import OpenAPIRuntime
import OpenAPIURLSession

/// Date transcoder that handles ISO 8601 dates both with and without fractional seconds.
///
/// The backend (Pydantic/FastAPI) sends dates with microsecond precision
/// (e.g. "2025-11-26T02:01:47.860855Z") but `ISO8601DateFormatter` with default
/// options rejects fractional seconds, and with `.withFractionalSeconds` it rejects
/// dates without them. This transcoder tries fractional seconds first, then falls
/// back to the standard format.
struct FlexibleISO8601DateTranscoder: DateTranscoder, @unchecked Sendable {
    private let lock = NSLock()
    private let withFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private let withoutFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    func encode(_ date: Date) throws -> String {
        lock.lock()
        defer { lock.unlock() }
        return withFractional.string(from: date)
    }

    func decode(_ dateString: String) throws -> Date {
        lock.lock()
        defer { lock.unlock() }
        if let date = withFractional.date(from: dateString) {
            return date
        }
        if let date = withoutFractional.date(from: dateString) {
            return date
        }
        throw DecodingError.dataCorrupted(
            .init(codingPath: [], debugDescription: "Expected ISO 8601 date string, got: \(dateString)")
        )
    }
}

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
            configuration: .init(dateTranscoder: FlexibleISO8601DateTranscoder()),
            transport: URLSessionTransport(),
            middlewares: [
                authMiddleware,
                loggingMiddleware
            ]
        )
    }
}
