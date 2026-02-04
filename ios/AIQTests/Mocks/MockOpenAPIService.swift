@testable import AIQ
import AIQAPIClient
import Foundation

/// Mock implementation of OpenAPIServiceProtocol for testing
///
/// Uses a class (not actor) for simpler test ergonomics. Tests run sequentially
/// within a test class, so actor isolation is unnecessary overhead.
final class MockOpenAPIService: OpenAPIServiceProtocol, @unchecked Sendable {
    // MARK: - Call Tracking

    private(set) var loginCalled = false
    private(set) var registerCalled = false
    private(set) var refreshTokenCalled = false
    private(set) var logoutCalled = false
    private(set) var getProfileCalled = false
    private(set) var deleteAccountCalled = false
    private(set) var startTestCalled = false
    private(set) var submitTestCalled = false
    private(set) var abandonTestCalled = false
    private(set) var getTestSessionCalled = false
    private(set) var getTestResultsCalled = false
    private(set) var getTestHistoryCalled = false
    private(set) var getActiveTestCalled = false
    private(set) var startAdaptiveTestCalled = false
    private(set) var submitAdaptiveResponseCalled = false
    private(set) var getTestProgressCalled = false
    private(set) var registerDeviceCalled = false
    private(set) var unregisterDeviceCalled = false
    private(set) var updateNotificationPreferencesCalled = false
    private(set) var getNotificationPreferencesCalled = false
    private(set) var submitFeedbackCalled = false
    private(set) var setTokensCalled = false
    private(set) var clearTokensCalled = false

    // MARK: - Parameter Capture

    private(set) var lastLoginEmail: String?
    private(set) var lastLoginPassword: String?
    private(set) var lastRegisterEmail: String?
    private(set) var lastRegisterPassword: String?
    private(set) var lastRegisterFirstName: String?
    private(set) var lastRegisterLastName: String?
    private(set) var lastSubmitTestSessionId: Int?
    private(set) var lastSubmitTestResponses: [QuestionResponse]?
    private(set) var lastSubmitTestTimeLimitExceeded: Bool?
    private(set) var lastAbandonTestSessionId: Int?
    private(set) var lastGetTestSessionId: Int?
    private(set) var lastGetTestResultsId: Int?
    private(set) var lastGetTestHistoryLimit: Int?
    private(set) var lastGetTestHistoryOffset: Int?
    private(set) var lastRegisterDeviceToken: String?
    private(set) var lastUpdateNotificationPreferencesEnabled: Bool?
    private(set) var lastFeedback: Feedback?
    private(set) var lastAccessToken: String?
    private(set) var lastRefreshToken: String?
    private(set) var lastAdaptiveResponseSessionId: Int?
    private(set) var lastAdaptiveResponseQuestionId: Int?
    private(set) var lastAdaptiveResponseUserAnswer: String?
    private(set) var lastAdaptiveResponseTimeSpent: Int?
    private(set) var lastGetTestProgressSessionId: Int?

    // MARK: - Call Counts

    private(set) var getTestHistoryCallCount = 0
    private(set) var abandonTestCallCount = 0

    // MARK: - Response Stubs

    var loginResponse: AuthResponse?
    var loginError: Error?
    var registerResponse: AuthResponse?
    var registerError: Error?
    var refreshTokenResponse: AuthResponse?
    var refreshTokenError: Error?
    var logoutError: Error?
    var getProfileResponse: User?
    var getProfileError: Error?
    var deleteAccountError: Error?
    var startTestResponse: StartTestResponse?
    var startTestError: Error?
    var submitTestResponse: TestSubmitResponse?
    var submitTestError: Error?
    var abandonTestResponse: TestAbandonResponse?
    var abandonTestError: Error?
    var getTestSessionResponse: TestSessionStatusResponse?
    var getTestSessionError: Error?
    var getTestResultsResponse: TestResult?
    var getTestResultsError: Error?
    var getTestHistoryResponse: PaginatedTestHistoryResponse?
    var getTestHistoryError: Error?
    var getActiveTestResponse: TestSessionStatusResponse?
    var getActiveTestError: Error?
    var startAdaptiveTestResponse: StartTestResponse?
    var startAdaptiveTestError: Error?
    var submitAdaptiveResponseResponse: Components.Schemas.AdaptiveNextResponse?
    var submitAdaptiveResponseError: Error?
    var getTestProgressResponse: Components.Schemas.TestProgressResponse?
    var getTestProgressError: Error?
    var registerDeviceError: Error?
    var unregisterDeviceError: Error?
    var updateNotificationPreferencesError: Error?
    var getNotificationPreferencesResponse: Components.Schemas.NotificationPreferencesResponse?
    var getNotificationPreferencesError: Error?
    var submitFeedbackResponse: FeedbackSubmitResponse?
    var submitFeedbackError: Error?

    // MARK: - Initialization

    init() {}

    // MARK: - Authentication

    func login(email: String, password: String) async throws -> AuthResponse {
        loginCalled = true
        lastLoginEmail = email
        lastLoginPassword = password
        if let error = loginError { throw error }
        guard let response = loginResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "loginResponse not configured"
            ])
        }
        return response
    }

    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear _: Int?,
        educationLevel _: EducationLevel?,
        country _: String?,
        region _: String?
    ) async throws -> AuthResponse {
        registerCalled = true
        lastRegisterEmail = email
        lastRegisterPassword = password
        lastRegisterFirstName = firstName
        lastRegisterLastName = lastName
        if let error = registerError { throw error }
        guard let response = registerResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "registerResponse not configured"
            ])
        }
        return response
    }

    func refreshToken() async throws -> AuthResponse {
        refreshTokenCalled = true
        if let error = refreshTokenError { throw error }
        guard let response = refreshTokenResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "refreshTokenResponse not configured"
            ])
        }
        return response
    }

    func logout() async throws {
        logoutCalled = true
        if let error = logoutError { throw error }
    }

    // MARK: - User Profile

    func getProfile() async throws -> User {
        getProfileCalled = true
        if let error = getProfileError { throw error }
        guard let response = getProfileResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "getProfileResponse not configured"
            ])
        }
        return response
    }

    func deleteAccount() async throws {
        deleteAccountCalled = true
        if let error = deleteAccountError { throw error }
    }

    // MARK: - Test Management

    func startTest() async throws -> StartTestResponse {
        startTestCalled = true
        if let error = startTestError { throw error }
        guard let response = startTestResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "startTestResponse not configured"
            ])
        }
        return response
    }

    func submitTest(
        sessionId: Int,
        responses: [QuestionResponse],
        timeLimitExceeded: Bool
    ) async throws -> TestSubmitResponse {
        submitTestCalled = true
        lastSubmitTestSessionId = sessionId
        lastSubmitTestResponses = responses
        lastSubmitTestTimeLimitExceeded = timeLimitExceeded
        if let error = submitTestError { throw error }
        guard let response = submitTestResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "submitTestResponse not configured"
            ])
        }
        return response
    }

    func abandonTest(sessionId: Int) async throws -> TestAbandonResponse {
        abandonTestCalled = true
        abandonTestCallCount += 1
        lastAbandonTestSessionId = sessionId
        if let error = abandonTestError { throw error }
        guard let response = abandonTestResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "abandonTestResponse not configured"
            ])
        }
        return response
    }

    func getTestSession(sessionId: Int) async throws -> TestSessionStatusResponse {
        getTestSessionCalled = true
        lastGetTestSessionId = sessionId
        if let error = getTestSessionError { throw error }
        guard let response = getTestSessionResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "getTestSessionResponse not configured"
            ])
        }
        return response
    }

    func getTestResults(resultId: Int) async throws -> TestResult {
        getTestResultsCalled = true
        lastGetTestResultsId = resultId
        if let error = getTestResultsError { throw error }
        guard let response = getTestResultsResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "getTestResultsResponse not configured"
            ])
        }
        return response
    }

    func getTestHistory(limit: Int?, offset: Int?) async throws -> PaginatedTestHistoryResponse {
        getTestHistoryCalled = true
        getTestHistoryCallCount += 1
        lastGetTestHistoryLimit = limit
        lastGetTestHistoryOffset = offset
        if let error = getTestHistoryError { throw error }
        guard let response = getTestHistoryResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "getTestHistoryResponse not configured"
            ])
        }
        return response
    }

    func getActiveTest() async throws -> TestSessionStatusResponse? {
        getActiveTestCalled = true
        if let error = getActiveTestError { throw error }
        return getActiveTestResponse
    }

    func startAdaptiveTest() async throws -> StartTestResponse {
        startAdaptiveTestCalled = true
        if let error = startAdaptiveTestError { throw error }
        guard let response = startAdaptiveTestResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "startAdaptiveTestResponse not configured"
            ])
        }
        return response
    }

    // swiftlint:disable:next line_length
    func submitAdaptiveResponse(sessionId: Int, questionId: Int, userAnswer: String, timeSpentSeconds: Int?) async throws -> Components.Schemas.AdaptiveNextResponse {
        submitAdaptiveResponseCalled = true
        lastAdaptiveResponseSessionId = sessionId
        lastAdaptiveResponseQuestionId = questionId
        lastAdaptiveResponseUserAnswer = userAnswer
        lastAdaptiveResponseTimeSpent = timeSpentSeconds
        if let error = submitAdaptiveResponseError { throw error }
        guard let response = submitAdaptiveResponseResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "submitAdaptiveResponseResponse not configured"
            ])
        }
        return response
    }

    func getTestProgress(sessionId: Int) async throws -> Components.Schemas.TestProgressResponse {
        getTestProgressCalled = true
        lastGetTestProgressSessionId = sessionId
        if let error = getTestProgressError { throw error }
        guard let response = getTestProgressResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "getTestProgressResponse not configured"
            ])
        }
        return response
    }

    // MARK: - Notifications

    func registerDevice(deviceToken: String) async throws {
        registerDeviceCalled = true
        lastRegisterDeviceToken = deviceToken
        if let error = registerDeviceError { throw error }
    }

    func unregisterDevice() async throws {
        unregisterDeviceCalled = true
        if let error = unregisterDeviceError { throw error }
    }

    func updateNotificationPreferences(enabled: Bool) async throws {
        updateNotificationPreferencesCalled = true
        lastUpdateNotificationPreferencesEnabled = enabled
        if let error = updateNotificationPreferencesError { throw error }
    }

    func getNotificationPreferences() async throws -> Components.Schemas.NotificationPreferencesResponse {
        getNotificationPreferencesCalled = true
        if let error = getNotificationPreferencesError { throw error }
        guard let response = getNotificationPreferencesResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "getNotificationPreferencesResponse not configured"
            ])
        }
        return response
    }

    // MARK: - Feedback

    func submitFeedback(_ feedback: Feedback) async throws -> FeedbackSubmitResponse {
        submitFeedbackCalled = true
        lastFeedback = feedback
        if let error = submitFeedbackError { throw error }
        guard let response = submitFeedbackResponse else {
            throw NSError(domain: "MockOpenAPIService", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "submitFeedbackResponse not configured"
            ])
        }
        return response
    }

    // MARK: - Token Management

    func setTokens(accessToken: String, refreshToken: String) async {
        setTokensCalled = true
        lastAccessToken = accessToken
        lastRefreshToken = refreshToken
    }

    func clearTokens() async {
        clearTokensCalled = true
    }

    // MARK: - Convenience Helpers

    /// Set test history response with a simple array of results
    func setTestHistoryResponse(_ results: [TestResult], totalCount: Int? = nil, hasMore: Bool = false) {
        getTestHistoryResponse = PaginatedTestHistoryResponse(
            hasMore: hasMore,
            limit: 50,
            offset: 0,
            results: results,
            totalCount: totalCount ?? results.count
        )
    }

    /// Reset all tracking state
    func reset() {
        loginCalled = false
        registerCalled = false
        refreshTokenCalled = false
        logoutCalled = false
        getProfileCalled = false
        deleteAccountCalled = false
        startTestCalled = false
        submitTestCalled = false
        abandonTestCalled = false
        getTestSessionCalled = false
        getTestResultsCalled = false
        getTestHistoryCalled = false
        getActiveTestCalled = false
        startAdaptiveTestCalled = false
        submitAdaptiveResponseCalled = false
        getTestProgressCalled = false
        registerDeviceCalled = false
        unregisterDeviceCalled = false
        updateNotificationPreferencesCalled = false
        getNotificationPreferencesCalled = false
        submitFeedbackCalled = false
        setTokensCalled = false
        clearTokensCalled = false

        lastLoginEmail = nil
        lastLoginPassword = nil
        lastRegisterEmail = nil
        lastRegisterPassword = nil
        lastRegisterFirstName = nil
        lastRegisterLastName = nil
        lastSubmitTestSessionId = nil
        lastSubmitTestResponses = nil
        lastSubmitTestTimeLimitExceeded = nil
        lastAbandonTestSessionId = nil
        lastGetTestSessionId = nil
        lastGetTestResultsId = nil
        lastGetTestHistoryLimit = nil
        lastGetTestHistoryOffset = nil
        lastRegisterDeviceToken = nil
        lastUpdateNotificationPreferencesEnabled = nil
        lastFeedback = nil
        lastAccessToken = nil
        lastRefreshToken = nil
        lastAdaptiveResponseSessionId = nil
        lastAdaptiveResponseQuestionId = nil
        lastAdaptiveResponseUserAnswer = nil
        lastAdaptiveResponseTimeSpent = nil
        lastGetTestProgressSessionId = nil

        getTestHistoryCallCount = 0
        abandonTestCallCount = 0

        loginResponse = nil
        loginError = nil
        registerResponse = nil
        registerError = nil
        refreshTokenResponse = nil
        refreshTokenError = nil
        logoutError = nil
        getProfileResponse = nil
        getProfileError = nil
        deleteAccountError = nil
        startTestResponse = nil
        startTestError = nil
        submitTestResponse = nil
        submitTestError = nil
        abandonTestResponse = nil
        abandonTestError = nil
        getTestSessionResponse = nil
        getTestSessionError = nil
        getTestResultsResponse = nil
        getTestResultsError = nil
        getTestHistoryResponse = nil
        getTestHistoryError = nil
        getActiveTestResponse = nil
        getActiveTestError = nil
        startAdaptiveTestResponse = nil
        startAdaptiveTestError = nil
        submitAdaptiveResponseResponse = nil
        submitAdaptiveResponseError = nil
        getTestProgressResponse = nil
        getTestProgressError = nil
        registerDeviceError = nil
        unregisterDeviceError = nil
        updateNotificationPreferencesError = nil
        getNotificationPreferencesResponse = nil
        getNotificationPreferencesError = nil
        submitFeedbackResponse = nil
        submitFeedbackError = nil
    }
}
