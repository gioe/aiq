import Foundation

/// Protocol defining the API client interface
protocol APIClientProtocol {
    /// Perform an API request
    /// - Parameters:
    ///   - endpoint: The API endpoint to call
    ///   - method: HTTP method to use
    ///   - body: Optional request body
    ///   - requiresAuth: Whether authentication is required
    ///   - customHeaders: Optional custom headers to add to the request
    ///   - cacheKey: Optional cache key for storing/retrieving cached responses
    ///   - cacheDuration: Optional cache duration in seconds (only used if cacheKey is provided)
    ///   - forceRefresh: If true, bypass cache and fetch from API
    /// - Returns: Decoded response of type T
    func request<T: Decodable>( // swiftlint:disable:this function_parameter_count
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool,
        customHeaders: [String: String]?,
        cacheKey: String?,
        cacheDuration: TimeInterval?,
        forceRefresh: Bool
    ) async throws -> T

    /// Set the authentication token for API requests
    /// - Parameter token: The bearer token to use, or nil to clear
    func setAuthToken(_ token: String?)
}

/// Extension providing default parameter values for protocol
extension APIClientProtocol {
    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod = .get,
        body: Encodable? = nil,
        requiresAuth: Bool = true,
        customHeaders: [String: String]? = nil,
        cacheKey: String? = nil,
        cacheDuration: TimeInterval? = nil,
        forceRefresh: Bool = false
    ) async throws -> T {
        try await request(
            endpoint: endpoint,
            method: method,
            body: body,
            requiresAuth: requiresAuth,
            customHeaders: customHeaders,
            cacheKey: cacheKey,
            cacheDuration: cacheDuration,
            forceRefresh: forceRefresh
        )
    }
}

/// HTTP methods supported by the API
enum HTTPMethod: String {
    /// HTTP GET method
    case get = "GET"
    /// HTTP POST method
    case post = "POST"
    /// HTTP PUT method
    case put = "PUT"
    /// HTTP DELETE method
    case delete = "DELETE"
}

/// API endpoint definitions
enum APIEndpoint: Equatable {
    /// User registration endpoint
    case register
    /// User login endpoint
    case login
    /// Token refresh endpoint
    case refreshToken
    /// User logout endpoint
    case logout
    /// User profile endpoint
    case userProfile
    /// Start test session endpoint
    case testStart
    /// Submit test answers endpoint
    case testSubmit
    /// Abandon test session endpoint
    case testAbandon(Int)
    /// Retrieve specific test session by ID
    case testSession(Int)
    /// Get test results by ID
    case testResults(String)
    /// Get test history endpoint with pagination
    case testHistory(limit: Int?, offset: Int?)
    /// Register device for push notifications
    case notificationRegisterDevice
    /// Update notification preferences
    case notificationPreferences
    /// Check for active test session
    case testActive
    /// Delete user account
    case deleteAccount

    /// The URL path for this endpoint
    var path: String {
        switch self {
        case .register:
            "/v1/auth/register"
        case .login:
            "/v1/auth/login"
        case .refreshToken:
            "/v1/auth/refresh"
        case .logout:
            "/v1/auth/logout"
        case .userProfile:
            "/v1/user/profile"
        case .testStart:
            "/v1/test/start"
        case .testSubmit:
            "/v1/test/submit"
        case let .testAbandon(sessionId):
            "/v1/test/\(sessionId)/abandon"
        case let .testSession(sessionId):
            "/v1/test/session/\(sessionId)"
        case let .testResults(testId):
            "/v1/test/results/\(testId)"
        case let .testHistory(limit, offset):
            {
                var path = "/v1/test/history"
                var queryParams: [String] = []
                if let limit {
                    queryParams.append("limit=\(limit)")
                }
                if let offset {
                    queryParams.append("offset=\(offset)")
                }
                if !queryParams.isEmpty {
                    path += "?" + queryParams.joined(separator: "&")
                }
                return path
            }()
        case .notificationRegisterDevice:
            "/v1/notifications/register-device"
        case .notificationPreferences:
            "/v1/notifications/preferences"
        case .testActive:
            "/v1/test/active"
        case .deleteAccount:
            "/v1/user/delete-account"
        }
    }
}

/// Context for request retries after token refresh
private struct RequestContext {
    let endpoint: APIEndpoint
    let method: HTTPMethod
    let body: Encodable?
    let requiresAuth: Bool
    let customHeaders: [String: String]?
    let retryCount: Int

    /// Maximum number of retries allowed for token refresh
    static let maxRetries = 1
}

/// Main API client implementation
class APIClient: APIClientProtocol {
    /// Shared singleton instance
    static let shared = APIClient(
        baseURL: AppConfig.apiBaseURL,
        retryPolicy: .default
    )

    private let baseURL: URL
    private let session: URLSession
    private var authToken: String?
    private var requestInterceptors: [RequestInterceptor]
    private var responseInterceptors: [ResponseInterceptor]
    private let retryExecutor: RetryExecutor
    private let requestTimeout: TimeInterval
    private let tokenRefreshInterceptor: TokenRefreshInterceptor

    /// Initialize the API client
    /// - Parameters:
    ///   - baseURL: The base URL for API requests
    ///   - session: URLSession to use. Defaults to `.shared` which is required for TrustKit
    ///              certificate pinning to work (TrustKit swizzles URLSession.shared).
    ///   - retryPolicy: Retry policy for failed requests
    ///   - requestTimeout: Timeout for requests in seconds
    ///   - requestInterceptors: Custom request interceptors
    ///   - responseInterceptors: Custom response interceptors
    init(
        baseURL: String,
        session: URLSession = .shared,
        retryPolicy: RetryPolicy = .default,
        requestTimeout: TimeInterval = 30.0,
        requestInterceptors: [RequestInterceptor]? = nil,
        responseInterceptors: [ResponseInterceptor]? = nil
    ) {
        guard let url = URL(string: baseURL) else {
            fatalError("Invalid base URL: \(baseURL)")
        }
        self.baseURL = url
        self.session = session
        self.requestTimeout = requestTimeout
        retryExecutor = RetryExecutor(policy: retryPolicy)

        // Initialize token refresh interceptor
        // Note: AuthService will be set later to avoid circular dependency
        tokenRefreshInterceptor = TokenRefreshInterceptor()

        // Set up request interceptors (use provided or defaults)
        self.requestInterceptors = requestInterceptors ?? [
            ConnectivityInterceptor(),
            LoggingInterceptor()
        ]

        // Set up response interceptors (use provided or defaults)
        self.responseInterceptors = responseInterceptors ?? [
            tokenRefreshInterceptor
        ]
    }

    func setAuthToken(_ token: String?) {
        authToken = token
    }

    /// Set the authentication service for automatic token refresh
    /// - Parameter authService: The authentication service to use for token refresh operations
    func setAuthService(_ authService: AuthServiceProtocol) async {
        await tokenRefreshInterceptor.setAuthService(authService)
    }

    /// Add a request interceptor to the pipeline
    /// - Parameter interceptor: The request interceptor to add
    func addRequestInterceptor(_ interceptor: RequestInterceptor) {
        requestInterceptors.append(interceptor)
    }

    /// Add a response interceptor to the pipeline
    /// - Parameter interceptor: The response interceptor to add
    func addResponseInterceptor(_ interceptor: ResponseInterceptor) {
        responseInterceptors.append(interceptor)
    }

    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod = .get,
        body: Encodable? = nil,
        requiresAuth: Bool = true,
        customHeaders: [String: String]? = nil,
        cacheKey: String? = nil,
        cacheDuration: TimeInterval? = nil,
        forceRefresh: Bool = false
    ) async throws -> T {
        // Check cache first if caching is enabled and not forcing refresh
        if let cacheKey, !forceRefresh {
            if let cached: T = await DataCache.shared.get(forKey: cacheKey) {
                #if DEBUG
                    print("✅ Loaded response from cache (key: \(cacheKey))")
                #endif
                return cached
            }
        }

        // Use retry executor for resilient requests
        let result: T = try await retryExecutor.execute {
            try await self.performRequest(
                endpoint: endpoint,
                method: method,
                body: body,
                requiresAuth: requiresAuth,
                customHeaders: customHeaders
            )
        }

        // Cache the result if caching is enabled
        if let cacheKey {
            await DataCache.shared.set(
                result,
                forKey: cacheKey,
                expiration: cacheDuration
            )
            #if DEBUG
                let durationText = cacheDuration.map { "\($0)s" } ?? "default"
                print("✅ Cached response (key: \(cacheKey), duration: \(durationText))")
            #endif
        }

        return result
    }

    private func performRequest<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool,
        customHeaders: [String: String]?
    ) async throws -> (T, HTTPURLResponse) {
        let urlRequest = try await prepareRequest(
            endpoint: endpoint,
            method: method,
            body: body,
            requiresAuth: requiresAuth,
            customHeaders: customHeaders
        )

        let (data, httpResponse, duration) = try await executeRequest(urlRequest)

        let context = RequestContext(
            endpoint: endpoint,
            method: method,
            body: body,
            requiresAuth: requiresAuth,
            customHeaders: customHeaders,
            retryCount: 0
        )

        let responseData = try await applyResponseInterceptors(
            data: data,
            response: httpResponse,
            context: context
        )

        return try handleResponseWithAnalytics(
            data: responseData,
            response: httpResponse,
            endpoint: endpoint,
            duration: duration
        )
    }

    private func prepareRequest(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool,
        customHeaders: [String: String]?
    ) async throws -> URLRequest {
        var urlRequest = try buildRequest(
            endpoint: endpoint,
            method: method,
            body: body,
            requiresAuth: requiresAuth
        )

        // Add custom headers if provided
        if let customHeaders {
            for (key, value) in customHeaders {
                urlRequest.setValue(value, forHTTPHeaderField: key)
            }
        }

        // Apply request interceptors
        for interceptor in requestInterceptors {
            urlRequest = try await interceptor.intercept(urlRequest)
        }

        return urlRequest
    }

    private func executeRequest(_ urlRequest: URLRequest) async throws -> (Data, HTTPURLResponse, TimeInterval) {
        let startTime = Date()
        logRequest(urlRequest)

        // Perform network request and wrap URLErrors in APIError
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: urlRequest)
        } catch let urlError as URLError {
            throw APIError.networkError(urlError)
        }

        let duration = Date().timeIntervalSince(startTime)

        guard let httpResponse = response as? HTTPURLResponse else {
            print("❌ Invalid response - not an HTTP response")
            throw APIError.invalidResponse
        }

        logResponse(httpResponse, data: data, duration: duration)
        NetworkLogger.shared.logResponse(httpResponse, data: data)

        return (data, httpResponse, duration)
    }

    private func applyResponseInterceptors(
        data: Data,
        response: HTTPURLResponse,
        context: RequestContext
    ) async throws -> Data {
        var responseData = data

        for interceptor in responseInterceptors {
            do {
                responseData = try await interceptor.intercept(response: response, data: responseData)
            } catch {
                // If a response interceptor handles the error (e.g., token refresh),
                // retry the original request
                if let tokenRefreshError = error as? TokenRefreshError,
                   case .shouldRetryRequest = tokenRefreshError {
                    // Check if we've exceeded the retry limit
                    guard context.retryCount < RequestContext.maxRetries else {
                        print("❌ Token refresh retry limit exceeded (\(RequestContext.maxRetries) attempts)")
                        throw APIError.unauthorized(message: "Authentication failed after token refresh")
                    }

                    // Retry the request with incremented retry count
                    let urlRequest = try await prepareRequest(
                        endpoint: context.endpoint,
                        method: context.method,
                        body: context.body,
                        requiresAuth: context.requiresAuth,
                        customHeaders: context.customHeaders
                    )
                    let (newData, newResponse, _) = try await executeRequest(urlRequest)

                    // Create new context with incremented retry count
                    let newContext = RequestContext(
                        endpoint: context.endpoint,
                        method: context.method,
                        body: context.body,
                        requiresAuth: context.requiresAuth,
                        customHeaders: context.customHeaders,
                        retryCount: context.retryCount + 1
                    )

                    return try await applyResponseInterceptors(
                        data: newData,
                        response: newResponse,
                        context: newContext
                    )
                }
                throw error
            }
        }

        return responseData
    }

    private func handleResponseWithAnalytics<T: Decodable>(
        data: Data,
        response: HTTPURLResponse,
        endpoint: APIEndpoint,
        duration: TimeInterval
    ) throws -> (T, HTTPURLResponse) {
        do {
            let result: T = try handleResponse(data: data, statusCode: response.statusCode)

            // Track slow requests (> 2 seconds)
            if duration > Constants.Network.slowRequestThreshold {
                AnalyticsService.shared.trackSlowRequest(
                    endpoint: endpoint.path,
                    durationSeconds: duration,
                    statusCode: response.statusCode
                )
            }

            return (result, response)
        } catch {
            // Track API errors
            AnalyticsService.shared.trackAPIError(
                endpoint: endpoint.path,
                error: error,
                statusCode: response.statusCode
            )
            throw error
        }
    }

    private func buildRequest(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool
    ) throws -> URLRequest {
        guard let url = URL(string: endpoint.path, relativeTo: baseURL) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue
        request.timeoutInterval = requestTimeout
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("iOS", forHTTPHeaderField: "X-Platform")
        request.setValue(AppConfig.appVersion, forHTTPHeaderField: "X-App-Version")

        if requiresAuth, let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            request.httpBody = try encoder.encode(body)
        }

        return request
    }

    private func handleResponse<T: Decodable>(data: Data, statusCode: Int) throws -> T {
        switch statusCode {
        case 200 ... 299:
            return try decodeResponse(data: data)
        case 400:
            let message = parseErrorMessage(from: data)
            throw APIError.badRequest(message: message)
        case 401:
            let message = parseErrorMessage(from: data)
            throw APIError.unauthorized(message: message)
        case 403:
            let message = parseErrorMessage(from: data)
            throw APIError.forbidden(message: message)
        case 404:
            let message = parseErrorMessage(from: data)
            throw APIError.notFound(message: message)
        case 408:
            throw APIError.timeout
        case 422:
            // Validation error - map to badRequest
            let message = parseErrorMessage(from: data)
            throw APIError.unprocessableEntity(message: message)
        case 500 ... 599:
            let message = parseErrorMessage(from: data)
            throw APIError.serverError(statusCode: statusCode, message: message)
        default:
            let message = parseErrorMessage(from: data)
            throw APIError.unknown(message: message)
        }
    }

    private func parseErrorMessage(from data: Data) -> String? {
        guard let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) else {
            return nil
        }
        return errorResponse.detail
    }

    private func decodeResponse<T: Decodable>(data: Data) throws -> T {
        do {
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            return try decoder.decode(T.self, from: data)
        } catch {
            // Enhanced logging for debugging decoding errors
            print("❌ DECODING ERROR for type: \(T.self)")
            print("📝 Raw response data size: \(data.count) bytes")

            // Log the raw JSON response if possible
            if let jsonString = String(data: data, encoding: .utf8) {
                print("📄 Raw JSON response:")
                print(jsonString)
            } else {
                print("⚠️ Unable to convert response data to string")
            }

            // Log specific decoding error details
            if let decodingError = error as? DecodingError {
                print("🔍 Decoding error details:")
                switch decodingError {
                case let .keyNotFound(key, context):
                    let path = context.codingPath.map(\.stringValue).joined(separator: " -> ")
                    print("  - Missing key: '\(key.stringValue)' at path: \(path)")
                case let .typeMismatch(type, context):
                    let path = context.codingPath.map(\.stringValue).joined(separator: " -> ")
                    print("  - Type mismatch for type: \(type) at path: \(path)")
                    print("  - Debug description: \(context.debugDescription)")
                case let .valueNotFound(type, context):
                    let path = context.codingPath.map(\.stringValue).joined(separator: " -> ")
                    print("  - Value not found for type: \(type) at path: \(path)")
                    print("  - Debug description: \(context.debugDescription)")
                case let .dataCorrupted(context):
                    let path = context.codingPath.map(\.stringValue).joined(separator: " -> ")
                    print("  - Data corrupted at path: \(path)")
                    print("  - Debug description: \(context.debugDescription)")
                @unknown default:
                    print("  - Unknown decoding error: \(error.localizedDescription)")
                }
            } else {
                print("  - Error type: \(type(of: error))")
                print("  - Error description: \(error.localizedDescription)")
            }

            throw APIError.decodingError(error)
        }
    }

    private func logRequest(_ request: URLRequest) {
        print("📤 Making request to: \(request.url?.absoluteString ?? "unknown URL")")
        print("   - Method: \(request.httpMethod ?? "unknown")")
        print("   - Headers: \(request.allHTTPHeaderFields ?? [:])")
        if let bodyData = request.httpBody, let bodyString = String(data: bodyData, encoding: .utf8) {
            print("   - Body: \(bodyString)")
        }
    }

    private func logResponse(_ response: HTTPURLResponse, data: Data, duration: TimeInterval) {
        print("📥 Received response:")
        print("   - Status code: \(response.statusCode)")
        print("   - Duration: \(String(format: "%.2f", duration))s")
        print("   - Response size: \(data.count) bytes")
    }
}
