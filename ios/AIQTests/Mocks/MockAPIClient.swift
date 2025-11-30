@testable import AIQ
import Foundation

/// Mock implementation of APIClientProtocol for testing
class MockAPIClient: APIClientProtocol {
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

    // Queue-based responses for multiple sequential calls
    var responseQueue: [Any] = []
    var errorQueue: [Error] = []

    // MARK: - APIClientProtocol Implementation

    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool
    ) async throws -> T {
        requestCalled = true
        lastEndpoint = endpoint
        lastMethod = method
        lastBody = body
        lastRequiresAuth = requiresAuth

        // Track all calls
        allEndpoints.append(endpoint)
        allMethods.append(method)

        // Check error queue first
        if !errorQueue.isEmpty {
            let error = errorQueue.removeFirst()
            throw error
        }

        // Check for single error
        if let error = mockError {
            throw error
        }

        // Check response queue
        if !responseQueue.isEmpty {
            let response = responseQueue.removeFirst()
            guard let typedResponse = response as? T else {
                throw NSError(
                    domain: "MockAPIClient",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "Queued response type mismatch"]
                )
            }
            return typedResponse
        }

        // Fall back to single response
        guard let response = mockResponse as? T else {
            throw NSError(
                domain: "MockAPIClient",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Mock response not configured or type mismatch"]
            )
        }

        return response
    }

    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool,
        customHeaders: [String: String]
    ) async throws -> T {
        lastCustomHeaders = customHeaders
        return try await request(
            endpoint: endpoint,
            method: method,
            body: body,
            requiresAuth: requiresAuth
        )
    }

    func setAuthToken(_: String?) {
        // No-op for mock
    }

    // MARK: - Helper Methods

    /// Add a response to the queue for sequential API calls
    func addQueuedResponse(_ response: some Any) {
        responseQueue.append(response)
    }

    /// Add an error to the queue for sequential API calls
    func addQueuedError(_ error: Error) {
        errorQueue.append(error)
    }

    func reset() {
        requestCalled = false
        lastEndpoint = nil
        lastMethod = nil
        lastBody = nil
        lastRequiresAuth = nil
        lastCustomHeaders = nil
        mockResponse = nil
        mockError = nil
        responseQueue.removeAll()
        errorQueue.removeAll()
        allEndpoints.removeAll()
        allMethods.removeAll()
    }
}
