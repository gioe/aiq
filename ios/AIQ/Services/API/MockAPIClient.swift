import Foundation
import os

/// Mock API client for UI testing that provides canned responses without network calls
///
/// This mock client is activated via the `--uitesting` launch argument and provides
/// realistic responses for all API endpoints used in the test-taking flow.
///
/// Usage in UI tests:
/// ```swift
/// // In BaseUITest.setupLaunchConfiguration():
/// app.launchArguments = ["--uitesting"]
/// ```
class MockAPIClient: APIClientProtocol {
    private var authToken: String?
    private var mockQuestions: [Question] = []
    private var mockTestSession: TestSession?
    private var mockTestResult: SubmittedTestResult?
    private let logger = Logger(subsystem: "com.aiq.app", category: "MockAPIClient")

    init() {
        logger.notice("MockAPIClient initialized")
        setupMockData()
    }

    func setAuthToken(_ token: String?) {
        authToken = token
    }

    // swiftlint:disable:next function_parameter_count cyclomatic_complexity function_body_length
    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method _: HTTPMethod,
        body _: Encodable?,
        requiresAuth _: Bool,
        customHeaders _: [String: String]?,
        cacheKey _: String?,
        cacheDuration _: TimeInterval?,
        forceRefresh _: Bool
    ) async throws -> T {
        // Simulate network delay for realism
        try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

        #if DEBUG
            print("🧪 [MockAPIClient] Handling request to \(endpoint)")
        #endif

        // Mock responses based on endpoint
        switch endpoint {
        case .login:
            logger.notice("🧪 Returning mock login response")
            guard let response = mockLoginResponse() as? T else {
                logger.error("Failed to cast login response to expected type")
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            logger.notice("🧪 Mock login response created successfully")
            return response

        case .register:
            guard let response = mockRegisterResponse() as? T else {
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            return response

        case .logout:
            guard let response = mockLogoutResponse() as? T else {
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            return response

        case .testStart:
            logger.notice("🧪 Handling testStart endpoint")
            guard let response = mockTestStartResponse() as? T else {
                logger.error("🧪 Failed to cast testStart response to expected type \(T.self)")
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            logger.notice("🧪 Returning mock testStart response with \(mockQuestions.count) questions")
            return response

        case .testSubmit:
            guard let response = mockTestSubmitResponse() as? T else {
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            return response

        case .testAbandon:
            guard let response = mockTestAbandonResponse() as? T else {
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            return response

        case .testHistory:
            guard let response = mockTestHistoryResponse() as? T else {
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            return response

        case .testActive:
            // Return 404 to simulate "no active session"
            // The ViewModel expects this and treats it as nil (optional response)
            logger.notice("🧪 Returning 404 for testActive (no active session)")
            throw APIError.notFound(message: "No active test session")

        case .userProfile:
            guard let response = mockUserProfileResponse() as? T else {
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            return response

        case .notificationPreferences:
            guard let response = mockNotificationPreferencesResponse() as? T else {
                throw APIError.decodingError(NSError(domain: "MockAPIClient", code: -1))
            }
            return response

        default:
            // For endpoints not needed in test-taking flow, return a simple success response
            #if DEBUG
                print("⚠️ [MockAPIClient] Unhandled endpoint: \(endpoint)")
            #endif
            // Try to return EmptyResponse for Void returns, otherwise throw
            if T.self == EmptyResponse.self {
                // swiftlint:disable:next force_cast
                return EmptyResponse() as! T
            }
            throw APIError.notFound(message: "Mock endpoint not implemented: \(endpoint)")
        }
    }

    // MARK: - Mock Data Setup

    private func setupMockData() {
        // Setup mock questions using the same pattern as TestTakingViewModel+MockData
        // swiftlint:disable force_try
        mockQuestions = [
            try! Question(
                id: 1,
                questionText: "What number comes next in this sequence: 2, 4, 8, 16, ?",
                questionType: .pattern,
                difficultyLevel: .easy,
                answerOptions: ["24", "28", "32", "64"],
                explanation: "The pattern is doubling: 2×2=4, 4×2=8, 8×2=16, 16×2=32"
            ),
            try! Question(
                id: 2,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange",
                questionType: .logic,
                difficultyLevel: .easy,
                answerOptions: ["Apple", "Banana", "Carrot", "Orange"],
                explanation: "Carrot is a vegetable, while the others are fruits"
            ),
            try! Question(
                id: 3,
                questionText: "If all roses are flowers and some flowers fade quickly, then:",
                questionType: .logic,
                difficultyLevel: .medium,
                answerOptions: [
                    "All roses fade quickly",
                    "Some roses might fade quickly",
                    "No roses fade quickly",
                    "Cannot be determined"
                ],
                explanation: "We can only conclude that some roses might fade quickly"
            ),
            try! Question(
                id: 4,
                questionText: "What is 15% of 200?",
                questionType: .math,
                difficultyLevel: .easy,
                answerOptions: ["25", "30", "35", "40"],
                explanation: "15% of 200 = 0.15 × 200 = 30"
            ),
            try! Question(
                id: 5,
                questionText: "Find the missing letter in the sequence: A, C, F, J, O, ?",
                questionType: .pattern,
                difficultyLevel: .medium,
                answerOptions: ["P", "Q", "T", "U"],
                explanation: "The gaps increase by 1 each time: +1, +2, +3, +4, +5 → U"
            )
        ]
        // swiftlint:enable force_try
    }

    // MARK: - Mock Response Generators

    private func mockLoginResponse() -> AuthResponse {
        AuthResponse(
            accessToken: "mock_access_token_\(UUID().uuidString)",
            refreshToken: "mock_refresh_token_\(UUID().uuidString)",
            tokenType: "Bearer",
            user: mockUser()
        )
    }

    private func mockRegisterResponse() -> AuthResponse {
        mockLoginResponse()
    }

    private func mockLogoutResponse() -> EmptyResponse {
        EmptyResponse()
    }

    private func mockTestStartResponse() -> StartTestResponse {
        let session = TestSession(
            id: 1,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: mockQuestions,
            timeLimitExceeded: false
        )
        mockTestSession = session

        return StartTestResponse(
            session: session,
            questions: mockQuestions,
            totalQuestions: mockQuestions.count
        )
    }

    private func mockTestSubmitResponse() -> TestSubmitResponse {
        let result = SubmittedTestResult(
            id: 1,
            testSessionId: 1,
            userId: 1,
            iqScore: 115,
            percentileRank: 84.0,
            totalQuestions: mockQuestions.count,
            correctAnswers: 4,
            accuracyPercentage: 80.0,
            completionTimeSeconds: 180,
            completedAt: Date(),
            responseTimeFlags: nil,
            domainScores: nil,
            strongestDomain: "Logic",
            weakestDomain: "Pattern",
            confidenceInterval: nil
        )
        mockTestResult = result

        let completedSession = TestSession(
            id: 1,
            userId: 1,
            startedAt: mockTestSession?.startedAt ?? Date().addingTimeInterval(-300),
            completedAt: Date(),
            status: .completed,
            questions: mockQuestions,
            timeLimitExceeded: false
        )

        return TestSubmitResponse(
            session: completedSession,
            result: result,
            responsesCount: mockQuestions.count,
            message: "Test submitted successfully"
        )
    }

    private func mockTestAbandonResponse() -> TestAbandonResponse {
        let abandonedSession = TestSession(
            id: 1,
            userId: 1,
            startedAt: mockTestSession?.startedAt ?? Date().addingTimeInterval(-300),
            completedAt: Date(),
            status: .abandoned,
            questions: mockQuestions,
            timeLimitExceeded: false
        )

        return TestAbandonResponse(
            session: abandonedSession,
            message: "Test session abandoned",
            responsesSaved: 2
        )
    }

    private func mockTestHistoryResponse() -> PaginatedTestHistoryResponse {
        // Return empty history for UI tests (tests can verify new test appears after completion)
        PaginatedTestHistoryResponse(
            results: [],
            totalCount: 0,
            limit: 10,
            offset: 0,
            hasMore: false
        )
    }

    private func mockUserProfileResponse() -> User {
        mockUser()
    }

    private func mockNotificationPreferencesResponse() -> NotificationPreferencesResponse {
        NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Notification preferences retrieved"
        )
    }

    private func mockUser() -> User {
        User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date().addingTimeInterval(-86400 * 30), // 30 days ago
            lastLoginAt: Date(),
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
    }
}

// MARK: - Supporting Types

/// Empty response for endpoints that don't return data
struct EmptyResponse: Codable {}
