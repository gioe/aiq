import Foundation

#if DEBUG

    /// Mock API client for UI tests
    ///
    /// This mock provides pre-configured responses for all API endpoints needed
    /// by UI tests. Responses are configured based on the current MockScenario.
    ///
    /// Unlike the unit test MockAPIClient (which is an actor), this mock is
    /// a simple class designed for synchronous UI test configuration.
    final class UITestMockAPIClient: APIClientProtocol {
        /// Current scenario determining response behavior
        private var scenario: MockScenario = .default

        /// Whether to simulate network errors
        private var shouldSimulateNetworkError: Bool = false

        init() {}

        /// Configure the mock for a specific test scenario
        func configureForScenario(_ scenario: MockScenario) {
            self.scenario = scenario
            shouldSimulateNetworkError = (scenario == .networkError)
        }

        // MARK: - APIClientProtocol

        nonisolated func setAuthToken(_: String?) {
            // No-op for UI tests - auth is handled by MockAuthManager
        }

        // swiftlint:disable:next function_parameter_count
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
            print("[UITestMockAPIClient] Request: \(endpoint.path), expecting type: \(T.self)")

            // Simulate network delay
            try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

            if shouldSimulateNetworkError {
                print("[UITestMockAPIClient] Simulating network error")
                throw APIError.networkError(
                    NSError(domain: NSURLErrorDomain, code: NSURLErrorNotConnectedToInternet)
                )
            }

            // Route to appropriate mock response based on endpoint
            do {
                let response: T = try mockResponse(for: endpoint)
                print("[UITestMockAPIClient] Response success for: \(endpoint.path)")
                return response
            } catch {
                print("[UITestMockAPIClient] Error for \(endpoint.path): \(error)")
                throw error
            }
        }

        // MARK: - Mock Response Routing

        private func mockResponse<T: Decodable>(for endpoint: APIEndpoint) throws -> T {
            let path = endpoint.path

            // Test History endpoint
            if path.contains("/test/history") {
                return try castResponse(mockTestHistoryResponse())
            }

            // Test Active Session endpoint
            if path.contains("/test/active") {
                return try castResponse(mockActiveSessionResponse())
            }

            // Start Test endpoint
            if path.contains("/test/start") {
                return try castResponse(mockStartTestResponse())
            }

            // Get Questions endpoint
            if path.contains("/test/questions") || path.contains("/questions") {
                return try castResponse(mockQuestionsResponse())
            }

            // Submit Test endpoint
            if path.contains("/test/submit") || path.contains("/submit") {
                return try castResponse(mockSubmitTestResponse())
            }

            // Abandon Test endpoint
            if path.contains("/test/abandon") || path.contains("/abandon") {
                return try castResponse(mockAbandonTestResponse())
            }

            // User Profile endpoint
            if path.contains("/user/me") || path.contains("/user/profile") {
                return try castResponse(UITestMockAuthManager.mockUser)
            }

            // Default: throw error for unhandled endpoints
            throw APIError.decodingError(
                NSError(domain: "UITestMockAPIClient", code: -1, userInfo: [
                    NSLocalizedDescriptionKey: "No mock configured for endpoint: \(path)"
                ])
            )
        }

        // MARK: - Mock Response Builders

        private func mockTestHistoryResponse() -> PaginatedTestHistoryResponse {
            switch scenario {
            case .loggedInNoHistory, .loggedOut, .default, .registrationTimeout, .registrationServerError:
                PaginatedTestHistoryResponse(
                    hasMore: false,
                    limit: 50,
                    offset: 0,
                    results: [],
                    totalCount: 0
                )
            case .loggedInWithHistory, .testInProgress, .loginFailure, .networkError:
                PaginatedTestHistoryResponse(
                    hasMore: false,
                    limit: 50,
                    offset: 0,
                    results: UITestMockData.sampleTestHistory,
                    totalCount: UITestMockData.sampleTestHistory.count
                )
            }
        }

        private func mockActiveSessionResponse() -> TestSession? {
            switch scenario {
            case .testInProgress:
                UITestMockData.inProgressSession
            default:
                nil
            }
        }

        private func mockStartTestResponse() -> StartTestResponse {
            StartTestResponse(
                questions: UITestMockData.sampleQuestions,
                session: UITestMockData.newSession,
                totalQuestions: UITestMockData.sampleQuestions.count
            )
        }

        private func mockQuestionsResponse() -> [Question] {
            UITestMockData.sampleQuestions
        }

        private func mockSubmitTestResponse() -> TestSubmitResponse {
            TestSubmitResponse(
                message: "Test completed successfully",
                responsesCount: UITestMockData.sampleQuestions.count,
                result: UITestMockData.highScoreResult,
                session: UITestMockData.completedSession
            )
        }

        private func mockAbandonTestResponse() -> TestAbandonResponse {
            TestAbandonResponse(
                message: "Test abandoned",
                responsesSaved: 5,
                session: UITestMockData.abandonedSession
            )
        }

        // MARK: - Helpers

        private func castResponse<T: Decodable>(_ response: some Any) throws -> T {
            guard let typed = response as? T else {
                throw APIError.decodingError(
                    NSError(domain: "UITestMockAPIClient", code: -1, userInfo: [
                        NSLocalizedDescriptionKey: "Response type mismatch"
                    ])
                )
            }
            return typed
        }
    }

    // MARK: - Mock Data

    /// Factory for creating mock data for UI tests
    enum UITestMockData {
        // MARK: - Sample Questions

        static let sampleQuestions: [Question] = [
            MockDataFactory.makeQuestion(
                id: 1,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange?",
                questionType: "logic",
                difficultyLevel: "easy"
            ),
            MockDataFactory.makeQuestion(
                id: 2,
                questionText: "What is 15% of 200?",
                questionType: "math",
                difficultyLevel: "easy"
            ),
            MockDataFactory.makeQuestion(
                id: 3,
                questionText: "What number comes next: 2, 4, 8, 16, ?",
                questionType: "pattern",
                difficultyLevel: "medium"
            ),
            MockDataFactory.makeQuestion(
                id: 4,
                questionText: "If all cats have whiskers, and Fluffy is a cat, what can we conclude?",
                questionType: "logic",
                difficultyLevel: "easy"
            ),
            MockDataFactory.makeQuestion(
                id: 5,
                questionText: "Which shape completes the pattern?",
                questionType: "spatial",
                difficultyLevel: "medium"
            )
        ]

        // MARK: - Sample Test Results

        static let sampleTestHistory: [TestResult] = [
            MockDataFactory.makeTestResult(
                id: 1,
                testSessionId: 1,
                userId: 1,
                iqScore: 105,
                totalQuestions: 20,
                correctAnswers: 13,
                accuracyPercentage: 65.0,
                completedAt: Date().addingTimeInterval(-30 * 24 * 60 * 60)
            ),
            MockDataFactory.makeTestResult(
                id: 2,
                testSessionId: 2,
                userId: 1,
                iqScore: 112,
                totalQuestions: 20,
                correctAnswers: 15,
                accuracyPercentage: 75.0,
                completedAt: Date().addingTimeInterval(-20 * 24 * 60 * 60)
            ),
            MockDataFactory.makeTestResult(
                id: 3,
                testSessionId: 3,
                userId: 1,
                iqScore: 118,
                totalQuestions: 20,
                correctAnswers: 17,
                accuracyPercentage: 85.0,
                completedAt: Date().addingTimeInterval(-10 * 24 * 60 * 60)
            ),
            MockDataFactory.makeTestResult(
                id: 4,
                testSessionId: 4,
                userId: 1,
                iqScore: 125,
                totalQuestions: 20,
                correctAnswers: 18,
                accuracyPercentage: 90.0,
                completedAt: Date()
            )
        ]

        // MARK: - Sample Test Sessions

        static let newSession = MockDataFactory.makeTestSession(
            id: 100,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )

        static let inProgressSession = MockDataFactory.makeTestSession(
            id: 99,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-3600)
        )

        static let completedSession = MockDataFactory.makeTestSession(
            id: 100,
            userId: 1,
            status: "completed",
            startedAt: Date().addingTimeInterval(-1800)
        )

        static let abandonedSession = MockDataFactory.makeTestSession(
            id: 100,
            userId: 1,
            status: "abandoned",
            startedAt: Date().addingTimeInterval(-900)
        )

        // MARK: - Sample Submitted Result

        static let highScoreResult = MockDataFactory.makeTestResult(
            id: 5,
            testSessionId: 100,
            userId: 1,
            iqScore: 128,
            totalQuestions: 20,
            correctAnswers: 18,
            accuracyPercentage: 90.0,
            completedAt: Date()
        )
    }

#endif
