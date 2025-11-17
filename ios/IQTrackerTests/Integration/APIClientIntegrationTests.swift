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
            session: mockURLSession
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

        // Mock successful login response
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
                "user": [
                    "id": "123",
                    "email": email,
                    "first_name": "Test",
                    "last_name": "User"
                ]
            ] as [String: Any]

            let data = try! JSONSerialization.data(withJSONObject: response)
            let httpResponse = HTTPURLResponse(
                url: url,
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            return (httpResponse, data)
        }

        // When
        let loginRequest = LoginRequest(email: email, password: password)
        let result: AuthResponse = try await sut.request(
            "/auth/login",
            method: .POST,
            body: loginRequest
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

        // Mock successful registration response
        MockURLProtocol.requestHandler = { request in
            guard let url = request.url,
                  url.path.contains("/auth/register")
            else {
                throw URLError(.badServerResponse)
            }

            let response = [
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "user": [
                    "id": "456",
                    "email": email,
                    "first_name": firstName,
                    "last_name": lastName
                ]
            ] as [String: Any]

            let data = try! JSONSerialization.data(withJSONObject: response)
            let httpResponse = HTTPURLResponse(
                url: url,
                statusCode: 201,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            return (httpResponse, data)
        }

        // When
        let registrationRequest = RegistrationRequest(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName
        )
        let result: AuthResponse = try await sut.request(
            "/auth/register",
            method: .POST,
            body: registrationRequest
        )

        // Then
        XCTAssertEqual(result.accessToken, "new-access-token")
        XCTAssertEqual(result.user.email, email)
        XCTAssertEqual(result.user.firstName, firstName)
    }

    // MARK: - Token Management Integration Tests

    func testAutomaticTokenInjection() async throws {
        // Given - Set access token
        sut.setAccessToken("test-bearer-token")

        // Mock response that verifies Authorization header
        var capturedHeaders: [String: String]?
        MockURLProtocol.requestHandler = { request in
            capturedHeaders = request.allHTTPHeaderFields

            let url = request.url!
            let response = [
                "id": "123",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User"
            ] as [String: Any]

            let data = try! JSONSerialization.data(withJSONObject: response)
            let httpResponse = HTTPURLResponse(
                url: url,
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            return (httpResponse, data)
        }

        // When
        let _: UserProfile = try await sut.request("/user/profile", method: .GET)

        // Then - Verify Authorization header was included
        XCTAssertEqual(capturedHeaders?["Authorization"], "Bearer test-bearer-token")
    }

    // MARK: - Test Taking Flow Integration Tests

    func testCompleteTestTakingFlow() async throws {
        // Given
        sut.setAccessToken("valid-token")

        var requestCount = 0

        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            let url = request.url!

            if url.path.contains("/test/start") {
                // Mock start test response
                let response = [
                    "session": [
                        "id": "session-123",
                        "status": "in_progress",
                        "started_at": ISO8601DateFormatter().string(from: Date())
                    ],
                    "questions": [
                        [
                            "id": "q1",
                            "question_text": "What is 2+2?",
                            "question_type": "mathematical",
                            "answer_options": ["A": "3", "B": "4", "C": "5"]
                        ],
                        [
                            "id": "q2",
                            "question_text": "What comes next: 1, 2, 3, ?",
                            "question_type": "pattern_recognition",
                            "answer_options": ["A": "4", "B": "5", "C": "6"]
                        ]
                    ],
                    "total_questions": 2
                ] as [String: Any]

                let data = try! JSONSerialization.data(withJSONObject: response)
                let httpResponse = HTTPURLResponse(
                    url: url,
                    statusCode: 200,
                    httpVersion: nil,
                    headerFields: ["Content-Type": "application/json"]
                )!

                return (httpResponse, data)
            } else if url.path.contains("/test/submit") {
                // Mock submit test response
                let response = [
                    "result": [
                        "id": "result-123",
                        "iq_score": 120,
                        "total_questions": 2,
                        "correct_answers": 2,
                        "completion_time_seconds": 60,
                        "completed_at": ISO8601DateFormatter().string(from: Date())
                    ]
                ] as [String: Any]

                let data = try! JSONSerialization.data(withJSONObject: response)
                let httpResponse = HTTPURLResponse(
                    url: url,
                    statusCode: 200,
                    httpVersion: nil,
                    headerFields: ["Content-Type": "application/json"]
                )!

                return (httpResponse, data)
            }

            throw URLError(.badURL)
        }

        // When - Start test
        let startResponse: TestStartResponse = try await sut.request(
            "/test/start?question_count=2",
            method: .POST
        )

        // Then - Verify test started
        XCTAssertEqual(startResponse.session.status, "in_progress")
        XCTAssertEqual(startResponse.questions.count, 2)

        // When - Submit test
        let submitRequest = TestSubmitRequest(
            sessionId: startResponse.session.id,
            responses: [
                QuestionResponse(questionId: "q1", userAnswer: "4"),
                QuestionResponse(questionId: "q2", userAnswer: "4")
            ]
        )

        let submitResponse: TestSubmitResponse = try await sut.request(
            "/test/submit",
            method: .POST,
            body: submitRequest
        )

        // Then - Verify submission successful
        XCTAssertEqual(submitResponse.result.iqScore, 120)
        XCTAssertEqual(submitResponse.result.totalQuestions, 2)
        XCTAssertEqual(requestCount, 2)
    }

    // MARK: - Error Handling Integration Tests

    func testNetworkErrorHandling() async {
        // Given - Mock network error
        MockURLProtocol.requestHandler = { _ in
            throw URLError(.notConnectedToInternet)
        }

        // When/Then
        do {
            let _: UserProfile = try await sut.request("/user/profile", method: .GET)
            XCTFail("Should have thrown error")
        } catch let error as APIError {
            // Verify error is properly mapped
            if case .networkError = error {
                // Success - correct error type
            } else {
                XCTFail("Expected networkError, got \(error)")
            }
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    func testUnauthorizedErrorHandling() async {
        // Given - Mock 401 response
        MockURLProtocol.requestHandler = { request in
            let url = request.url!
            let response = ["detail": "Unauthorized"]
            let data = try! JSONSerialization.data(withJSONObject: response)
            let httpResponse = HTTPURLResponse(
                url: url,
                statusCode: 401,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            return (httpResponse, data)
        }

        // When/Then
        do {
            let _: UserProfile = try await sut.request("/user/profile", method: .GET)
            XCTFail("Should have thrown error")
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

    func testServerErrorHandling() async {
        // Given - Mock 500 response
        MockURLProtocol.requestHandler = { request in
            let url = request.url!
            let response = ["detail": "Internal Server Error"]
            let data = try! JSONSerialization.data(withJSONObject: response)
            let httpResponse = HTTPURLResponse(
                url: url,
                statusCode: 500,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            return (httpResponse, data)
        }

        // When/Then
        do {
            let _: UserProfile = try await sut.request("/user/profile", method: .GET)
            XCTFail("Should have thrown error")
        } catch let error as APIError {
            if case .serverError = error {
                // Success - correct error type
            } else {
                XCTFail("Expected serverError, got \(error)")
            }
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    func testValidationErrorHandling() async {
        // Given - Mock 422 validation error response
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

            let data = try! JSONSerialization.data(withJSONObject: response)
            let httpResponse = HTTPURLResponse(
                url: url,
                statusCode: 422,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            return (httpResponse, data)
        }

        // When/Then
        do {
            let request = LoginRequest(email: "invalid", password: "test")
            let _: AuthResponse = try await sut.request("/auth/login", method: .POST, body: request)
            XCTFail("Should have thrown error")
        } catch let error as APIError {
            if case .validationError = error {
                // Success - correct error type
            } else {
                XCTFail("Expected validationError, got \(error)")
            }
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    // MARK: - History and Results Integration Tests

    func testFetchTestHistory() async throws {
        // Given
        sut.setAccessToken("valid-token")

        MockURLProtocol.requestHandler = { request in
            let url = request.url!
            let response = [
                "results": [
                    [
                        "id": "result-1",
                        "iq_score": 120,
                        "total_questions": 20,
                        "correct_answers": 15,
                        "completed_at": ISO8601DateFormatter().string(from: Date())
                    ],
                    [
                        "id": "result-2",
                        "iq_score": 118,
                        "total_questions": 20,
                        "correct_answers": 14,
                        "completed_at": ISO8601DateFormatter().string(from: Date().addingTimeInterval(-86400))
                    ]
                ],
                "total_tests": 2
            ] as [String: Any]

            let data = try! JSONSerialization.data(withJSONObject: response)
            let httpResponse = HTTPURLResponse(
                url: url,
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            return (httpResponse, data)
        }

        // When
        let history: TestHistoryResponse = try await sut.request("/test/history", method: .GET)

        // Then
        XCTAssertEqual(history.results.count, 2)
        XCTAssertEqual(history.totalTests, 2)
        XCTAssertEqual(history.results[0].iqScore, 120)
        XCTAssertEqual(history.results[1].iqScore, 118)
    }
}

// MARK: - Mock URLProtocol

class MockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with _: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let handler = MockURLProtocol.requestHandler else {
            fatalError("Request handler is not set")
        }

        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {
        // Nothing to do
    }
}

// MARK: - Test Data Structures

struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct RegistrationRequest: Codable {
    let email: String
    let password: String
    let firstName: String
    let lastName: String

    enum CodingKeys: String, CodingKey {
        case email
        case password
        case firstName = "first_name"
        case lastName = "last_name"
    }
}

struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let user: UserProfile

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case user
    }
}

struct UserProfile: Codable {
    let id: String
    let email: String
    let firstName: String
    let lastName: String

    enum CodingKeys: String, CodingKey {
        case id
        case email
        case firstName = "first_name"
        case lastName = "last_name"
    }
}

struct TestStartResponse: Codable {
    let session: TestSession
    let questions: [Question]
    let totalQuestions: Int

    enum CodingKeys: String, CodingKey {
        case session
        case questions
        case totalQuestions = "total_questions"
    }
}

struct TestSession: Codable {
    let id: String
    let status: String
    let startedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case status
        case startedAt = "started_at"
    }
}

struct Question: Codable {
    let id: String
    let questionText: String
    let questionType: String
    let answerOptions: [String: String]

    enum CodingKeys: String, CodingKey {
        case id
        case questionText = "question_text"
        case questionType = "question_type"
        case answerOptions = "answer_options"
    }
}

struct TestSubmitRequest: Codable {
    let sessionId: String
    let responses: [QuestionResponse]

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case responses
    }
}

struct QuestionResponse: Codable {
    let questionId: String
    let userAnswer: String

    enum CodingKeys: String, CodingKey {
        case questionId = "question_id"
        case userAnswer = "user_answer"
    }
}

struct TestSubmitResponse: Codable {
    let result: TestResult
}

struct TestResult: Codable {
    let id: String
    let iqScore: Int
    let totalQuestions: Int
    let correctAnswers: Int
    let completionTimeSeconds: Int
    let completedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case iqScore = "iq_score"
        case totalQuestions = "total_questions"
        case correctAnswers = "correct_answers"
        case completionTimeSeconds = "completion_time_seconds"
        case completedAt = "completed_at"
    }
}

struct TestHistoryResponse: Codable {
    let results: [TestResult]
    let totalTests: Int

    enum CodingKeys: String, CodingKey {
        case results
        case totalTests = "total_tests"
    }
}
