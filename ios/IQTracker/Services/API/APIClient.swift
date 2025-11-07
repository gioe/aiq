import Foundation

/// Protocol defining the API client interface
protocol APIClientProtocol {
    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool
    ) async throws -> T

    func setAuthToken(_ token: String?)
}

/// HTTP methods supported by the API
enum HTTPMethod: String {
    case get = "GET"
    case post = "POST"
    case put = "PUT"
    case delete = "DELETE"
}

/// API endpoint definitions
enum APIEndpoint {
    case register
    case login
    case refreshToken
    case logout
    case userProfile
    case testStart
    case testSubmit
    case testResults(String)
    case testHistory

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
        case let .testResults(testId):
            "/v1/test/results/\(testId)"
        case .testHistory:
            "/v1/test/history"
        }
    }
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
    private var interceptors: [RequestInterceptor]
    private let retryExecutor: RetryExecutor
    private let requestTimeout: TimeInterval

    init(
        baseURL: String,
        session: URLSession = .shared,
        retryPolicy: RetryPolicy = .default,
        requestTimeout: TimeInterval = 30.0
    ) {
        guard let url = URL(string: baseURL) else {
            fatalError("Invalid base URL: \(baseURL)")
        }
        self.baseURL = url
        self.session = session
        self.requestTimeout = requestTimeout
        retryExecutor = RetryExecutor(policy: retryPolicy)

        // Set up default interceptors
        interceptors = [
            ConnectivityInterceptor(),
            LoggingInterceptor()
        ]
    }

    func setAuthToken(_ token: String?) {
        authToken = token
    }

    func addInterceptor(_ interceptor: RequestInterceptor) {
        interceptors.append(interceptor)
    }

    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod = .get,
        body: Encodable? = nil,
        requiresAuth: Bool = true
    ) async throws -> T {
        // Use retry executor for resilient requests
        try await retryExecutor.execute {
            try await self.performRequest(
                endpoint: endpoint,
                method: method,
                body: body,
                requiresAuth: requiresAuth
            )
        }
    }

    private func performRequest<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool
    ) async throws -> (T, HTTPURLResponse) {
        var urlRequest = try buildRequest(
            endpoint: endpoint,
            method: method,
            body: body,
            requiresAuth: requiresAuth
        )

        // Apply interceptors
        for interceptor in interceptors {
            urlRequest = try await interceptor.intercept(urlRequest)
        }

        // Perform request
        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        // Log response
        NetworkLogger.shared.logResponse(httpResponse, data: data)

        // Handle response
        let result: T = try handleResponse(data: data, statusCode: httpResponse.statusCode)
        return (result, httpResponse)
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
        case 401:
            throw APIError.unauthorized
        case 403:
            throw APIError.forbidden
        case 404:
            throw APIError.notFound
        case 500 ... 599:
            throw APIError.serverError(statusCode: statusCode)
        default:
            throw APIError.unknown
        }
    }

    private func decodeResponse<T: Decodable>(data: Data) throws -> T {
        do {
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
}
