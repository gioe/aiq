import AIQAPIClientCore
import Foundation

#if DebugBuild

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

        /// Tracks the number of startTest() calls for failure-then-success scenarios
        private var startTestCallCount = 0

        init() {}

        /// Configure the mock for a specific test scenario
        func configureForScenario(_ scenario: MockScenario) {
            self.scenario = scenario
            shouldSimulateNetworkError = (scenario == .networkError)
        }

        // MARK: - Error Helper

        private func throwIfNetworkError() throws {
            if shouldSimulateNetworkError {
                throw APIError.api(.noInternetConnection)
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
            switch scenario {
            case .startTestNetworkFailure:
                throw APIError.api(.noInternetConnection)
            case .startTestNonRetryableFailure:
                throw APIError.api(.badRequest(message: "Questions not available."))
            case .startTestFailureThenSuccess:
                startTestCallCount += 1
                if startTestCallCount == 1 {
                    throw APIError.api(.noInternetConnection)
                }
                return StartTestResponse(
                    questions: UITestMockData.sampleQuestions,
                    session: UITestMockData.newSession,
                    totalQuestions: UITestMockData.sampleQuestions.count
                )
            default:
                try throwIfNetworkError()
                return StartTestResponse(
                    questions: UITestMockData.sampleQuestions,
                    session: UITestMockData.newSession,
                    totalQuestions: UITestMockData.sampleQuestions.count
                )
            }
        }

        func submitTest(
            sessionId _: Int,
            responses _: [QuestionResponse],
            timeLimitExceeded _: Bool
        ) async throws -> TestSubmitResponse {
            try throwIfNetworkError()
            let result: TestResult = switch scenario {
            case .timerExpiredWithAnswers:
                UITestMockData.lowScoreResult
            case .loggedInWithHistoryNilDate:
                UITestMockData.midScoreResult
            default:
                UITestMockData.highScoreResult
            }
            return TestSubmitResponse(
                message: "Test completed successfully",
                responsesCount: UITestMockData.sampleQuestions.count,
                result: result,
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
            switch scenario {
            case .timerExpiredZeroAnswers:
                return TestSessionStatusResponse(
                    questions: UITestMockData.sampleQuestions,
                    questionsCount: 0,
                    session: UITestMockData.expiredSession
                )
            case .timerExpiredWithAnswers:
                return TestSessionStatusResponse(
                    questions: UITestMockData.sampleQuestions,
                    questionsCount: 1,
                    session: UITestMockData.nearExpiredSession
                )
            default:
                let questions = scenario == .memoryInProgress
                    ? UITestMockData.sampleMemoryQuestions
                    : UITestMockData.sampleQuestions
                let session = UITestMockData.recentInProgressSession
                return TestSessionStatusResponse(
                    questions: questions,
                    questionsCount: 0,
                    session: session
                )
            }
        }

        func getTestResults(resultId _: Int) async throws -> TestResult {
            try throwIfNetworkError()
            return UITestMockData.highScoreResult
        }

        func getTestHistory(limit _: Int?, offset _: Int?) async throws -> PaginatedTestHistoryResponse {
            try throwIfNetworkError()

            switch scenario {
            case .loggedInNoHistory, .loggedOut, .default, .registrationTimeout, .registrationServerError,
                 .startTestNetworkFailure, .startTestFailureThenSuccess, .startTestNonRetryableFailure,
                 .timerExpiredZeroAnswers, .timerExpiredWithAnswers:
                return PaginatedTestHistoryResponse(
                    hasMore: false,
                    limit: 50,
                    offset: 0,
                    results: [],
                    totalCount: 0
                )
            case .loggedInWithHistory, .loggedInWithHistoryNilDate, .testInProgress, .loginFailure,
                 .networkError, .memoryInProgress, .notificationsDisabled:
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
                    session: UITestMockData.recentInProgressSession
                )
            case .memoryInProgress:
                return TestSessionStatusResponse(
                    questions: UITestMockData.sampleMemoryQuestions,
                    questionsCount: 0,
                    session: UITestMockData.recentInProgressSession
                )
            case .timerExpiredWithAnswers:
                return TestSessionStatusResponse(
                    questions: UITestMockData.sampleQuestions,
                    questionsCount: 1,
                    session: UITestMockData.nearExpiredSession
                )
            case .timerExpiredZeroAnswers:
                // Returns nil intentionally: this scenario exercises the silent abandonment path
                // where the timer fires before any answers are submitted. In production the server
                // would still have an in-progress session record, but the UI test only needs the
                // dashboard to show "Start Test" (no Resume button) — which happens when the server
                // returns no active session. LocalAnswerStorage drives the abandonment cleanup,
                // so no server-side session is needed for this test path.
                return nil
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

        // MARK: - Guest Test Management

        func startGuestTest(deviceId _: String) async throws -> Components.Schemas.GuestStartTestResponse {
            try throwIfNetworkError()
            return Components.Schemas.GuestStartTestResponse(
                guestToken: "mock-guest-token",
                questions: UITestMockData.sampleQuestions,
                session: UITestMockData.newSession,
                testsRemaining: 3,
                totalQuestions: UITestMockData.sampleQuestions.count
            )
        }

        func submitGuestTest(
            guestToken _: String,
            responses _: [QuestionResponse],
            timeLimitExceeded _: Bool
        ) async throws -> Components.Schemas.GuestSubmitTestResponse {
            try throwIfNetworkError()
            return Components.Schemas.GuestSubmitTestResponse(
                message: "Test submitted successfully",
                responsesCount: UITestMockData.sampleQuestions.count,
                result: UITestMockData.highScoreResult,
                session: UITestMockData.completedSession
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
            let enabled = scenario != .notificationsDisabled
            return Components.Schemas.NotificationPreferencesResponse(
                message: "Preferences retrieved",
                notificationEnabled: enabled
            )
        }

        // MARK: - Benchmarks

        func getBenchmarkSummary() async throws -> Components.Schemas.BenchmarkSummaryResponse {
            try throwIfNetworkError()
            let models: [Components.Schemas.ModelSummary] = switch scenario {
            case .loggedInWithHistory, .loggedInWithHistoryNilDate:
                MockDataFactory.sampleBenchmarkModels
            default:
                []
            }
            return Components.Schemas.BenchmarkSummaryResponse(
                cacheTtl: 600,
                minRuns: 3,
                models: models
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

        static let sampleMemoryQuestions: [Question] = [
            MockDataFactory.makeMemoryQuestion(
                id: 10,
                stimulus: "The sequence is: Red, Blue, Green, Yellow, Purple",
                questionText: "Which color appeared first in the sequence?",
                difficultyLevel: "medium",
                answerOptions: ["Red", "Blue", "Green", "Yellow"]
            )
        ]

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

        /// Session started 5 minutes ago — used for `testInProgress` and `memoryInProgress`
        /// so the 30-minute test timer does not expire immediately when `TestTakingView` loads.
        static let recentInProgressSession = MockDataFactory.makeTestSession(
            id: 99,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-300)
        )

        /// Session started 36 minutes ago — timer expires immediately when startWithSessionTime is called.
        /// Used for `timerExpiredZeroAnswers` scenario (0 answers → silent abandonment).
        static let expiredSession = MockDataFactory.makeTestSession(
            id: 98,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-Double(TestTimerManager.totalTimeSeconds + 60))
        )

        /// Session with ~20 seconds remaining — passes hasActiveTest on dashboard and fires
        /// the timer within 20 seconds when TestTakingView starts it.
        /// 20-second buffer ensures the Resume button appears even on slow CI runners before
        /// the timer fires. Used for `timerExpiredWithAnswers` (partial answers → Time's Up alert).
        ///
        /// Must satisfy DashboardViewModel.hasActiveTest: elapsed < totalTimeSeconds.
        /// Keep this buffer >= 10s to avoid CI race conditions on slow runners.
        static let nearExpiredSession = MockDataFactory.makeTestSession(
            id: 97,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-Double(TestTimerManager.totalTimeSeconds - 20))
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

        static let midScoreResult = MockDataFactory.makeTestResult(
            id: 6,
            testSessionId: 100,
            userId: 1,
            iqScore: 100,
            totalQuestions: 20,
            correctAnswers: 12,
            accuracyPercentage: 60.0,
            completedAt: Date()
        )

        static let lowScoreResult = MockDataFactory.makeTestResult(
            id: 7,
            testSessionId: 100,
            userId: 1,
            iqScore: 85,
            totalQuestions: 20,
            correctAnswers: 8,
            accuracyPercentage: 40.0,
            completedAt: Date()
        )
    }

#endif
