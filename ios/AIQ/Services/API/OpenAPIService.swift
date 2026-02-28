// swiftlint:disable file_length
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
    func getTestHistory(limit: Int?, offset: Int?) async throws -> PaginatedTestHistoryResponse
    func getActiveTest() async throws -> Components.Schemas.TestSessionStatusResponse?
    func startAdaptiveTest() async throws -> Components.Schemas.StartTestResponse
    // swiftlint:disable:next line_length
    func submitAdaptiveResponse(sessionId: Int, questionId: Int, userAnswer: String, timeSpentSeconds: Int?) async throws -> Components.Schemas.AdaptiveNextResponse
    func getTestProgress(sessionId: Int) async throws -> Components.Schemas.TestProgressResponse

    // MARK: - Notifications

    func registerDevice(deviceToken: String) async throws
    func unregisterDevice() async throws
    func updateNotificationPreferences(enabled: Bool) async throws
    func getNotificationPreferences() async throws -> Components.Schemas.NotificationPreferencesResponse

    // MARK: - Feedback

    func submitFeedback(_ feedback: Feedback) async throws -> FeedbackSubmitResponse

    // MARK: - Token Management

    func setTokens(accessToken: String, refreshToken: String) async
    func clearTokens() async
}

// MARK: - Implementation

// swiftlint:disable type_body_length
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
        let factory = AIQAPIClientFactory(serverURL: serverURL)
        self.factory = factory

        // Bare client used exclusively for the refresh call — no TokenRefreshMiddleware to
        // prevent reentrancy. Captured once here so each refresh reuses the same instance.
        let bareClient = factory.makeClient()
        let refreshMiddleware = TokenRefreshMiddleware { [bareClient, factory] in
            let response = try await bareClient.refreshAccessTokenV1AuthRefreshPost()
            switch response {
            case let .ok(ok):
                guard case let .json(tokenRefresh) = ok.body else {
                    throw APIError.invalidResponse
                }
                await factory.authMiddleware.setTokens(
                    accessToken: tokenRefresh.accessToken,
                    refreshToken: tokenRefresh.refreshToken
                )
            case let .undocumented(statusCode, _):
                throw APIError.unauthorized(message: "Refresh failed: HTTP \(statusCode)")
            }
        }

        client = factory.makeClient(tokenRefreshMiddleware: refreshMiddleware)
    }

    /// Initialize with an existing factory (for testing)
    init(factory: AIQAPIClientFactory) {
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
                    throw APIError.invalidResponse
                }
                return mapToAuthResponse(token)

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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

        do {
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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    func refreshToken() async throws -> AuthResponse {
        do {
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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    func logout() async throws {
        do {
            let response = try await client.logoutUserV1AuthLogoutPost()

            switch response {
            case .noContent:
                await clearTokens()

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    // MARK: - User Profile

    func getProfile() async throws -> User {
        do {
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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
            throw mapToAPIError(error)
        }
    }

    // MARK: - Test Management

    func startTest() async throws -> Components.Schemas.StartTestResponse {
        do {
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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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

        do {
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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
                    throw APIError.invalidResponse
                }
                return abandonResponse

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
                    throw APIError.invalidResponse
                }
                return sessionResponse

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
                    throw APIError.invalidResponse
                }
                return resultResponse

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
                    throw APIError.invalidResponse
                }
                return paginatedResponse

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    func getActiveTest() async throws -> Components.Schemas.TestSessionStatusResponse? {
        do {
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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    func startAdaptiveTest() async throws -> Components.Schemas.StartTestResponse {
        do {
            let response = try await client.startTestV1TestStartPost(query: .init(adaptive: true))

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
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    // swiftlint:disable:next line_length
    func submitAdaptiveResponse(sessionId: Int, questionId: Int, userAnswer: String, timeSpentSeconds: Int?) async throws -> Components.Schemas.AdaptiveNextResponse {
        do {
            let response = try await client.submitAdaptiveResponseV1TestNextPost(
                body: .json(
                    Components.Schemas.AdaptiveResponseRequest(
                        questionId: questionId,
                        sessionId: sessionId,
                        timeSpentSeconds: timeSpentSeconds,
                        userAnswer: userAnswer
                    )
                )
            )

            switch response {
            case let .ok(okResponse):
                guard case let .json(nextResponse) = okResponse.body else {
                    throw APIError.invalidResponse
                }
                return nextResponse

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    func getTestProgress(sessionId: Int) async throws -> Components.Schemas.TestProgressResponse {
        do {
            let response = try await client.getTestProgressV1TestProgressGet(query: .init(sessionId: sessionId))

            switch response {
            case let .ok(okResponse):
                guard case let .json(progressResponse) = okResponse.body else {
                    throw APIError.invalidResponse
                }
                return progressResponse

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
            throw mapToAPIError(error)
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
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    func getNotificationPreferences() async throws -> Components.Schemas.NotificationPreferencesResponse {
        do {
            let response = try await client.getNotificationPreferencesV1NotificationsPreferencesGet()

            switch response {
            case let .ok(okResponse):
                guard case let .json(preferencesResponse) = okResponse.body else {
                    throw APIError.invalidResponse
                }
                return preferencesResponse

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
        }
    }

    // MARK: - Feedback

    // swiftlint:disable:next cyclomatic_complexity
    func submitFeedback(_ feedback: Feedback) async throws -> FeedbackSubmitResponse {
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

        do {
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
            case let .created(createdResponse):
                guard case let .json(feedbackResponse) = createdResponse.body else {
                    throw APIError.invalidResponse
                }
                return feedbackResponse

            case .unprocessableContent:
                throw APIError.unprocessableEntity(message: "Validation failed")

            case let .undocumented(statusCode, payload):
                throw await mapUndocumentedError(statusCode: statusCode, payload: payload)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw mapToAPIError(error)
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
    private func mapToAPIError(_ error: Error) -> APIError {
        // Already an APIError — pass through
        if let apiError = error as? APIError {
            return apiError
        }

        // Dig through the error chain to find the underlying cause.
        // ClientError wraps the real error; NSError bridging may add another layer.
        let underlying = (error as NSError).userInfo[NSUnderlyingErrorKey] as? Error ?? error

        if underlying is DecodingError {
            return .decodingError(underlying)
        }

        if let urlError = underlying as? URLError {
            switch urlError.code {
            case .notConnectedToInternet, .networkConnectionLost:
                return .noInternetConnection
            case .timedOut:
                return .timeout
            default:
                return .networkError(urlError)
            }
        }

        return .unknown(message: error.localizedDescription)
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

// swiftlint:enable type_body_length
