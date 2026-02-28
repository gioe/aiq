import Foundation
import HTTPTypes
import OpenAPIRuntime

/// Middleware that transparently refreshes access tokens on 401 responses.
///
/// When a request returns 401, this middleware:
/// 1. Calls `tokenRefreshHandler` (which updates `AuthenticationMiddleware` with new tokens)
/// 2. Retries the original request — `AuthenticationMiddleware` injects the fresh token
///
/// Concurrent 401 responses are coalesced: only one refresh runs at a time; all others
/// await the same `Task` and then retry.
///
/// Placement in middleware chain: **before** `AuthenticationMiddleware` so that the retry
/// re-enters `authMiddleware` and picks up the freshly-stored token.
///
/// ## Infinite-loop guard
/// If a 401 arrives from the refresh endpoint itself, the error is rethrown immediately
/// without triggering another refresh cycle.
actor TokenRefreshMiddleware: ClientMiddleware {
    /// Derived from the OpenAPI generator naming convention:
    /// {operation_id}_{path_segments_with_underscores}_{http_method}
    /// This matches `POST /v1/auth/refresh` → "refresh_access_token_v1_auth_refresh_post".
    /// Must be kept in sync with the OpenAPI spec if the endpoint path or HTTP method changes.
    static let refreshOperationID = "refresh_access_token_v1_auth_refresh_post"

    /// Closure that performs the token refresh and updates stored tokens as a side effect.
    private let tokenRefreshHandler: () async throws -> Void

    /// Coalescing task: non-nil while a refresh is in flight.
    private var refreshTask: Task<Void, Error>?

    init(tokenRefreshHandler: @escaping () async throws -> Void) {
        self.tokenRefreshHandler = tokenRefreshHandler
    }

    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        // Buffer the body to Data *before* the first next() call so the same bytes can be
        // replayed on retry. HTTPBody is a consumable stream — reading it twice from the same
        // instance yields 0 bytes on the second read.
        let bodyData: Data? = if let body {
            try await Data(collecting: body, upTo: 1024 * 1024)
        } else {
            nil
        }

        let (response, responseBody) = try await next(request, bodyData.map { HTTPBody($0) }, baseURL)

        guard response.status == .unauthorized else {
            return (response, responseBody)
        }

        // Guard: never attempt to refresh if the refresh endpoint itself returns 401.
        guard operationID != Self.refreshOperationID else {
            throw APIError.unauthorized(message: "Refresh token expired or invalid")
        }

        try await performRefresh()

        // Construct a fresh HTTPBody from the saved Data for the retry attempt.
        return try await next(request, bodyData.map { HTTPBody($0) }, baseURL)
    }

    // MARK: - Private

    private func performRefresh() async throws {
        if let existing = refreshTask {
            try await existing.value
            return
        }

        let task = Task<Void, Error> { [tokenRefreshHandler] in
            try await tokenRefreshHandler()
        }
        refreshTask = task
        defer { refreshTask = nil }

        do {
            try await task.value
        } catch {
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .tokenRefresh,
                additionalInfo: [
                    "event": "token_refresh_failed",
                    "middleware": "TokenRefreshMiddleware"
                ]
            )
            throw error
        }
    }
}
