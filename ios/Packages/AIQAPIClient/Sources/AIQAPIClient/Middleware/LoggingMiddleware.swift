import Foundation
import HTTPTypes
import OpenAPIRuntime

/// A middleware that logs request and response details for debugging.
///
/// This middleware provides configurable logging of API calls, including timing,
/// headers, and optionally body content. It's designed to match the existing
/// logging behavior from the legacy `APIClient`.
///
/// ## Usage
/// ```swift
/// let loggingMiddleware = LoggingMiddleware(logLevel: .debug)
/// let client = Client(
///     serverURL: serverURL,
///     transport: URLSessionTransport(),
///     middlewares: [loggingMiddleware]
/// )
/// ```
public struct LoggingMiddleware: ClientMiddleware {
    /// Log levels for API requests
    public enum LogLevel: Int, Comparable, Sendable {
        /// No logging
        case none = 0
        /// Log errors only
        case error = 1
        /// Log basic request/response info (URLs, status codes)
        case info = 2
        /// Log detailed info including headers and timing
        case debug = 3
        /// Log everything including bodies
        case verbose = 4

        public static func < (lhs: LogLevel, rhs: LogLevel) -> Bool {
            lhs.rawValue < rhs.rawValue
        }
    }

    private let logLevel: LogLevel
    private let sensitiveHeaders: Set<String>

    /// Creates a new logging middleware
    /// - Parameters:
    ///   - logLevel: The level of detail to log. Defaults to `.debug` in DEBUG builds, `.error` otherwise.
    ///   - sensitiveHeaders: Header names to redact from logs. Defaults to ["Authorization"].
    public init(
        logLevel: LogLevel? = nil,
        sensitiveHeaders: Set<String> = ["Authorization", "authorization"]
    ) {
        #if DEBUG
            self.logLevel = logLevel ?? .debug
        #else
            self.logLevel = logLevel ?? .error
        #endif
        self.sensitiveHeaders = sensitiveHeaders
    }

    public func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        guard logLevel > .none else {
            return try await next(request, body, baseURL)
        }

        let startTime = Date()
        let requestURL = baseURL.appendingPathComponent(request.path ?? "")

        // Log request
        if logLevel >= .info {
            print("📤 [\(operationID)] \(request.method.rawValue) \(requestURL.absoluteString)")
        }

        if logLevel >= .debug {
            logHeaders(request.headerFields, prefix: "   Request")
        }

        do {
            let (response, responseBody) = try await next(request, body, baseURL)
            let duration = Date().timeIntervalSince(startTime)

            // Log response
            if logLevel >= .info {
                let statusEmoji = response.status.code < 400 ? "📥" : "❌"
                print("\(statusEmoji) [\(operationID)] \(response.status.code) (\(String(format: "%.2f", duration))s)")
            }

            if logLevel >= .debug {
                logHeaders(response.headerFields, prefix: "   Response")
            }

            return (response, responseBody)
        } catch {
            let duration = Date().timeIntervalSince(startTime)

            if logLevel >= .error {
                print("❌ [\(operationID)] Error after \(String(format: "%.2f", duration))s: \(error)")
            }

            throw error
        }
    }

    private func logHeaders(_ headers: HTTPFields, prefix: String) {
        var headerDict: [String: String] = [:]
        for header in headers {
            let value = sensitiveHeaders.contains(header.name.rawName)
                ? "[REDACTED]"
                : header.value
            headerDict[header.name.rawName] = value
        }
        if !headerDict.isEmpty {
            print("\(prefix) Headers: \(headerDict)")
        }
    }
}
