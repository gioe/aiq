import AIQAPIClient
import Foundation

#if DEBUG

    /// Mock OpenAPI service for UI tests
    ///
    /// This mock provides pre-configured responses for all API operations needed
    /// by UI tests. Responses are configured based on the current MockScenario.
    ///
    /// Unlike the unit test MockOpenAPIService (which is an actor), this mock is
    /// a simple class designed for synchronous UI test configuration.
    final class UITestMockOpenAPIService: OpenAPIServiceProtocol, @unchecked Sendable {
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

        // MARK: - Error Helper

        private func throwIfNetworkError() throws {
            if shouldSimulateNetworkError {
                throw APIError.networkError(
                    NSError(domain: NSURLErrorDomain, code: NSURLErrorNotConnectedToInternet)
                )
            }
        }

        // MARK: - Authentication

        func login(email _: String, password _: String) async throws -> AuthResponse {
            try throwIfNetworkError()
            return UITestMockData.mockAuthResponse
        }

        // swiftlint:disable:next function_parameter_count
        func register(
            email _: String,
            password _: String,
            firstName _: String,
            lastName _: String,
            birthYear _: Int?,
            educationLevel _: EducationLevel?,
            country _: String?,
            region _: String?
        ) async throws -> AuthResponse {
            try throwIfNetworkError()
            return UITestMockData.mockAuthResponse
        }

        func refreshToken() async throws -> AuthResponse {
            try throwIfNetworkError()
            return UITestMockData.mockAuthResponse
        }

        func logout() async throws {
            try throwIfNetworkError()
        }

        // MARK: - User Profile

        func getProfile() async throws -> User {
            try throwIfNetworkError()
            return UITestMockAuthManager.mockUser
        }

        func deleteAccount() async throws {
            try throwIfNetworkError()
        }

        // MARK: - Test Management

        func startTest() async throws -> StartTestResponse {
            try throwIfNetworkError()
            return StartTestResponse(
                questions: UITestMockData.sampleQuestions,
                session: UITestMockData.newSession,
                totalQuestions: UITestMockData.sampleQuestions.count
            )
        }

        func submitTest(
            sessionId _: Int,
            responses _: [QuestionResponse],
            timeLimitExceeded _: Bool
        ) async throws -> TestSubmitResponse {
            try throwIfNetworkError()
            return TestSubmitResponse(
                message: "Test completed successfully",
                responsesCount: UITestMockData.sampleQuestions.count,
                result: UITestMockData.highScoreResult,
                session: UITestMockData.completedSession
            )
        }

        func abandonTest(sessionId _: Int) async throws -> TestAbandonResponse {
            try throwIfNetworkError()
            return TestAbandonResponse(
                message: "Test abandoned",
                responsesSaved: 5,
                session: UITestMockData.abandonedSession
            )
        }

        func getTestSession(sessionId _: Int) async throws -> TestSessionStatusResponse {
            try throwIfNetworkError()
            return TestSessionStatusResponse(
                questions: UITestMockData.sampleQuestions,
                questionsCount: 0,
                session: UITestMockData.inProgressSession
            )
        }

        func getTestResults(resultId _: Int) async throws -> TestResult {
            try throwIfNetworkError()
            return UITestMockData.highScoreResult
        }

        func getTestHistory(limit _: Int?, offset _: Int?) async throws -> PaginatedTestHistoryResponse {
            try throwIfNetworkError()

            switch scenario {
            case .loggedInNoHistory, .loggedOut, .default, .registrationTimeout, .registrationServerError:
                return PaginatedTestHistoryResponse(
                    hasMore: false,
                    limit: 50,
                    offset: 0,
                    results: [],
                    totalCount: 0
                )
            case .loggedInWithHistory, .testInProgress, .loginFailure, .networkError:
                return PaginatedTestHistoryResponse(
                    hasMore: false,
                    limit: 50,
                    offset: 0,
                    results: UITestMockData.sampleTestHistory,
                    totalCount: UITestMockData.sampleTestHistory.count
                )
            }
        }

        func getActiveTest() async throws -> TestSessionStatusResponse? {
            try throwIfNetworkError()

            switch scenario {
            case .testInProgress:
                return TestSessionStatusResponse(
                    questions: UITestMockData.sampleQuestions,
                    questionsCount: 0,
                    session: UITestMockData.inProgressSession
                )
            default:
                return nil
            }
        }

        // MARK: - Adaptive Test Management

        func startAdaptiveTest() async throws -> StartTestResponse {
            try throwIfNetworkError()
            let firstQuestion = UITestMockData.sampleQuestions[0]
            return StartTestResponse(
                currentSe: 1.0,
                currentTheta: 0.0,
                questions: [firstQuestion],
                session: UITestMockData.newSession,
                totalQuestions: 1
            )
        }

        // swiftlint:disable:next line_length
        func submitAdaptiveResponse(sessionId _: Int, questionId _: Int, userAnswer _: String, timeSpentSeconds _: Int?) async throws -> Components.Schemas.AdaptiveNextResponse {
            try throwIfNetworkError()
            return Components.Schemas.AdaptiveNextResponse(
                currentSe: 0.5,
                currentTheta: 0.5,
                itemsAdministered: 2,
                nextQuestion: .init(value1: UITestMockData.sampleQuestions[1]),
                testComplete: false
            )
        }

        func getTestProgress(sessionId _: Int) async throws -> Components.Schemas.TestProgressResponse {
            try throwIfNetworkError()
            return Components.Schemas.TestProgressResponse(
                currentSe: 0.5,
                domainCoverage: .init(additionalProperties: ["logic": 1]),
                elapsedSeconds: 60,
                estimatedItemsRemaining: 13,
                itemsAdministered: 2,
                sessionId: 100,
                totalDomainsCovered: 1,
                totalItemsMax: 15
            )
        }

        // MARK: - Notifications

        func registerDevice(deviceToken _: String) async throws {
            try throwIfNetworkError()
        }

        func unregisterDevice() async throws {
            try throwIfNetworkError()
        }

        func updateNotificationPreferences(enabled _: Bool) async throws {
            try throwIfNetworkError()
        }

        func getNotificationPreferences() async throws -> Components.Schemas.NotificationPreferencesResponse {
            try throwIfNetworkError()
            return Components.Schemas.NotificationPreferencesResponse(
                message: "Preferences retrieved",
                notificationEnabled: true
            )
        }

        // MARK: - Feedback

        func submitFeedback(_: Feedback) async throws -> FeedbackSubmitResponse {
            try throwIfNetworkError()
            return FeedbackSubmitResponse(
                message: "Thank you for your feedback!",
                submissionId: 1,
                success: true
            )
        }

        // MARK: - Token Management

        func setTokens(accessToken _: String, refreshToken _: String) async {
            // No-op for UI tests - auth is handled by MockAuthManager
        }

        func clearTokens() async {
            // No-op for UI tests
        }
    }

    // MARK: - Mock Auth Response

    extension UITestMockData {
        static let mockAuthResponse = AuthResponse(
            accessToken: "mock-access-token",
            refreshToken: "mock-refresh-token",
            tokenType: "Bearer",
            user: UITestMockAuthManager.mockUser
        )
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
                difficultyLevel: "easy",
                answerOptions: ["Apple", "Banana", "Carrot", "Orange"]
            ),
            MockDataFactory.makeQuestion(
                id: 2,
                questionText: "What is 15% of 200?",
                questionType: "math",
                difficultyLevel: "easy",
                answerOptions: ["20", "25", "30", "35"]
            ),
            MockDataFactory.makeQuestion(
                id: 3,
                questionText: "What number comes next: 2, 4, 8, 16, ?",
                questionType: "pattern",
                difficultyLevel: "medium",
                answerOptions: ["18", "24", "32", "64"]
            ),
            MockDataFactory.makeQuestion(
                id: 4,
                questionText: "If all cats have whiskers, and Fluffy is a cat, what can we conclude?",
                questionType: "logic",
                difficultyLevel: "easy",
                answerOptions: ["Fluffy has whiskers", "Fluffy is a dog", "Whiskers are rare", "Cats are unique"]
            ),
            MockDataFactory.makeQuestion(
                id: 5,
                questionText: "Which shape completes the pattern?",
                questionType: "spatial",
                difficultyLevel: "medium",
                answerOptions: ["Circle", "Square", "Triangle", "Hexagon"]
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
