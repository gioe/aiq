@testable import AIQ
import Foundation

/// Mock implementation of APIClientProtocol for testing
/// Thread-safe via actor isolation
actor MockAPIClient: APIClientProtocol {
    // MARK: - Properties for Testing

    var requestCalled = false
    var lastEndpoint: APIEndpoint?
    var lastMethod: HTTPMethod?
    var lastBody: Encodable?
    var lastRequiresAuth: Bool?
    var lastCustomHeaders: [String: String]?

    // Track all API calls
    var allEndpoints: [APIEndpoint] = []
    var allMethods: [HTTPMethod] = []

    // MARK: - Mock Response Configuration

    var mockResponse: Any?
    var mockError: Error?

    // Endpoint-based response mapping
    var endpointResponses: [String: Any] = [:]
    var endpointErrors: [String: Error] = [:]

    // MARK: - Initialization

    init() {}

    // MARK: - APIClientProtocol Implementation

    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool,
        customHeaders: [String: String]?,
        cacheKey: String?,
        cacheDuration: TimeInterval?,
        forceRefresh: Bool
    ) async throws -> T {
        // Check cache first if caching is enabled and not forcing refresh
        // Use DataCache (same as real APIClient) instead of internal cache
        if let cacheKey, !forceRefresh {
            if let cached: T = await DataCache.shared.get(forKey: cacheKey) {
                #if DEBUG
                    print("✅ MockAPIClient Cache HIT: \(cacheKey)")
                #endif
                return cached
            }
        }

        // Track API call (only called when cache miss or force refresh)
        // All mutations are now actor-isolated and thread-safe
        requestCalled = true
        lastEndpoint = endpoint
        lastMethod = method
        lastBody = body
        lastRequiresAuth = requiresAuth
        lastCustomHeaders = customHeaders

        // Track all calls
        allEndpoints.append(endpoint)
        allMethods.append(method)

        // Check endpoint-specific error first
        let endpointKey = endpoint.path
        if let endpointError = endpointErrors[endpointKey] {
            throw endpointError
        }

        // Check for single error
        if let error = mockError {
            throw error
        }

        // Get response: endpoint-specific or single
        let response: T
        if let endpointResponse = endpointResponses[endpointKey] {
            // Use endpoint-specific response
            if endpointResponse is NSNull {
                response = nilValue()
            } else {
                guard let typedResponse = endpointResponse as? T else {
                    throw NSError(
                        domain: "MockAPIClient",
                        code: -1,
                        userInfo: [NSLocalizedDescriptionKey: "Endpoint response type mismatch for \(endpointKey)"]
                    )
                }
                response = typedResponse
            }
        } else {
            // Fall back to single response
            guard let singleResponse = mockResponse as? T else {
                throw NSError(
                    domain: "MockAPIClient",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "Mock response not configured or type mismatch"]
                )
            }
            response = singleResponse
        }

        // Cache the result if caching is enabled
        // Use DataCache (same as real APIClient) to properly mock caching behavior
        if let cacheKey {
            await DataCache.shared.set(
                response,
                forKey: cacheKey,
                expiration: cacheDuration
            )
            #if DEBUG
                print("📦 MockAPIClient Cache SET: \(cacheKey)")
            #endif
        }

        return response
    }

    nonisolated func setAuthToken(_: String?) {
        // No-op for mock
        // nonisolated because this doesn't access actor state
    }

    // MARK: - Helper Methods

    /// Set response for a specific endpoint
    /// - Parameters:
    ///   - response: The response to return for this endpoint
    ///   - endpoint: The API endpoint
    func setResponse(_ response: some Any, for endpoint: APIEndpoint) {
        endpointResponses[endpoint.path] = response
    }

    /// Set test history response, automatically wrapping in paginated format (BCQ-004)
    /// - Parameter results: Array of test results to return
    /// - Note: The backend now returns `PaginatedTestHistoryResponse` instead of `[TestResult]`
    func setTestHistoryResponse(_ results: [TestResult]) {
        let paginatedResponse = PaginatedTestHistoryResponse(
            results: results,
            totalCount: results.count,
            limit: 50,
            offset: 0,
            hasMore: false
        )
        endpointResponses[APIEndpoint.testHistory.path] = paginatedResponse
    }

    /// Set error for a specific endpoint
    /// - Parameters:
    ///   - error: The error to throw for this endpoint
    ///   - endpoint: The API endpoint
    func setError(_ error: Error, for endpoint: APIEndpoint) {
        endpointErrors[endpoint.path] = error
    }

    func setMockError(_ error: APIError?) {
        mockError = error
    }

    /// Reset API call tracking state
    /// Note: This does NOT clear DataCache - tests should manage DataCache directly
    func reset() {
        requestCalled = false
        lastEndpoint = nil
        lastMethod = nil
        lastBody = nil
        lastRequiresAuth = nil
        lastCustomHeaders = nil
        mockResponse = nil
        mockError = nil
        endpointResponses.removeAll()
        endpointErrors.removeAll()
        allEndpoints.removeAll()
        allMethods.removeAll()
    }

    /// Helper function to return nil for optional types
    /// This avoids double-optional issues when T is already an Optional type
    private func nilValue<T>() -> T {
        // Cast Optional<Any>.none (nil) through Any to T
        // This works when T is an optional type like TestSessionStatusResponse?
        if let result = (Any?.none as Any) as? T {
            result
        } else {
            fatalError("Cannot cast nil to type \(T.self) - type must be Optional")
        }
    }
}
