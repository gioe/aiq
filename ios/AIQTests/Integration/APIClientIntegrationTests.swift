import Combine
import XCTest

@testable import AIQ

/// Integration tests for APIClient networking layer.
/// These tests verify the APIClient works correctly with URLSession and handles real HTTP scenarios.
@MainActor
final class APIClientIntegrationTests: XCTestCase {
    var sut: APIClient!
    var mockURLSession: URLSession!
    var cancellables: Set<AnyCancellable>!

    override func setUp() {
        super.setUp()
        cancellables = []

        // Create URLSession with mock configuration
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        mockURLSession = URLSession(configuration: configuration)

        sut = APIClient(
            baseURL: "https://api.test.com",
            session: mockURLSession,
            retryPolicy: RetryPolicy(
                maxAttempts: 1,
                retryableStatusCodes: [],
                retryableErrors: [],
                delayCalculator: { _ in 0 }
            ), // Disable retries for testing
            requestInterceptors: [], // Disable interceptors for testing
            responseInterceptors: [] // Disable interceptors for testing
        )
    }

    override func tearDown() {
        cancellables = nil
        mockURLSession = nil
        sut = nil
        MockURLProtocol.requestHandler = nil
        super.tearDown()
    }

    // MARK: - Authentication Flow Integration Tests

    func testCompleteLoginFlow() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"

        mockLoginResponse(email: email, password: password)

        // When
        let loginRequest = LoginRequest(email: email, password: password)
        let result: AuthResponse = try await sut.request(
            endpoint: .login,
            method: .post,
            body: loginRequest,
            requiresAuth: false
        )

        // Then
        XCTAssertEqual(result.accessToken, "mock-access-token")
        XCTAssertEqual(result.refreshToken, "mock-refresh-token")
        XCTAssertEqual(result.user.email, email)
    }

    func testCompleteRegistrationFlow() async throws {
        // Given
        let email = "newuser@example.com"
        let password = "SecurePass123!"
        let firstName = "New"
        let lastName = "User"

        mockRegistrationResponse(email: email, firstName: firstName, lastName: lastName)

        // When
        let registrationRequest = RegisterRequest(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let result: AuthResponse = try await sut.request(
            endpoint: .register,
            method: .post,
            body: registrationRequest,
            requiresAuth: false
        )

        // Then
        XCTAssertEqual(result.accessToken, "new-access-token")
        XCTAssertEqual(result.user.email, email)
        XCTAssertEqual(result.user.firstName, firstName)
    }

    // MARK: - Token Management Integration Tests

    func testAutomaticTokenInjection() async throws {
        // Given - Set access token
        sut.setAuthToken("test-bearer-token")

        let capturedHeaders = HeadersCapture()
        mockUserProfileResponse(captureHeaders: capturedHeaders)

        // When
        let _: UserProfile = try await sut.request(
            endpoint: .userProfile,
            method: .get,
            body: nil as String?,
            requiresAuth: true
        )

        // Then - Verify Authorization header was included
        XCTAssertEqual(capturedHeaders.headers?["Authorization"], "Bearer test-bearer-token")
    }

    // MARK: - Test Taking Flow Integration Tests

    func testCompleteTestTakingFlow() async throws {
        // Given
        sut.setAuthToken("valid-token")

        let requestCount = RequestCounter()
        mockTestTakingFlow(requestCount: requestCount)
        // When - Start test
        let startResponse: StartTestResponse = try await sut.request(
            endpoint: .testStart,
            method: .post,
            body: nil as String?,
            requiresAuth: true
        )

        // Then - Verify test started
        XCTAssertEqual(startResponse.session.status, .inProgress)
        XCTAssertEqual(startResponse.questions.count, 2)

        // When - Submit test
        let submitResponse = try await submitTest(sessionId: startResponse.session.id)

        // Then - Verify submission successful
        XCTAssertEqual(submitResponse.result.iqScore, 120)
        XCTAssertEqual(submitResponse.result.totalQuestions, 2)
        XCTAssertEqual(requestCount.count, 2)
    }

    // MARK: - Token Refresh Retry Limit Tests

    func testTokenRefreshRetryLimitPreventsInfiniteLoop() async {
        // Given - Create APIClient with token refresh interceptor
        let mockAuthService = MockAuthService()
        let tokenRefreshInterceptor = TokenRefreshInterceptor(authService: mockAuthService)

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        let testSession = URLSession(configuration: configuration)

        let testClient = APIClient(
            baseURL: "https://api.test.com",
            session: testSession,
            retryPolicy: RetryPolicy(
                maxAttempts: 1,
                retryableStatusCodes: [],
                retryableErrors: [],
                delayCalculator: { _ in 0 }
            ),
            requestInterceptors: [],
            responseInterceptors: [tokenRefreshInterceptor]
        )

        testClient.setAuthToken("expired-token")

        var requestCount = 0
        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            let url = request.url!

            // Token refresh endpoint always succeeds
            if url.path.contains("/auth/refresh") {
                let response = [
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "token_type": "bearer",
                    "user": [
                        "id": 123,
                        "email": "test@example.com",
                        "first_name": "Test",
                        "last_name": "User",
                        "created_at": ISO8601DateFormatter().string(from: Date()),
                        "last_login_at": ISO8601DateFormatter().string(from: Date()),
                        "notification_enabled": true
                    ] as [String: Any]
                ] as [String: Any]
                return try self.createHTTPResponse(url: url, statusCode: 200, json: response)
            }

            // All other requests return 401 to simulate persistent auth failure
            let errorResponse = ["detail": "Unauthorized"]
            return try self.createHTTPResponse(url: url, statusCode: 401, json: errorResponse)
        }

        // When/Then - Request should fail after retry limit is exceeded
        do {
            let _: UserProfile = try await testClient.request(
                endpoint: .userProfile,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )
            XCTFail("Should have thrown unauthorized error after retry limit")
        } catch let error as APIError {
            if case let .unauthorized(message) = error {
                // Success - verify it's the retry limit error
                XCTAssertTrue(
                    message?.contains("Authentication failed after token refresh") ?? false,
                    "Error message should indicate retry limit exceeded"
                )
                // Verify we didn't recurse infinitely
                // Should be: 1 initial request + 1 token refresh + 1 retry + 1 token refresh = 4 max
                XCTAssertLessThanOrEqual(requestCount, 4, "Should not exceed retry limit")
            } else {
                XCTFail("Expected unauthorized error with retry limit message, got \(error)")
            }
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    // MARK: - Error Handling Integration Tests

    func testNetworkErrorHandling() async {
        // Given - Mock network error
        MockURLProtocol.requestHandler = { _ in
            throw URLError(.notConnectedToInternet)
        }

        // When/Then
        await assertThrowsAPIError(.networkError(URLError(.notConnectedToInternet)))
    }

    func testUnauthorizedErrorHandling() async {
        // Given - Mock 401 response
        mockHTTPErrorResponse(statusCode: 401, detail: "Unauthorized")

        // When/Then
        await assertThrowsAPIError(.unauthorized(message: nil))
    }

    func testServerErrorHandling() async {
        // Given - Mock 500 response
        mockHTTPErrorResponse(statusCode: 500, detail: "Internal Server Error")

        // When/Then
        await assertThrowsAPIError(.serverError(statusCode: 500, message: nil))
    }

    func testValidationErrorHandling() async {
        // Given - Mock 422 validation error response
        mockValidationErrorResponse()

        // When/Then
        do {
            let request = LoginRequest(email: "invalid", password: "test")
            let _: AuthResponse = try await sut.request(
                endpoint: .login,
                method: .post,
                body: request,
                requiresAuth: false
            )
            XCTFail("Should have thrown error")
        } catch let error as APIError {
            if case .unprocessableEntity = error {
                // Success - correct error type (422 validation error maps to unprocessableEntity)
            } else {
                XCTFail("Expected unprocessableEntity, got \(error)")
            }
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    // MARK: - History and Results Integration Tests

    func testFetchTestHistory() async throws {
        // Given
        sut.setAuthToken("valid-token")
        mockTestHistoryResponse()

        // When - API now returns paginated response (BCQ-004)
        let paginatedResponse: PaginatedTestHistoryResponse = try await sut.request(
            endpoint: .testHistory,
            method: .get,
            body: nil as String?,
            requiresAuth: true
        )

        // Then
        XCTAssertEqual(paginatedResponse.results.count, 2)
        XCTAssertEqual(paginatedResponse.results[0].iqScore, 120)
        XCTAssertEqual(paginatedResponse.results[1].iqScore, 118)
        XCTAssertEqual(paginatedResponse.totalCount, 2)
        XCTAssertEqual(paginatedResponse.limit, 50)
        XCTAssertEqual(paginatedResponse.offset, 0)
        XCTAssertFalse(paginatedResponse.hasMore)
    }

    // MARK: - Active Session Integration Tests

    func testFetchActiveSession_WithActiveSession() async throws {
        // Given
        sut.setAuthToken("valid-token")
        mockActiveSessionResponse(hasActiveSession: true)

        // When
        let response: TestSessionStatusResponse = try await sut.request(
            endpoint: .testActive,
            method: .get,
            body: nil as String?,
            requiresAuth: true
        )

        // Then
        XCTAssertEqual(response.session.id, 123)
        XCTAssertEqual(response.session.status, .inProgress)
        XCTAssertEqual(response.questionsCount, 5)
    }

    func testFetchActiveSession_NoActiveSession() async throws {
        // Given
        sut.setAuthToken("valid-token")
        mockActiveSessionResponse(hasActiveSession: false)

        // When/Then
        // Backend returns null when no active session exists
        // The API client should handle this gracefully by allowing Optional return type
        do {
            let response: TestSessionStatusResponse? = try await sut.request(
                endpoint: .testActive,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )
            // Success - null response handled gracefully
            XCTAssertNil(response, "Should decode null response as nil")
        } catch {
            XCTFail("Should handle null response gracefully, got error: \(error)")
        }
    }

    func testFetchActiveSession_Unauthorized() async throws {
        // Given - No auth token set
        mockHTTPErrorResponse(statusCode: 401, detail: "Unauthorized")

        // When/Then
        do {
            let _: TestSessionStatusResponse = try await sut.request(
                endpoint: .testActive,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )
            XCTFail("Should have thrown unauthorized error")
        } catch let error as APIError {
            if case .unauthorized = error {
                // Success - correct error type
            } else {
                XCTFail("Expected unauthorized error, got \(error)")
            }
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    func testFetchActiveSession_ServerError() async throws {
        // Given
        sut.setAuthToken("valid-token")
        mockHTTPErrorResponse(statusCode: 500, detail: "Internal Server Error")

        // When/Then
        do {
            let _: TestSessionStatusResponse = try await sut.request(
                endpoint: .testActive,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )
            XCTFail("Should have thrown server error")
        } catch let error as APIError {
            if case .serverError = error {
                // Success - correct error type
            } else {
                XCTFail("Expected server error, got \(error)")
            }
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }
}

// MARK: - Helper Methods

extension APIClientIntegrationTests {
    private func mockLoginResponse(email: String, password: String) {
        MockURLProtocol.requestHandler = { request in
            guard let url = request.url,
                  url.path.contains("/auth/login"),
                  let body = request.httpBody,
                  let json = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
                  json["email"] as? String == email,
                  json["password"] as? String == password
            else {
                throw URLError(.badServerResponse)
            }

            let response = [
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "token_type": "bearer",
                "user": [
                    "id": 123,
                    "email": email,
                    "first_name": "Test",
                    "last_name": "User",
                    "created_at": ISO8601DateFormatter().string(from: Date()),
                    "last_login_at": ISO8601DateFormatter().string(from: Date()),
                    "notification_enabled": true
                ] as [String: Any]
            ] as [String: Any]

            return try self.createHTTPResponse(url: url, statusCode: 200, json: response)
        }
    }

    private func mockRegistrationResponse(email: String, firstName: String, lastName: String) {
        MockURLProtocol.requestHandler = { request in
            guard let url = request.url,
                  url.path.contains("/auth/register")
            else {
                throw URLError(.badServerResponse)
            }

            let response = [
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "token_type": "bearer",
                "user": [
                    "id": 456,
                    "email": email,
                    "first_name": firstName,
                    "last_name": lastName,
                    "created_at": ISO8601DateFormatter().string(from: Date()),
                    "last_login_at": ISO8601DateFormatter().string(from: Date()),
                    "notification_enabled": true
                ] as [String: Any]
            ] as [String: Any]

            return try self.createHTTPResponse(url: url, statusCode: 201, json: response)
        }
    }

    private func mockUserProfileResponse(captureHeaders: HeadersCapture) {
        MockURLProtocol.requestHandler = { request in
            captureHeaders.headers = request.allHTTPHeaderFields

            let url = request.url!
            let response = [
                "first_name": "Test",
                "last_name": "User",
                "notification_enabled": true
            ] as [String: Any]

            return try self.createHTTPResponse(url: url, statusCode: 200, json: response)
        }
    }

    private func mockTestTakingFlow(requestCount: RequestCounter) {
        MockURLProtocol.requestHandler = { request in
            requestCount.increment()
            let url = request.url!

            if url.path.contains("/test/start") {
                return try self.createStartTestResponse(url: url)
            } else if url.path.contains("/test/submit") {
                return try self.createSubmitTestResponse(url: url)
            }

            throw URLError(.badURL)
        }
    }

    private func createStartTestResponse(url: URL) throws -> (HTTPURLResponse, Data) {
        let response = [
            "session": [
                "id": 123,
                "user_id": 1,
                "started_at": ISO8601DateFormatter().string(from: Date()),
                "completed_at": nil as String?,
                "status": "in_progress"
            ] as [String: Any?],
            "questions": [
                [
                    "id": 1,
                    "question_text": "What is 2+2?",
                    "question_type": "math",
                    "difficulty_level": "easy",
                    "answer_options": ["3", "4", "5"]
                ],
                [
                    "id": 2,
                    "question_text": "What comes next: 1, 2, 3, ?",
                    "question_type": "pattern",
                    "difficulty_level": "easy",
                    "answer_options": ["4", "5", "6"]
                ]
            ],
            "total_questions": 2
        ] as [String: Any]

        return try createHTTPResponse(url: url, statusCode: 200, json: response)
    }

    private func createSubmitTestResponse(url: URL) throws -> (HTTPURLResponse, Data) {
        let response = [
            "session": [
                "id": 123,
                "user_id": 1,
                "started_at": ISO8601DateFormatter().string(from: Date().addingTimeInterval(-120)),
                "completed_at": ISO8601DateFormatter().string(from: Date()),
                "status": "completed"
            ] as [String: Any],
            "result": [
                "id": 1,
                "test_session_id": 123,
                "user_id": 1,
                "iq_score": 120,
                "percentile_rank": 84.0,
                "total_questions": 2,
                "correct_answers": 2,
                "accuracy_percentage": 100.0,
                "completion_time_seconds": 60,
                "completed_at": ISO8601DateFormatter().string(from: Date())
            ],
            "responses_count": 2,
            "message": "Test completed successfully"
        ] as [String: Any]

        return try createHTTPResponse(url: url, statusCode: 200, json: response)
    }

    private func submitTest(sessionId: Int) async throws -> TestSubmitResponse {
        let submitRequest = TestSubmission(
            sessionId: sessionId,
            responses: [
                QuestionResponse(questionId: 1, userAnswer: "4"),
                QuestionResponse(questionId: 2, userAnswer: "4")
            ]
        )

        return try await sut.request(
            endpoint: .testSubmit,
            method: .post,
            body: submitRequest,
            requiresAuth: true
        )
    }

    private func mockHTTPErrorResponse(statusCode: Int, detail: String) {
        MockURLProtocol.requestHandler = { request in
            let url = request.url!
            let response = ["detail": detail]
            return try self.createHTTPResponse(url: url, statusCode: statusCode, json: response)
        }
    }

    private func mockValidationErrorResponse() {
        MockURLProtocol.requestHandler = { request in
            let url = request.url!
            let response = [
                "detail": [
                    [
                        "loc": ["body", "email"],
                        "msg": "Invalid email format",
                        "type": "value_error"
                    ]
                ]
            ] as [String: Any]

            return try self.createHTTPResponse(url: url, statusCode: 422, json: response)
        }
    }

    private func mockTestHistoryResponse() {
        MockURLProtocol.requestHandler = { request in
            guard let url = request.url else {
                throw URLError(.badURL)
            }

            // Return paginated response format (BCQ-004)
            let paginatedResponse: [String: Any] = [
                "results": [
                    [
                        "id": 1,
                        "test_session_id": 1,
                        "user_id": 1,
                        "iq_score": 120,
                        "percentile_rank": 84.0,
                        "total_questions": 20,
                        "correct_answers": 15,
                        "accuracy_percentage": 75.0,
                        "completion_time_seconds": 1200,
                        "completed_at": ISO8601DateFormatter().string(from: Date())
                    ],
                    [
                        "id": 2,
                        "test_session_id": 2,
                        "user_id": 1,
                        "iq_score": 118,
                        "percentile_rank": 80.0,
                        "total_questions": 20,
                        "correct_answers": 14,
                        "accuracy_percentage": 70.0,
                        "completion_time_seconds": 1300,
                        "completed_at": ISO8601DateFormatter().string(from: Date().addingTimeInterval(-86400))
                    ]
                ],
                "total_count": 2,
                "limit": 50,
                "offset": 0,
                "has_more": false
            ]

            guard let data = try? JSONSerialization.data(withJSONObject: paginatedResponse),
                  let httpResponse = HTTPURLResponse(
                      url: url,
                      statusCode: 200,
                      httpVersion: nil,
                      headerFields: ["Content-Type": "application/json"]
                  )
            else {
                throw URLError(.cannotParseResponse)
            }

            return (httpResponse, data)
        }
    }

    private func mockActiveSessionResponse(hasActiveSession: Bool) {
        MockURLProtocol.requestHandler = { request in
            let url = request.url!

            if hasActiveSession {
                let response = [
                    "session": [
                        "id": 123,
                        "user_id": 1,
                        "started_at": ISO8601DateFormatter().string(from: Date()),
                        "completed_at": nil as String?,
                        "status": "in_progress"
                    ] as [String: Any?],
                    "questions_count": 5
                ] as [String: Any]

                return try self.createHTTPResponse(url: url, statusCode: 200, json: response)
            } else {
                // Backend returns null when no active session
                guard let httpResponse = HTTPURLResponse(
                    url: url,
                    statusCode: 200,
                    httpVersion: nil,
                    headerFields: ["Content-Type": "application/json"]
                ) else {
                    throw URLError(.cannotParseResponse)
                }

                let data = "null".data(using: .utf8)!
                return (httpResponse, data)
            }
        }
    }

    private func createHTTPResponse(
        url: URL,
        statusCode: Int,
        json: [String: Any]
    ) throws -> (HTTPURLResponse, Data) {
        guard let data = try? JSONSerialization.data(withJSONObject: json),
              let httpResponse = HTTPURLResponse(
                  url: url,
                  statusCode: statusCode,
                  httpVersion: nil,
                  headerFields: ["Content-Type": "application/json"]
              )
        else {
            throw URLError(.cannotParseResponse)
        }

        return (httpResponse, data)
    }

    private func assertThrowsAPIError(
        _ expectedError: APIError,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        do {
            let _: UserProfile = try await sut.request(
                endpoint: .userProfile,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )
            XCTFail("Should have thrown error", file: file, line: line)
        } catch let error as APIError {
            switch (error, expectedError) {
            case (.networkError(_), .networkError(_)),
                 (.unauthorized(_), .unauthorized(_)),
                 (.serverError(_, _), .serverError(_, _)):
                break // Success - correct error type
            default:
                XCTFail("Expected \(expectedError), got \(error)", file: file, line: line)
            }
        } catch {
            XCTFail("Unexpected error type: \(error)", file: file, line: line)
        }
    }
}

// MARK: - Helper Classes

/// Reference type wrapper for counting requests in escaping closures
private class RequestCounter {
    var count = 0

    func increment() {
        count += 1
    }
}

/// Reference type wrapper for capturing headers in escaping closures
private class HeadersCapture {
    var headers: [String: String]?
}

/// Mock authentication service for testing token refresh
private class MockAuthService: AuthServiceProtocol {
    var isAuthenticated: Bool = true
    var currentUser: AIQ.User?
    var refreshTokenCallCount = 0
    var logoutCallCount = 0

    func register(
        email _: String,
        password _: String,
        firstName _: String,
        lastName _: String,
        birthYear _: Int?,
        educationLevel _: EducationLevel?,
        country _: String?,
        region _: String?
    ) async throws -> AIQ.AuthResponse {
        fatalError("Not implemented for this test")
    }

    func login(email _: String, password _: String) async throws -> AIQ.AuthResponse {
        fatalError("Not implemented for this test")
    }

    func refreshToken() async throws -> AIQ.AuthResponse {
        refreshTokenCallCount += 1
        // Return a mock successful refresh response
        let user = AIQ.User(
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
        currentUser = user
        return AIQ.AuthResponse(
            accessToken: "new-access-token-\(refreshTokenCallCount)",
            refreshToken: "new-refresh-token-\(refreshTokenCallCount)",
            tokenType: "bearer",
            user: user
        )
    }

    func logout() async throws {
        logoutCallCount += 1
        isAuthenticated = false
        currentUser = nil
    }

    func getAccessToken() -> String? {
        "mock-access-token"
    }
}
