import Foundation
@testable import AIQ

/// Mock implementation of APIClientProtocol for testing
class MockAPIClient: APIClientProtocol {
    // MARK: - Properties for Testing

    var requestCalled = false
    var lastEndpoint: APIEndpoint?
    var lastMethod: HTTPMethod?
    var lastBody: Encodable?
    var lastRequiresAuth: Bool?
    var lastCustomHeaders: [String: String]?

    // MARK: - Mock Response Configuration

    var mockResponse: Any?
    var mockError: Error?

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

        if let error = mockError {
            throw error
        }

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

    func setAuthToken(_ token: String?) {
        // No-op for mock
    }

    // MARK: - Helper Methods

    func reset() {
        requestCalled = false
        lastEndpoint = nil
        lastMethod = nil
        lastBody = nil
        lastRequiresAuth = nil
        lastCustomHeaders = nil
        mockResponse = nil
        mockError = nil
    }
}
