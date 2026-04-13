// swiftlint:disable file_length
import AIQAPIClientCore
import Foundation
import HTTPTypes
import OpenAPIRuntime

// MARK: - Protocol

/// Protocol for the OpenAPI service layer
///
/// This protocol wraps the generated OpenAPI client and provides a clean,
/// typed interface for API operations. It handles:
/// - Token management via AuthenticationMiddleware
/// - Error mapping from OpenAPI responses to APIError
/// - Response unwrapping and type conversion
///
/// Note: This service uses the generated OpenAPI types directly (Components.Schemas.*).
/// For backward compatibility with existing code using manual types, callers may need
/// to convert between the generated types and the legacy manual types.
protocol OpenAPIServiceProtocol: Sendable {
    // MARK: - Authentication

    func login(email: String, password: String) async throws -> AuthResponse
    // swiftlint:disable:next function_parameter_count
    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear: Int?,
        educationLevel: EducationLevel?,
        country: String?,
        region: String?
    ) async throws -> AuthResponse
    func refreshToken() async throws -> AuthResponse
    func logout() async throws

    // MARK: - User Profile

    func getProfile() async throws -> User
    func deleteAccount() async throws

    // MARK: - Test Management

    func startTest() async throws -> Components.Schemas.StartTestResponse
    // swiftlint:disable:next line_length
    func submitTest(sessionId: Int, responses: [QuestionResponse], timeLimitExceeded: Bool) async throws -> Components.Schemas.SubmitTestResponse
    func abandonTest(sessionId: Int) async throws -> Components.Schemas.TestSessionAbandonResponse
    func getTestSession(sessionId: Int) async throws -> Components.Schemas.TestSessionStatusResponse
    func getTestResults(resultId: Int) async throws -> Components.Schemas.TestResultResponse
    func getTestHistory(limit: Int?, offset: Int?) async throws -> PaginatedTestHistoryResponse
    func getActiveTest() async throws -> Components.Schemas.TestSessionStatusResponse?
    func startAdaptiveTest() async throws -> Components.Schemas.StartTestResponse
    // swiftlint:disable:next line_length
    func submitAdaptiveResponse(sessionId: Int, questionId: Int, userAnswer: String, timeSpentSeconds: Int?) async throws -> Components.Schemas.AdaptiveNextResponse
    func getTestProgress(sessionId: Int) async throws -> Components.Schemas.TestProgressResponse

    // MARK: - Guest Test Management

    func startGuestTest(deviceId: String) async throws -> Components.Schemas.GuestStartTestResponse
    // swiftlint:disable:next line_length
    func submitGuestTest(guestToken: String, responses: [QuestionResponse], timeLimitExceeded: Bool) async throws -> Components.Schemas.GuestSubmitTestResponse

    // MARK: - Notifications

    func registerDevice(deviceToken: String) async throws
    func unregisterDevice() async throws
    func updateNotificationPreferences(enabled: Bool) async throws
    func getNotificationPreferences() async throws -> Components.Schemas.NotificationPreferencesResponse

    // MARK: - Benchmarks

    func getBenchmarkSummary() async throws -> Components.Schemas.BenchmarkSummaryResponse

    // MARK: - Feedback

    func submitFeedback(_ feedback: Feedback) async throws -> FeedbackSubmitResponse

    // MARK: - Groups

    func listGroups() async throws -> [Components.Schemas.GroupResponse]
    func createGroup(name: String) async throws -> Components.Schemas.GroupResponse
    func getGroup(groupId: Int) async throws -> Components.Schemas.GroupDetailResponse
    func deleteGroup(groupId: Int) async throws
    func joinGroup(inviteCode: String) async throws -> Components.Schemas.GroupResponse
    func generateInvite(groupId: Int) async throws -> Components.Schemas.GroupInviteResponse
    func getLeaderboard(groupId: Int) async throws -> Components.Schemas.LeaderboardResponse
    func removeMember(groupId: Int, userId: Int) async throws

    // MARK: - Token Management

    func setTokens(accessToken: String, refreshToken: String) async
    func clearTokens() async
}

// MARK: - Implementation

// swiftlint:disable type_body_length
/// OpenAPI service implementation that wraps the generated client.
///
/// This class is marked `@unchecked Sendable` because:
/// - `APIClientFactory` is thread-safe: it only holds the server URL and middleware actors
/// - `Client` (from swift-openapi-runtime) is designed to be thread-safe for concurrent requests
/// - `AuthenticationMiddleware` uses an actor for token storage, ensuring thread-safe access
/// - All properties are `let` constants, initialized once in `init`
///
/// The generated Client from swift-openapi-generator uses URLSession internally,
/// which is thread-safe for concurrent requests.
final class OpenAPIService: OpenAPIServiceProtocol, @unchecked Sendable {
    private let factory: APIClientFactory
    private let client: Client

    /// Initialize with a server URL
    init(serverURL: URL) {
        let factory = APIClientFactory(serverURL: serverURL)
        self.factory = factory

        // Bare client used exclusively for the refresh call — no TokenRefreshMiddleware to
        // prevent reentrancy. Captured once here so each refresh reuses the same instance.
        let bareClient = factory.makeClient()
        let refreshMiddleware = TokenRefreshMiddleware { [bareClient, factory] in
            let response = try await bareClient.refreshAccessTokenV1AuthRefreshPost()
            switch response {
            case let .ok(ok):
                guard case let .json(tokenRefresh) = ok.body else {
                    throw APIError.api(.invalidResponse)
                }
                await factory.authMiddleware.setTokens(
                    accessToken: tokenRefresh.accessToken,
                    refreshToken: tokenRefresh.refreshToken
                )
            case let .undocumented(statusCode, _):
                throw APIError.api(.unauthorized(message: "Refresh failed: HTTP \(statusCode)"))
            }
        }

        client = factory.makeClient(tokenRefreshMiddleware: refreshMiddleware)
    }

    /// Initialize with an existing factory (for testing)
    init(factory: APIClientFactory) {
        self.factory = factory
        client = factory.makeClient()
    }

    // MARK: - Authentication

    func login(email: String, password: String) async throws -> AuthResponse {
        do {
            let response = try await client.loginUserV1AuthLoginPost(
                body: .json(
                    Components.Schemas.UserLogin(
                        email: email,
                        password: password
                    )
                )
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(token) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return mapToAuthResponse(token)

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear _: Int? = nil,
        educationLevel _: EducationLevel? = nil,
        country _: String? = nil,
        region _: String? = nil
    ) async throws -> AuthResponse {
        do {
            let response = try await client.registerUserV1AuthRegisterPost(
                body: .json(
                    Components.Schemas.UserRegister(
                        email: email,
                        password: password,
                        firstName: firstName,
                        lastName: lastName
                    )
                )
            )

            switch response {
            case let .created(createdResponse):
                guard case let .json(token) = createdResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return mapToAuthResponse(token)

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func refreshToken() async throws -> AuthResponse {
        do {
            let response = try await client.refreshAccessTokenV1AuthRefreshPost()

            switch response {
            case let .ok(okResponse):
                guard case let .json(tokenRefresh) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                // TokenRefresh includes user data, so we can build a complete AuthResponse
                return AuthResponse(
                    accessToken: tokenRefresh.accessToken,
                    refreshToken: tokenRefresh.refreshToken,
                    tokenType: tokenRefresh.tokenType ?? "Bearer",
                    user: tokenRefresh.user
                )

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    /// Refresh access token - returns only the new tokens without user data.
    /// Use this when you only need to refresh tokens and don't need user profile.
    func refreshAccessToken() async throws -> (accessToken: String, refreshToken: String, tokenType: String) {
        do {
            let response = try await client.refreshAccessTokenV1AuthRefreshPost()

            switch response {
            case let .ok(okResponse):
                guard case let .json(tokenRefresh) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return (
                    accessToken: tokenRefresh.accessToken,
                    refreshToken: tokenRefresh.refreshToken,
                    tokenType: tokenRefresh.tokenType ?? "Bearer"
                )

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func logout() async throws {
        do {
            let response = try await client.logoutUserV1AuthLogoutPost()

            switch response {
            case .noContent:
                await clearTokens()

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - User Profile

    func getProfile() async throws -> User {
        do {
            let response = try await client.getUserProfileV1UserProfileGet()

            switch response {
            case let .ok(okResponse):
                guard case let .json(userResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return userResponse

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func deleteAccount() async throws {
        do {
            let response = try await client.deleteUserAccountV1UserDeleteAccountDelete()

            switch response {
            case .noContent:
                await clearTokens()

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - Test Management

    func startTest() async throws -> Components.Schemas.StartTestResponse {
        do {
            let response = try await client.startTestV1TestStartPost()

            switch response {
            case let .ok(okResponse):
                guard case let .json(startResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return startResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // swiftlint:disable:next line_length
    func submitTest(sessionId: Int, responses: [QuestionResponse], timeLimitExceeded: Bool) async throws -> Components.Schemas.SubmitTestResponse {
        let items = responses.map { response in
            Components.Schemas.ResponseItem(
                questionId: response.questionId,
                userAnswer: response.userAnswer
            )
        }

        do {
            let response = try await client.submitTestV1TestSubmitPost(
                body: .json(
                    Components.Schemas.ResponseSubmission(
                        sessionId: sessionId,
                        responses: items,
                        timeLimitExceeded: timeLimitExceeded
                    )
                )
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(submitResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return submitResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func abandonTest(sessionId: Int) async throws -> Components.Schemas.TestSessionAbandonResponse {
        do {
            let response = try await client.abandonTestV1TestSessionIdAbandonPost(
                path: .init(sessionId: sessionId)
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(abandonResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return abandonResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getTestSession(sessionId: Int) async throws -> Components.Schemas.TestSessionStatusResponse {
        do {
            let response = try await client.getTestSessionV1TestSessionSessionIdGet(
                path: .init(sessionId: sessionId)
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(sessionResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return sessionResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getTestResults(resultId: Int) async throws -> Components.Schemas.TestResultResponse {
        do {
            let response = try await client.getTestResultV1TestResultsResultIdGet(
                path: .init(resultId: resultId)
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(resultResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return resultResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getTestHistory(limit: Int? = nil, offset: Int? = nil) async throws -> PaginatedTestHistoryResponse {
        do {
            let response = try await client.getTestHistoryV1TestHistoryGet(
                query: .init(
                    limit: limit,
                    offset: offset
                )
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(paginatedResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return paginatedResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getActiveTest() async throws -> Components.Schemas.TestSessionStatusResponse? {
        // The swift-openapi-generator cannot produce a body type for anyOf:[schema, null] responses.
        // Decode the /v1/test/active response manually so we can handle the nullable JSON payload.
        // The middleware chain isn't available here, so we handle 401 with a single inline token
        // refresh and retry rather than going through TokenRefreshMiddleware.
        do {
            let initialToken = await factory.authMiddleware.getAccessToken()
            let (statusCode, data) = try await fetchActiveTest(token: initialToken)
            switch statusCode {
            case 200:
                return try decodeActiveTestResponse(data)
            case 401:
                _ = try await refreshAccessToken()
                let freshToken = await factory.authMiddleware.getAccessToken()
                let (retryStatus, retryData) = try await fetchActiveTest(token: freshToken)
                return try handleActiveTestStatus(retryStatus, data: retryData)
            default:
                throw APIError.api(.serverError(statusCode: statusCode, message: "Unexpected status"))
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    private func fetchActiveTest(token: String?) async throws -> (Int, Data) {
        let url = factory.serverURL.appendingPathComponent("v1/test/active")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, httpResponse) = try await URLSession.shared.data(for: request)
        guard let http = httpResponse as? HTTPURLResponse else {
            throw APIError.api(.invalidResponse)
        }
        return (http.statusCode, data)
    }

    private func decodeActiveTestResponse(_ data: Data) throws -> Components.Schemas.TestSessionStatusResponse? {
        let text = String(data: data, encoding: .utf8)
        if data.count <= 4, text?.trimmingCharacters(in: .whitespaces) == "null" {
            return nil
        }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(Components.Schemas.TestSessionStatusResponse.self, from: data)
    }

    private func handleActiveTestStatus(
        _ statusCode: Int,
        data: Data
    ) throws -> Components.Schemas.TestSessionStatusResponse? {
        switch statusCode {
        case 200:
            return try decodeActiveTestResponse(data)
        case 401:
            throw APIError.api(.unauthorized(message: "Unauthorized"))
        default:
            throw APIError.api(.serverError(statusCode: statusCode, message: "Unexpected status"))
        }
    }

    func startAdaptiveTest() async throws -> Components.Schemas.StartTestResponse {
        do {
            let response = try await client.startTestV1TestStartPost(query: .init(adaptive: true))

            switch response {
            case let .ok(okResponse):
                guard case let .json(startResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return startResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // swiftlint:disable:next line_length
    func submitAdaptiveResponse(sessionId: Int, questionId: Int, userAnswer: String, timeSpentSeconds _: Int?) async throws -> Components.Schemas.AdaptiveNextResponse {
        do {
            let response = try await client.submitAdaptiveResponseV1TestNextPost(
                body: .json(
                    Components.Schemas.AdaptiveResponseRequest(
                        sessionId: sessionId,
                        questionId: questionId,
                        userAnswer: userAnswer
                    )
                )
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(nextResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return nextResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getTestProgress(sessionId: Int) async throws -> Components.Schemas.TestProgressResponse {
        do {
            let response = try await client.getTestProgressV1TestProgressGet(query: .init(sessionId: sessionId))

            switch response {
            case let .ok(okResponse):
                guard case let .json(progressResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return progressResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - Guest Test Management

    func startGuestTest(deviceId: String) async throws -> Components.Schemas.GuestStartTestResponse {
        do {
            let response = try await client.startGuestTestV1TestGuestStartPost(
                headers: .init(xDeviceId: deviceId)
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(startResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return startResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // swiftlint:disable:next line_length
    func submitGuestTest(guestToken: String, responses: [QuestionResponse], timeLimitExceeded: Bool) async throws -> Components.Schemas.GuestSubmitTestResponse {
        let items = responses.map { response in
            Components.Schemas.ResponseItem(
                questionId: response.questionId,
                userAnswer: response.userAnswer
            )
        }

        do {
            let response = try await client.submitGuestTestV1TestGuestSubmitPost(
                body: .json(
                    Components.Schemas.GuestSubmitRequest(
                        guestToken: guestToken,
                        responses: items,
                        timeLimitExceeded: timeLimitExceeded
                    )
                )
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(submitResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return submitResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - Notifications

    func registerDevice(deviceToken: String) async throws {
        do {
            let response = try await client.registerDeviceTokenV1NotificationsRegisterDevicePost(
                body: .json(
                    Components.Schemas.DeviceTokenRegister(
                        deviceToken: deviceToken
                    )
                )
            )

            switch response {
            case .ok:
                return

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func unregisterDevice() async throws {
        do {
            let response = try await client.unregisterDeviceTokenV1NotificationsRegisterDeviceDelete()

            switch response {
            case .ok:
                return

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func updateNotificationPreferences(enabled: Bool) async throws {
        do {
            let response = try await client.updateNotificationPreferencesV1NotificationsPreferencesPut(
                body: .json(
                    Components.Schemas.NotificationPreferences(
                        notificationEnabled: enabled
                    )
                )
            )

            switch response {
            case .ok:
                return

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getNotificationPreferences() async throws -> Components.Schemas.NotificationPreferencesResponse {
        do {
            let response = try await client.getNotificationPreferencesV1NotificationsPreferencesGet()

            switch response {
            case let .ok(okResponse):
                guard case let .json(preferencesResponse) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return preferencesResponse

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - Benchmarks

    func getBenchmarkSummary() async throws -> Components.Schemas.BenchmarkSummaryResponse {
        do {
            let response = try await client.getBenchmarkSummaryV1BenchmarkSummaryGet()
            switch response {
            case let .ok(okResponse):
                guard case let .json(summary) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return summary
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - Feedback

    // swiftlint:disable:next cyclomatic_complexity
    func submitFeedback(_ feedback: Feedback) async throws -> FeedbackSubmitResponse {
        let categorySchema: Components.Schemas.FeedbackCategory = switch feedback.category {
        case .bugReport:
            .bugReport
        case .featureRequest:
            .featureRequest
        case .generalFeedback:
            .generalFeedback
        case .questionHelp:
            .questionHelp
        case .other:
            .other
        }

        do {
            let response = try await client.submitFeedbackV1FeedbackSubmitPost(
                body: .json(
                    Components.Schemas.FeedbackSubmitRequest(
                        name: feedback.name,
                        email: feedback.email,
                        category: categorySchema,
                        description: feedback.description
                    )
                )
            )

            switch response {
            case let .created(createdResponse):
                guard case let .json(feedbackResponse) = createdResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return feedbackResponse

            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - Groups

    func listGroups() async throws -> [Components.Schemas.GroupResponse] {
        do {
            let response = try await client.listGroupsV1GroupsGet()
            switch response {
            case let .ok(okResponse):
                guard case let .json(groups) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return groups
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func createGroup(name: String) async throws -> Components.Schemas.GroupResponse {
        do {
            let response = try await client.createGroupV1GroupsPost(
                body: .json(Components.Schemas.CreateGroupRequest(name: name))
            )
            switch response {
            case let .created(createdResponse):
                guard case let .json(group) = createdResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return group
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getGroup(groupId: Int) async throws -> Components.Schemas.GroupDetailResponse {
        do {
            let response = try await client.getGroupV1GroupsGroupIdGet(
                path: .init(groupId: groupId)
            )
            switch response {
            case let .ok(okResponse):
                guard case let .json(group) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return group
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func deleteGroup(groupId: Int) async throws {
        do {
            let response = try await client.deleteGroupV1GroupsGroupIdDelete(
                path: .init(groupId: groupId)
            )
            switch response {
            case .noContent:
                return
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func joinGroup(inviteCode: String) async throws -> Components.Schemas.GroupResponse {
        do {
            let response = try await client.joinGroupV1GroupsJoinPost(
                body: .json(Components.Schemas.JoinGroupRequest(inviteCode: inviteCode))
            )
            switch response {
            case let .ok(okResponse):
                guard case let .json(group) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return group
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func generateInvite(groupId: Int) async throws -> Components.Schemas.GroupInviteResponse {
        do {
            let response = try await client.generateInviteV1GroupsGroupIdInvitePost(
                path: .init(groupId: groupId)
            )
            switch response {
            case let .ok(okResponse):
                guard case let .json(invite) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return invite
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func getLeaderboard(groupId: Int) async throws -> Components.Schemas.LeaderboardResponse {
        do {
            let response = try await client.getLeaderboardV1GroupsGroupIdLeaderboardGet(
                path: .init(groupId: groupId)
            )
            switch response {
            case let .ok(okResponse):
                guard case let .json(leaderboard) = okResponse.body else {
                    throw APIError.api(.invalidResponse)
                }
                return leaderboard
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    func removeMember(groupId: Int, userId: Int) async throws {
        do {
            let response = try await client.removeMemberV1GroupsGroupIdMembersUserIdDelete(
                path: .init(groupId: groupId, userId: userId)
            )
            switch response {
            case .noContent:
                return
            case .unprocessableContent:
                throw APIError.api(.unprocessableEntity(message: "Validation failed"))
            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw try mapToAPIError(error)
        }
    }

    // MARK: - Token Management

    func setTokens(accessToken: String, refreshToken: String) async {
        await factory.authMiddleware.setTokens(
            accessToken: accessToken,
            refreshToken: refreshToken
        )
    }

    func clearTokens() async {
        await factory.authMiddleware.clearTokens()
    }

    // MARK: - Helper Methods

    /// Maps non-APIError errors (e.g. ClientError from OpenAPIRuntime) to typed APIError cases.
    /// This ensures all errors leaving OpenAPIService are properly typed.
    /// Throws `CancellationError` directly so task cancellation is never swallowed as APIError.unknown.
    ///
    /// - Note: `internal` (not `private`) to allow direct unit testing via `@testable import`.
    func mapToAPIError(_ error: Error) throws -> APIError {
        if error is CancellationError { throw error }

        // Already an APIError — pass through
        if let apiError = error as? APIError {
            return apiError
        }

        // ClientError wraps the real error in a typed property; NSError bridging cannot
        // reach it because ClientError does not conform to CustomNSError.
        if let clientError = error as? ClientError {
            return try mapToAPIError(clientError.underlyingError)
        }

        // Dig through the error chain via NSError bridging for other error types.
        let underlying = (error as NSError).userInfo[NSUnderlyingErrorKey] as? Error ?? error

        if underlying is DecodingError {
            return .api(.decodingError(underlying.localizedDescription))
        }

        if let urlError = underlying as? URLError {
            switch urlError.code {
            case .notConnectedToInternet, .networkConnectionLost:
                return .api(.noInternetConnection)
            case .timedOut:
                return .api(.timeout)
            default:
                return .api(.networkError(urlError.localizedDescription))
            }
        }

        return .api(.unknown(message: error.localizedDescription))
    }

    private func mapToAuthResponse(_ token: Components.Schemas.Token) -> AuthResponse {
        AuthResponse(
            accessToken: token.accessToken,
            refreshToken: token.refreshToken,
            tokenType: token.tokenType ?? "Bearer",
            user: token.user
        )
    }

    private func mapUndocumentedError(
        statusCode: Int,
        payload: OpenAPIRuntime.UndocumentedPayload
    ) async -> APIError {
        // Try to extract error message from response body
        let message = await extractErrorMessage(from: payload.body)

        switch statusCode {
        case 400:
            return APIError.parseBadRequest(message: message)
        case 401:
            return .api(.unauthorized(message: message))
        case 403:
            return .api(.forbidden(message: message))
        case 404:
            return .api(.notFound(message: message))
        case 408:
            return .api(.timeout)
        case 422:
            return .api(.unprocessableEntity(message: message))
        case 429:
            return .api(.rateLimitExceeded(message: message))
        case 500 ... 599:
            return .api(.serverError(statusCode: statusCode, message: message))
        default:
            return .api(.unknown(message: message ?? "Unexpected status code: \(statusCode)"))
        }
    }

    /// Extracts error message from HTTP response body.
    /// Returns nil if body is nil, empty, or cannot be decoded.
    private func extractErrorMessage(from body: HTTPBody?) async -> String? {
        guard let body else { return nil }

        do {
            // Collect body data (limit to 1MB to prevent memory issues)
            let data = try await Data(collecting: body, upTo: 1024 * 1024)
            let errorResponse = try JSONDecoder().decode(ErrorResponse.self, from: data)
            return errorResponse.detail
        } catch {
            // If decoding fails, try to get raw string
            return nil
        }
    }
}

// swiftlint:enable type_body_length
