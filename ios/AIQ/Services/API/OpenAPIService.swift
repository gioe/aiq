import AIQAPIClient
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
    func getTestHistory(limit: Int?, offset: Int?) async throws -> [Components.Schemas.TestResultResponse]
    func getActiveTest() async throws -> Components.Schemas.TestSessionStatusResponse?

    // MARK: - Notifications

    func registerDevice(deviceToken: String) async throws
    func updateNotificationPreferences(enabled: Bool) async throws

    // MARK: - Feedback

    func submitFeedback(_ feedback: Feedback) async throws

    // MARK: - Token Management

    func setTokens(accessToken: String, refreshToken: String) async
    func clearTokens() async
}

// MARK: - Implementation

/// OpenAPI service implementation that wraps the generated client.
///
/// This class is marked `@unchecked Sendable` because:
/// - `AIQAPIClientFactory` is thread-safe: it only holds the server URL and middleware actors
/// - `Client` (from swift-openapi-runtime) is designed to be thread-safe for concurrent requests
/// - `AuthenticationMiddleware` uses an actor for token storage, ensuring thread-safe access
/// - All properties are `let` constants, initialized once in `init`
///
/// The generated Client from swift-openapi-generator uses URLSession internally,
/// which is thread-safe for concurrent requests.
final class OpenAPIService: OpenAPIServiceProtocol, @unchecked Sendable {
    private let factory: AIQAPIClientFactory
    private let client: Client

    /// Initialize with a server URL
    init(serverURL: URL) {
        factory = AIQAPIClientFactory(serverURL: serverURL)
        client = factory.makeClient()
    }

    /// Initialize with an existing factory (for testing)
    init(factory: AIQAPIClientFactory) {
        self.factory = factory
        client = factory.makeClient()
    }

    // MARK: - Authentication

    func login(email: String, password: String) async throws -> AuthResponse {
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
                throw APIError.invalidResponse
            }
            return mapToAuthResponse(token)

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear: Int? = nil,
        educationLevel: EducationLevel? = nil,
        country: String? = nil,
        region: String? = nil
    ) async throws -> AuthResponse {
        // Convert education level to generated payload type
        // swiftformat:disable all
        // swiftlint:disable opening_brace
        let educationPayload: Components.Schemas.UserRegister.EducationLevelPayload?
        if let level = educationLevel,
           let schema = Components.Schemas.EducationLevelSchema(rawValue: level.rawValue)
        {
            educationPayload = .init(value1: schema)
        } else {
            educationPayload = nil
        }
        // swiftlint:enable opening_brace
        // swiftformat:enable all

        let response = try await client.registerUserV1AuthRegisterPost(
            body: .json(
                Components.Schemas.UserRegister(
                    birthYear: birthYear,
                    country: country,
                    educationLevel: educationPayload,
                    email: email,
                    firstName: firstName,
                    lastName: lastName,
                    password: password,
                    region: region
                )
            )
        )

        switch response {
        case let .created(createdResponse):
            guard case let .json(token) = createdResponse.body else {
                throw APIError.invalidResponse
            }
            return mapToAuthResponse(token)

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func refreshToken() async throws -> AuthResponse {
        let response = try await client.refreshAccessTokenV1AuthRefreshPost()

        switch response {
        case let .ok(okResponse):
            guard case let .json(tokenRefresh) = okResponse.body else {
                throw APIError.invalidResponse
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
    }

    /// Refresh access token - returns only the new tokens without user data.
    /// Use this when you only need to refresh tokens and don't need user profile.
    func refreshAccessToken() async throws -> (accessToken: String, refreshToken: String, tokenType: String) {
        let response = try await client.refreshAccessTokenV1AuthRefreshPost()

        switch response {
        case let .ok(okResponse):
            guard case let .json(tokenRefresh) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return (
                accessToken: tokenRefresh.accessToken,
                refreshToken: tokenRefresh.refreshToken,
                tokenType: tokenRefresh.tokenType ?? "Bearer"
            )

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func logout() async throws {
        let response = try await client.logoutUserV1AuthLogoutPost()

        switch response {
        case .noContent:
            await clearTokens()

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    // MARK: - User Profile

    func getProfile() async throws -> User {
        let response = try await client.getUserProfileV1UserProfileGet()

        switch response {
        case let .ok(okResponse):
            guard case let .json(userResponse) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return userResponse

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func deleteAccount() async throws {
        let response = try await client.deleteUserAccountV1UserDeleteAccountDelete()

        switch response {
        case .noContent:
            await clearTokens()

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    // MARK: - Test Management

    func startTest() async throws -> Components.Schemas.StartTestResponse {
        let response = try await client.startTestV1TestStartPost()

        switch response {
        case let .ok(okResponse):
            guard case let .json(startResponse) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return startResponse

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    // swiftlint:disable:next line_length
    func submitTest(sessionId: Int, responses: [QuestionResponse], timeLimitExceeded: Bool) async throws -> Components.Schemas.SubmitTestResponse {
        let items = responses.map { response in
            Components.Schemas.ResponseItem(
                questionId: response.questionId,
                timeSpentSeconds: response.timeSpentSeconds,
                userAnswer: response.userAnswer
            )
        }

        let response = try await client.submitTestV1TestSubmitPost(
            body: .json(
                Components.Schemas.ResponseSubmission(
                    responses: items,
                    sessionId: sessionId,
                    timeLimitExceeded: timeLimitExceeded
                )
            )
        )

        switch response {
        case let .ok(okResponse):
            guard case let .json(submitResponse) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return submitResponse

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func abandonTest(sessionId: Int) async throws -> Components.Schemas.TestSessionAbandonResponse {
        let response = try await client.abandonTestV1TestSessionIdAbandonPost(
            path: .init(sessionId: sessionId)
        )

        switch response {
        case let .ok(okResponse):
            guard case let .json(abandonResponse) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return abandonResponse

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func getTestSession(sessionId: Int) async throws -> Components.Schemas.TestSessionStatusResponse {
        let response = try await client.getTestSessionV1TestSessionSessionIdGet(
            path: .init(sessionId: sessionId)
        )

        switch response {
        case let .ok(okResponse):
            guard case let .json(sessionResponse) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return sessionResponse

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func getTestResults(resultId: Int) async throws -> Components.Schemas.TestResultResponse {
        let response = try await client.getTestResultV1TestResultsResultIdGet(
            path: .init(resultId: resultId)
        )

        switch response {
        case let .ok(okResponse):
            guard case let .json(resultResponse) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return resultResponse

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func getTestHistory(limit: Int? = nil, offset: Int? = nil) async throws -> [Components.Schemas.TestResultResponse] {
        let response = try await client.getTestHistoryV1TestHistoryGet(
            query: .init(
                limit: limit,
                offset: offset
            )
        )

        switch response {
        case let .ok(okResponse):
            guard case let .json(paginatedResponse) = okResponse.body else {
                throw APIError.invalidResponse
            }
            return paginatedResponse.results

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func getActiveTest() async throws -> Components.Schemas.TestSessionStatusResponse? {
        let response = try await client.getActiveTestSessionV1TestActiveGet()

        switch response {
        case let .ok(okResponse):
            guard case let .json(jsonPayload) = okResponse.body else {
                throw APIError.invalidResponse
            }
            // Response can be nil if no active session
            // The JsonPayload wraps the actual TestSessionStatusResponse in value1
            guard let payload = jsonPayload else {
                return nil
            }
            return payload.value1

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    // MARK: - Notifications

    func registerDevice(deviceToken: String) async throws {
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
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    func updateNotificationPreferences(enabled: Bool) async throws {
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
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
        }
    }

    // MARK: - Feedback

    func submitFeedback(_ feedback: Feedback) async throws {
        let categorySchema: Components.Schemas.FeedbackCategorySchema = switch feedback.category {
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

        let response = try await client.submitFeedbackV1FeedbackSubmitPost(
            body: .json(
                Components.Schemas.FeedbackSubmitRequest(
                    category: categorySchema,
                    description: feedback.description,
                    email: feedback.email,
                    name: feedback.name
                )
            )
        )

        switch response {
        case .created:
            return

        case .unprocessableContent:
            throw APIError.unprocessableEntity(message: "Validation failed")

        case let .undocumented(statusCode, payload):
            throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
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
            return APIError.unauthorized(message: message)
        case 403:
            return APIError.forbidden(message: message)
        case 404:
            return APIError.notFound(message: message)
        case 408:
            return APIError.timeout
        case 422:
            return APIError.unprocessableEntity(message: message)
        case 429:
            return APIError.rateLimitExceeded(message: message)
        case 500 ... 599:
            return APIError.serverError(statusCode: statusCode, message: message)
        default:
            return APIError.unknown(message: message ?? "Unexpected status code: \(statusCode)")
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
