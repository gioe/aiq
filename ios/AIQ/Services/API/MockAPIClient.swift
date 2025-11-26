import Foundation

/// Mock API client for testing and development
class MockAPIClient: APIClientProtocol {
    var authToken: String?
    var mockDelay: TimeInterval = 0.5
    var shouldFail: Bool = false
    var mockError: Error = APIError.unknown()

    // Mock responses
    var mockResponses: [String: Any] = [:]

    func setAuthToken(_ token: String?) {
        authToken = token
    }

    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method _: HTTPMethod,
        body _: Encodable?,
        requiresAuth _: Bool
    ) async throws -> T {
        // Simulate network delay
        try await Task.sleep(nanoseconds: UInt64(mockDelay * 1_000_000_000))

        // Simulate failure if configured
        if shouldFail {
            throw mockError
        }

        // Try to find mock response for endpoint
        let key = endpoint.path
        if let mockResponse = mockResponses[key] as? T {
            return mockResponse
        }

        // Return mock data based on type
        return try mockDefaultResponse()
    }

    private func mockDefaultResponse<T: Decodable>() throws -> T {
        // swiftlint:disable force_cast
        // Note: Force casts are intentional in mock implementation for testing
        // Return default mock responses for common types
        if T.self == AuthResponse.self {
            return AuthResponse(
                accessToken: "mock_access_token",
                refreshToken: "mock_refresh_token",
                tokenType: "Bearer",
                user: User(
                    id: 1,
                    email: "test@example.com",
                    firstName: "Test",
                    lastName: "User",
                    createdAt: Date(),
                    lastLoginAt: Date(),
                    notificationEnabled: true,
                    birthYear: nil,
                    educationLevel: nil,
                    country: nil,
                    region: nil
                )
            ) as! T
        } else if T.self == User.self {
            return User(
                id: 1,
                email: "test@example.com",
                firstName: "Test",
                lastName: "User",
                createdAt: Date(),
                lastLoginAt: Date(),
                notificationEnabled: true,
                birthYear: nil,
                educationLevel: nil,
                country: nil,
                region: nil
            ) as! T
        } else if T.self == TestSession.self {
            return TestSession(
                id: 1,
                userId: 1,
                startedAt: Date(),
                completedAt: nil,
                status: .inProgress,
                questions: []
            ) as! T
        } else if T.self == [TestResult].self {
            return [] as! T
        }
        // swiftlint:enable force_cast

        throw APIError.decodingError(
            NSError(domain: "MockAPIClient", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "No mock response configured for type \(T.self)"
            ])
        )
    }

    /// Configure a mock response for a specific endpoint
    func setMockResponse(_ response: some Encodable, for endpoint: APIEndpoint) {
        mockResponses[endpoint.path] = response
    }

    /// Reset all mock responses
    func resetMocks() {
        mockResponses.removeAll()
        shouldFail = false
        mockError = APIError.unknown()
        mockDelay = 0.5
    }
}
