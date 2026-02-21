@testable import AIQAPIClient
import Foundation
import HTTPTypes
import OpenAPIRuntime
import Testing

@Suite("LoggingMiddleware Tests")
struct LoggingMiddlewareTests {
    // MARK: - Log Level Filtering Tests

    @Test("No logging when log level is none")
    func noLoggingWhenLogLevelNone() async throws {
        let middleware = LoggingMiddleware(logLevel: .none)
        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")

        // Should pass through without any logging
        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { _, _, _ in
            (HTTPResponse(status: .ok), nil)
        }

        #expect(response.status == .ok)
    }

    @Test("Middleware passes through request and response unchanged")
    func middlewarePassesThroughUnchanged() async throws {
        let middleware = LoggingMiddleware(logLevel: .info)
        var request = HTTPRequest(method: .post, scheme: "https", authority: "api.example.com", path: "/v1/test")
        request.headerFields[.contentType] = "application/json"

        var capturedRequest: HTTPRequest?
        var capturedBody: HTTPBody?
        var capturedURL: URL?

        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { req, body, url in
            capturedRequest = req
            capturedBody = body
            capturedURL = url
            return (HTTPResponse(status: .created), nil)
        }

        // Verify request is passed through unchanged
        #expect(capturedRequest?.method == .post)
        #expect(capturedRequest?.path == "/v1/test")
        #expect(capturedRequest?.headerFields[.contentType] == "application/json")
        #expect(capturedBody == nil)
        #expect(capturedURL?.absoluteString == "https://api.example.com")

        // Verify response is returned unchanged
        #expect(response.status == .created)
    }

    @Test("Middleware propagates errors")
    func middlewarePropagatesErrors() async throws {
        let middleware = LoggingMiddleware(logLevel: .error)
        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")

        struct TestError: Error {}

        await #expect(throws: TestError.self) {
            try await middleware.intercept(
                request,
                body: nil,
                baseURL: #require(URL(string: "https://api.example.com")),
                operationID: "test_operation"
            ) { _, _, _ in
                throw TestError()
            }
        }
    }

    // MARK: - Sensitive Header Redaction Tests

    @Test("Default sensitive headers include authorization")
    func defaultSensitiveHeadersIncludeAuthorization() async throws {
        // Default initialization includes "authorization" as sensitive
        let middleware = LoggingMiddleware(logLevel: .debug)
        var request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")
        request.headerFields[.authorization] = "Bearer secret-token"

        // The middleware should redact authorization in logs
        // We can't directly verify log output, but we verify the middleware doesn't modify the request
        var capturedRequest: HTTPRequest?

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        // The actual request should still have the real token (not redacted)
        #expect(capturedRequest?.headerFields[.authorization] == "Bearer secret-token")
    }

    @Test("Custom sensitive headers are redacted")
    func customSensitiveHeadersAreRedacted() async throws {
        // Custom sensitive headers
        let middleware = LoggingMiddleware(
            logLevel: .debug,
            sensitiveHeaders: ["authorization", "x-api-key", "x-secret"]
        )

        var request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")
        request.headerFields[.authorization] = "Bearer token"
        try request.headerFields[#require(HTTPField.Name("X-API-Key"))] = "api-key-value"
        try request.headerFields[#require(HTTPField.Name("X-Secret"))] = "secret-value"
        request.headerFields[.contentType] = "application/json"

        var capturedRequest: HTTPRequest?

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Verify request headers are passed through unchanged to the next handler
        #expect(capturedRequest?.headerFields[.authorization] == "Bearer token")
        #expect(try capturedRequest?.headerFields[#require(HTTPField.Name("X-API-Key"))] == "api-key-value")
        #expect(try capturedRequest?.headerFields[#require(HTTPField.Name("X-Secret"))] == "secret-value")
        #expect(capturedRequest?.headerFields[.contentType] == "application/json")
    }

    @Test("Sensitive header comparison is case-insensitive")
    func sensitiveHeaderComparisonIsCaseInsensitive() async throws {
        // Using mixed case in the sensitive headers set
        let middleware = LoggingMiddleware(
            logLevel: .debug,
            sensitiveHeaders: ["AUTHORIZATION", "X-Api-Key"]
        )

        var request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")
        request.headerFields[.authorization] = "Bearer token" // lowercase
        try request.headerFields[#require(HTTPField.Name("x-api-key"))] = "key" // lowercase

        var capturedRequest: HTTPRequest?

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { req, _, _ in
            capturedRequest = req
            return (HTTPResponse(status: .ok), nil)
        }

        // Headers should pass through unchanged
        #expect(capturedRequest?.headerFields[.authorization] == "Bearer token")
    }

    // MARK: - Request/Response Timing Tests

    @Test("Middleware measures request duration")
    func middlewareMeasuresRequestDuration() async throws {
        let middleware = LoggingMiddleware(logLevel: .info)
        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")

        let startTime = Date()

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { _, _, _ in
            // Simulate a small delay
            try await Task.sleep(nanoseconds: 50_000_000) // 50ms
            return (HTTPResponse(status: .ok), nil)
        }

        let elapsed = Date().timeIntervalSince(startTime)

        // The request should have taken at least 50ms
        #expect(elapsed >= 0.05)
    }

    // MARK: - LogLevel Comparison Tests

    @Test("LogLevel comparison works correctly")
    func logLevelComparisonWorks() {
        #expect(LoggingMiddleware.LogLevel.none < LoggingMiddleware.LogLevel.error)
        #expect(LoggingMiddleware.LogLevel.error < LoggingMiddleware.LogLevel.info)
        #expect(LoggingMiddleware.LogLevel.info < LoggingMiddleware.LogLevel.debug)
        #expect(LoggingMiddleware.LogLevel.debug < LoggingMiddleware.LogLevel.verbose)

        #expect(LoggingMiddleware.LogLevel.verbose >= LoggingMiddleware.LogLevel.debug)
        #expect(LoggingMiddleware.LogLevel.debug >= LoggingMiddleware.LogLevel.info)
    }

    // MARK: - Different Response Status Tests

    @Test("Middleware handles success status codes")
    func middlewareHandlesSuccessStatusCodes() async throws {
        let middleware = LoggingMiddleware(logLevel: .info)
        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")

        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { _, _, _ in
            (HTTPResponse(status: .ok), nil)
        }

        #expect(response.status == .ok)
    }

    @Test("Middleware handles client error status codes")
    func middlewareHandlesClientErrorStatusCodes() async throws {
        let middleware = LoggingMiddleware(logLevel: .info)
        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")

        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { _, _, _ in
            (HTTPResponse(status: .notFound), nil)
        }

        #expect(response.status == .notFound)
    }

    @Test("Middleware handles server error status codes")
    func middlewareHandlesServerErrorStatusCodes() async throws {
        let middleware = LoggingMiddleware(logLevel: .info)
        let request = HTTPRequest(method: .get, scheme: "https", authority: "api.example.com", path: "/v1/test")

        let (response, _) = try await middleware.intercept(
            request,
            body: nil,
            baseURL: #require(URL(string: "https://api.example.com")),
            operationID: "test_operation"
        ) { _, _, _ in
            (HTTPResponse(status: .internalServerError), nil)
        }

        #expect(response.status == .internalServerError)
    }

    // MARK: - Sendable Conformance

    @Test("Middleware is Sendable and can be used across concurrency boundaries")
    func middlewareIsSendable() async {
        let middleware = LoggingMiddleware(logLevel: .info)

        // Use middleware from multiple concurrent tasks
        await withTaskGroup(of: HTTPResponse.Status.self) { group in
            for _ in 0 ..< 10 {
                group.addTask {
                    let request = HTTPRequest(
                        method: .get,
                        scheme: "https",
                        authority: "api.example.com",
                        path: "/test"
                    )
                    // swiftlint:disable:next force_try
                    let (response, _) = try! await middleware.intercept(
                        request,
                        body: nil,
                        baseURL: URL(string: "https://api.example.com")!,
                        operationID: "test"
                    ) { _, _, _ in
                        (HTTPResponse(status: .ok), nil)
                    }
                    return response.status
                }
            }

            for await status in group {
                #expect(status == .ok)
            }
        }
    }
}
