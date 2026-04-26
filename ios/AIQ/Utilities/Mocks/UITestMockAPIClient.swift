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

        func oauthApple(identityToken _: String, nonce _: String) async throws -> AuthResponse {
            try throwIfNetworkError()
            return UITestMockData.mockAuthResponse
        }

        func oauthGoogle(identityToken _: String) async throws -> AuthResponse {
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
                    session: UITestMockData.newSession,
                    questions: UITestMockData.sampleQuestions,
                    totalQuestions: UITestMockData.sampleQuestions.count
                )
            default:
                try throwIfNetworkError()
                return StartTestResponse(
                    session: UITestMockData.newSession,
                    questions: UITestMockData.sampleQuestions,
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
                session: UITestMockData.completedSession,
                result: result,
                responsesCount: UITestMockData.sampleQuestions.count,
                message: "Test completed successfully"
            )
        }

        func abandonTest(sessionId _: Int) async throws -> TestAbandonResponse {
            try throwIfNetworkError()
            return TestAbandonResponse(
                session: UITestMockData.abandonedSession,
                message: "Test abandoned",
                responsesSaved: 5
            )
        }

        func getTestSession(sessionId _: Int) async throws -> TestSessionStatusResponse {
            try throwIfNetworkError()
            switch scenario {
            case .timerExpiredZeroAnswers:
                return TestSessionStatusResponse(
                    session: UITestMockData.expiredSession,
                    questionsCount: 0
                )
            case .timerExpiredWithAnswers:
                return TestSessionStatusResponse(
                    session: UITestMockData.nearExpiredSession,
                    questionsCount: 1
                )
            case .timerNearWarning:
                return TestSessionStatusResponse(
                    session: UITestMockData.warningSession,
                    questionsCount: 0
                )
            default:
                let session = UITestMockData.recentInProgressSession
                return TestSessionStatusResponse(
                    session: session,
                    questionsCount: 0
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
                    results: [],
                    totalCount: 0,
                    limit: 50,
                    offset: 0,
                    hasMore: false
                )
            case .loggedInWithHistory, .loggedInWithHistoryNilDate, .testInProgress, .loginFailure,
                 .networkError, .memoryInProgress, .notificationsDisabled, .timerNearWarning:
                return PaginatedTestHistoryResponse(
                    results: UITestMockData.sampleTestHistory,
                    totalCount: UITestMockData.sampleTestHistory.count,
                    limit: 50,
                    offset: 0,
                    hasMore: false
                )
            }
        }

        func getActiveTest() async throws -> TestSessionStatusResponse? {
            try throwIfNetworkError()

            switch scenario {
            case .testInProgress:
                return TestSessionStatusResponse(
                    session: UITestMockData.recentInProgressSession,
                    questionsCount: 0
                )
            case .memoryInProgress:
                return TestSessionStatusResponse(
                    session: UITestMockData.recentInProgressSession,
                    questionsCount: 0
                )
            case .timerExpiredWithAnswers:
                return TestSessionStatusResponse(
                    session: UITestMockData.nearExpiredSession,
                    questionsCount: 1
                )
            case .timerExpiredZeroAnswers:
                // Returns nil intentionally: this scenario exercises the silent abandonment path
                // where the timer fires before any answers are submitted. In production the server
                // would still have an in-progress session record, but the UI test only needs the
                // dashboard to show "Start Test" (no Resume button) — which happens when the server
                // returns no active session. LocalAnswerStorage drives the abandonment cleanup,
                // so no server-side session is needed for this test path.
                return nil
            case .timerNearWarning:
                return TestSessionStatusResponse(
                    session: UITestMockData.warningSession,
                    questionsCount: 0
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
                session: UITestMockData.newSession,
                questions: [firstQuestion],
                totalQuestions: 1
            )
        }

        // swiftlint:disable:next line_length
        func submitAdaptiveResponse(sessionId _: Int, questionId _: Int, userAnswer _: String, timeSpentSeconds _: Int?) async throws -> Components.Schemas.AdaptiveNextResponse {
            try throwIfNetworkError()
            let nextQ = MockDataFactory.makeQuestion(
                id: 99,
                questionText: "What number comes next: 3, 6, 12, 24, ?",
                questionType: "pattern",
                difficultyLevel: "medium",
                answerOptions: ["30", "36", "48", "96"]
            )
            return Components.Schemas.AdaptiveNextResponse(
                nextQuestion: nextQ,
                currentTheta: 0.5,
                currentSe: 0.5,
                itemsAdministered: 2,
                testComplete: false
            )
        }

        func getTestProgress(sessionId _: Int) async throws -> Components.Schemas.TestProgressResponse {
            try throwIfNetworkError()
            return Components.Schemas.TestProgressResponse(
                sessionId: 100,
                itemsAdministered: 2,
                totalItemsMax: 15,
                estimatedItemsRemaining: 13,
                domainCoverage: .init(additionalProperties: ["logic": 1]),
                totalDomainsCovered: 1,
                elapsedSeconds: 60,
                currentSe: 0.5
            )
        }

        // MARK: - Guest Test Management

        func startGuestTest(deviceId _: String) async throws -> Components.Schemas.GuestStartTestResponse {
            try throwIfNetworkError()
            return Components.Schemas.GuestStartTestResponse(
                session: UITestMockData.newSession,
                questions: UITestMockData.sampleQuestions,
                totalQuestions: UITestMockData.sampleQuestions.count,
                guestToken: "mock-guest-token",
                testsRemaining: 3
            )
        }

        func submitGuestTest(
            guestToken _: String,
            responses _: [QuestionResponse],
            timeLimitExceeded _: Bool
        ) async throws -> Components.Schemas.GuestSubmitTestResponse {
            try throwIfNetworkError()
            return Components.Schemas.GuestSubmitTestResponse(
                session: UITestMockData.completedSession,
                result: UITestMockData.highScoreResult,
                responsesCount: UITestMockData.sampleQuestions.count,
                message: "Test submitted successfully"
            )
        }

        func submitGuestTestForClaim(
            guestToken _: String,
            responses _: [QuestionResponse],
            timeLimitExceeded _: Bool
        ) async throws -> GuestSubmitClaimResponse {
            try throwIfNetworkError()
            return GuestSubmitClaimResponse(
                session: UITestMockData.completedSession,
                result: UITestMockData.highScoreResult,
                responsesCount: UITestMockData.sampleQuestions.count,
                message: "Test submitted successfully",
                claimToken: "mock-guest-claim-token"
            )
        }

        func claimGuestResult(claimToken _: String) async throws -> GuestClaimResponse {
            try throwIfNetworkError()
            return GuestClaimResponse(
                session: UITestMockData.completedSession,
                result: UITestMockData.highScoreResult,
                responsesCount: UITestMockData.sampleQuestions.count,
                message: "Guest result claimed successfully."
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
                notificationEnabled: enabled,
                message: "Preferences retrieved"
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
                models: models,
                minRuns: 3,
                cacheTtl: 600
            )
        }

        // MARK: - Feedback

        func submitFeedback(_: Feedback) async throws -> FeedbackSubmitResponse {
            try throwIfNetworkError()
            return FeedbackSubmitResponse(
                success: true,
                submissionId: 1,
                message: "Thank you for your feedback!"
            )
        }

        // MARK: - Groups

        func listGroups() async throws -> [Components.Schemas.GroupResponse] {
            switch scenario {
            case .loggedInWithHistory:
                UITestMockData.sampleGroups
            default:
                []
            }
        }

        func createGroup(name _: String) async throws -> Components.Schemas.GroupResponse {
            throw APIError.api(.notFound(message: "Not implemented in UI tests"))
        }

        func getGroup(groupId _: Int) async throws -> Components.Schemas.GroupDetailResponse {
            switch scenario {
            case .loggedInWithHistory:
                return UITestMockData.sampleGroupDetail
            default:
                throw APIError.api(.notFound(message: "Not implemented in UI tests"))
            }
        }

        func deleteGroup(groupId _: Int) async throws {}
        func joinGroup(inviteCode _: String) async throws -> Components.Schemas.GroupResponse {
            throw APIError.api(.notFound(message: "Not implemented in UI tests"))
        }

        func generateInvite(groupId _: Int) async throws -> Components.Schemas.GroupInviteResponse {
            throw APIError.api(.notFound(message: "Not implemented in UI tests"))
        }

        func getLeaderboard(groupId _: Int) async throws -> Components.Schemas.LeaderboardResponse {
            switch scenario {
            case .loggedInWithHistory:
                return UITestMockData.sampleLeaderboard
            default:
                throw APIError.api(.notFound(message: "Not implemented in UI tests"))
            }
        }

        func removeMember(groupId _: Int, userId _: Int) async throws {}

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

        /// Session with ~4 minutes remaining — within the 5-minute warning threshold.
        /// Used for `timerNearWarning` scenario to trigger the warning banner immediately on load.
        /// 240-second buffer keeps the session valid (elapsed < totalTimeSeconds) so
        /// `DashboardViewModel.hasActiveTest` returns `true` and the Resume button is shown.
        static let warningSession = MockDataFactory.makeTestSession(
            id: 96,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-Double(TestTimerManager.totalTimeSeconds - 240))
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

        // MARK: - Sample Groups

        static let sampleGroupMembers: [Components.Schemas.GroupMemberResponse] = [
            Components.Schemas.GroupMemberResponse(
                userId: 1,
                firstName: "You",
                role: "owner",
                joinedAt: Date().addingTimeInterval(-30 * 24 * 60 * 60)
            ),
            Components.Schemas.GroupMemberResponse(
                userId: 2,
                firstName: "Alex",
                role: "member",
                joinedAt: Date().addingTimeInterval(-25 * 24 * 60 * 60)
            ),
            Components.Schemas.GroupMemberResponse(
                userId: 3,
                firstName: "Jordan",
                role: "member",
                joinedAt: Date().addingTimeInterval(-20 * 24 * 60 * 60)
            ),
            Components.Schemas.GroupMemberResponse(
                userId: 4,
                firstName: "Sam",
                role: "member",
                joinedAt: Date().addingTimeInterval(-15 * 24 * 60 * 60)
            )
        ]

        static let sampleGroups: [Components.Schemas.GroupResponse] = [
            Components.Schemas.GroupResponse(
                id: 1,
                name: "Brain Trust",
                createdBy: 1,
                createdAt: Date().addingTimeInterval(-30 * 24 * 60 * 60),
                inviteCode: "AIQ-BRAIN",
                maxMembers: 10,
                memberCount: 4
            ),
            Components.Schemas.GroupResponse(
                id: 2,
                name: "Study Group",
                createdBy: 2,
                createdAt: Date().addingTimeInterval(-14 * 24 * 60 * 60),
                inviteCode: "AIQ-STUDY",
                maxMembers: 20,
                memberCount: 2
            )
        ]

        static let sampleGroupDetail = Components.Schemas.GroupDetailResponse(
            id: 1,
            name: "Brain Trust",
            createdBy: 1,
            createdAt: Date().addingTimeInterval(-30 * 24 * 60 * 60),
            inviteCode: "AIQ-BRAIN",
            maxMembers: 10,
            memberCount: 4,
            members: sampleGroupMembers
        )

        static let sampleLeaderboard = Components.Schemas.LeaderboardResponse(
            groupId: 1,
            groupName: "Brain Trust",
            entries: [
                Components.Schemas.LeaderboardEntryResponse(
                    rank: 1,
                    userId: 1,
                    firstName: "You",
                    bestScore: 130,
                    averageScore: 122.5
                ),
                Components.Schemas.LeaderboardEntryResponse(
                    rank: 2,
                    userId: 2,
                    firstName: "Alex",
                    bestScore: 125,
                    averageScore: 118.0
                ),
                Components.Schemas.LeaderboardEntryResponse(
                    rank: 3,
                    userId: 3,
                    firstName: "Jordan",
                    bestScore: 119,
                    averageScore: 112.0
                ),
                Components.Schemas.LeaderboardEntryResponse(
                    rank: 4,
                    userId: 4,
                    firstName: "Sam",
                    bestScore: 112,
                    averageScore: 105.5
                )
            ],
            totalCount: 4
        )
    }

#endif
