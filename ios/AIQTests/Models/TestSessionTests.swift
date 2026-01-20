import AIQAPIClient
import XCTest

@testable import AIQ

final class TestSessionTests: XCTestCase {
    // MARK: - Date Decoder Helper

    private var iso8601Decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    private var iso8601Encoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }

    // MARK: - TestStatus Tests

    func testTestStatusRawValues() {
        XCTAssertEqual(TestStatus.inProgress.rawValue, "in_progress")
        XCTAssertEqual(TestStatus.completed.rawValue, "completed")
        XCTAssertEqual(TestStatus.abandoned.rawValue, "abandoned")
    }

    func testTestStatusDecoding() throws {
        let json = """
        "in_progress"
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let status = try JSONDecoder().decode(TestStatus.self, from: data)

        XCTAssertEqual(status, .inProgress)
    }

    func testTestStatusDecodingAllCases() throws {
        let testCases: [(String, TestStatus)] = [
            ("in_progress", .inProgress),
            ("completed", .completed),
            ("abandoned", .abandoned)
        ]

        for (rawValue, expectedStatus) in testCases {
            let json = "\"\(rawValue)\""
            let data = try XCTUnwrap(json.data(using: .utf8))
            let status = try JSONDecoder().decode(TestStatus.self, from: data)

            XCTAssertEqual(
                status,
                expectedStatus,
                "Failed to decode test status: \(rawValue)"
            )
        }
    }

    func testTestStatusEquality() {
        XCTAssertEqual(TestStatus.inProgress, TestStatus.inProgress)
        XCTAssertEqual(TestStatus.completed, TestStatus.completed)
        XCTAssertEqual(TestStatus.abandoned, TestStatus.abandoned)
        XCTAssertNotEqual(TestStatus.inProgress, TestStatus.completed)
        XCTAssertNotEqual(TestStatus.completed, TestStatus.abandoned)
    }

    func testTestStatusEncoding() throws {
        let status = TestStatus.inProgress
        let encoder = JSONEncoder()
        let data = try encoder.encode(status)
        let jsonString = try XCTUnwrap(String(data: data, encoding: .utf8))

        XCTAssertEqual(jsonString, "\"in_progress\"")
    }

    // MARK: - MockDataFactory Tests

    func testMakeTestSession_InProgressSessionNeverHasCompletedAt() {
        // Even if completedAt is explicitly provided, in-progress sessions should not have it
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "in_progress",
            startedAt: Date(),
            completedAt: Date() // Try to force a completedAt
        )
        XCTAssertNil(session.completedAt, "In-progress sessions should never have completedAt")
    }

    func testMakeTestSession_AbandonedSessionNeverHasCompletedAt() {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "abandoned",
            startedAt: Date(),
            completedAt: Date() // Try to force a completedAt
        )
        XCTAssertNil(session.completedAt, "Abandoned sessions should never have completedAt")
    }

    func testMakeTestSession_CompletedSessionAlwaysHasCompletedAt() {
        let startedAt = Date()
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "completed",
            startedAt: startedAt
        )
        XCTAssertNotNil(session.completedAt, "Completed sessions should always have completedAt")
        // Default is 30 minutes (1800 seconds) after start
        if let completedAt = session.completedAt {
            XCTAssertEqual(
                completedAt.timeIntervalSince(startedAt),
                1800,
                accuracy: 1.0,
                "Default completedAt should be 30 minutes after startedAt"
            )
        }
    }

    func testMakeTestSession_CompletedSessionUsesProvidedCompletedAt() {
        let startedAt = Date()
        let providedCompletedAt = startedAt.addingTimeInterval(900) // 15 minutes
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "completed",
            startedAt: startedAt,
            completedAt: providedCompletedAt
        )
        XCTAssertEqual(session.completedAt, providedCompletedAt)
    }

    // MARK: - TestSession Decoding Tests

    func testTestSessionDecodingWithAllFields() throws {
        let json = """
        {
            "id": 1,
            "user_id": 42,
            "started_at": "2024-01-15T10:30:00Z",
            "completed_at": "2024-01-15T11:00:00Z",
            "status": "completed",
            "time_limit_exceeded": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        XCTAssertEqual(session.id, 1)
        XCTAssertEqual(session.userId, 42)
        XCTAssertEqual(session.status, "completed")
        XCTAssertNotNil(session.completedAt)
        XCTAssertEqual(session.timeLimitExceeded, false)
    }

    func testTestSessionDecodingWithRequiredFieldsOnly() throws {
        let json = """
        {
            "id": 2,
            "user_id": 100,
            "started_at": "2024-01-15T10:30:00Z",
            "status": "in_progress"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        XCTAssertEqual(session.id, 2)
        XCTAssertEqual(session.userId, 100)
        XCTAssertEqual(session.status, "in_progress")
        XCTAssertNil(session.completedAt)
        XCTAssertNil(session.timeLimitExceeded)
    }

    func testTestSessionDecodingWithNullOptionalFields() throws {
        let json = """
        {
            "id": 3,
            "user_id": 200,
            "started_at": "2024-01-15T10:30:00Z",
            "completed_at": null,
            "status": "abandoned",
            "time_limit_exceeded": null
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        XCTAssertEqual(session.id, 3)
        XCTAssertEqual(session.status, "abandoned")
        XCTAssertNil(session.completedAt)
        XCTAssertNil(session.timeLimitExceeded)
    }

    func testTestSessionDecodingCodingKeysMapping() throws {
        let json = """
        {
            "id": 4,
            "user_id": 300,
            "started_at": "2024-01-15T10:30:00Z",
            "completed_at": "2024-01-15T11:00:00Z",
            "status": "completed",
            "time_limit_exceeded": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        // Verify snake_case fields are properly mapped to camelCase
        XCTAssertEqual(session.userId, 300)
        XCTAssertNotNil(session.startedAt)
        XCTAssertNotNil(session.completedAt)
        XCTAssertEqual(session.timeLimitExceeded, true)
    }

    func testTestSessionDecodingWithAllStatuses() throws {
        let testCases: [(String, String)] = [
            ("in_progress", "in_progress"),
            ("completed", "completed"),
            ("abandoned", "abandoned")
        ]

        for (rawValue, expectedStatus) in testCases {
            let json = """
            {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "status": "\(rawValue)"
            }
            """

            let data = try XCTUnwrap(json.data(using: .utf8))
            let session = try iso8601Decoder.decode(TestSession.self, from: data)

            XCTAssertEqual(
                session.status,
                expectedStatus,
                "Failed to decode test session with status: \(rawValue)"
            )
        }
    }

    // Note: The questions field is on TestSessionStatusResponse, not TestSessionResponse
    // This test is removed since TestSession (TestSessionResponse) does not have a questions property

    // MARK: - TestSession Equatable Tests

    func testTestSessionEquality() throws {
        let date1 = Date()
        let date2 = Date(timeIntervalSince1970: 1_705_315_800) // 2024-01-15T10:30:00Z

        let session1 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "completed",
            startedAt: date1,
            timeLimitExceeded: false
        )

        let session2 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "completed",
            startedAt: date1,
            timeLimitExceeded: false
        )

        XCTAssertEqual(session1, session2)
    }

    func testTestSessionInequalityDifferentId() throws {
        let date = Date()

        let session1 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "in_progress",
            startedAt: date
        )

        let session2 = MockDataFactory.makeTestSession(
            id: 2,
            userId: 42,
            status: "in_progress",
            startedAt: date
        )

        XCTAssertNotEqual(session1, session2)
    }

    func testTestSessionInequalityDifferentStatus() throws {
        let date = Date()

        let session1 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "in_progress",
            startedAt: date
        )

        let session2 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "completed",
            startedAt: date
        )

        XCTAssertNotEqual(session1, session2)
    }

    // MARK: - TestSession Encoding Tests

    func testTestSessionEncodingRoundTrip() throws {
        let startedAt = Date(timeIntervalSince1970: 1_705_315_800) // 2024-01-15T10:30:00Z
        let completedAt = Date(timeIntervalSince1970: 1_705_317_600) // 2024-01-15T11:00:00Z

        let session = MockDataFactory.makeTestSession(
            id: 123,
            userId: 456,
            status: "completed",
            startedAt: startedAt,
            timeLimitExceeded: false
        )

        let data = try iso8601Encoder.encode(session)
        let decodedSession = try iso8601Decoder.decode(TestSession.self, from: data)

        XCTAssertEqual(session.id, decodedSession.id)
        XCTAssertEqual(session.userId, decodedSession.userId)
        XCTAssertEqual(session.status, decodedSession.status)
        XCTAssertEqual(session.timeLimitExceeded, decodedSession.timeLimitExceeded)
    }

    func testTestSessionEncodingUsesSnakeCase() throws {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "completed",
            startedAt: Date(timeIntervalSince1970: 1_705_315_800),
            timeLimitExceeded: true
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(session)
        let jsonString = try XCTUnwrap(String(data: data, encoding: .utf8))

        // Verify snake_case keys are used in JSON
        XCTAssertTrue(jsonString.contains("user_id"))
        XCTAssertTrue(jsonString.contains("started_at"))
        XCTAssertTrue(jsonString.contains("completed_at"))
        XCTAssertTrue(jsonString.contains("time_limit_exceeded"))

        // Verify camelCase keys are NOT in JSON
        XCTAssertFalse(jsonString.contains("userId"))
        XCTAssertFalse(jsonString.contains("startedAt"))
        XCTAssertFalse(jsonString.contains("completedAt"))
        XCTAssertFalse(jsonString.contains("timeLimitExceeded"))
    }

    // MARK: - TestSession Identifiable Tests

    func testTestSessionIdentifiable() {
        let session = MockDataFactory.makeTestSession(
            id: 789,
            userId: 42,
            status: "in_progress",
            startedAt: Date()
        )

        XCTAssertEqual(session.id, 789)
    }

    // MARK: - StartTestResponse Tests

    func testStartTestResponseDecoding() throws {
        let json = """
        {
            "session": {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "status": "in_progress"
            },
            "questions": [
                {
                    "id": 1,
                    "question_text": "Test question",
                    "question_type": "pattern",
                    "difficulty_level": "easy"
                }
            ],
            "total_questions": 20
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let response = try iso8601Decoder.decode(StartTestResponse.self, from: data)

        XCTAssertEqual(response.session.id, 1)
        XCTAssertEqual(response.questions.count, 1)
        XCTAssertEqual(response.totalQuestions, 20)
    }

    func testStartTestResponseCodingKeysMapping() throws {
        let json = """
        {
            "session": {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "status": "in_progress"
            },
            "questions": [],
            "total_questions": 25
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let response = try iso8601Decoder.decode(StartTestResponse.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(response.totalQuestions, 25)
    }

    func testStartTestResponseEquality() throws {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "in_progress",
            startedAt: Date()
        )

        let question = Components.Schemas.QuestionResponse(
            answerOptions: nil,
            difficultyLevel: "easy",
            explanation: nil,
            id: 1,
            questionText: "Test",
            questionType: "pattern"
        )

        let response1 = StartTestResponse(
            questions: [question],
            session: session,
            totalQuestions: 20
        )

        let response2 = StartTestResponse(
            questions: [question],
            session: session,
            totalQuestions: 20
        )

        XCTAssertEqual(response1, response2)
    }

    func testStartTestResponseEncodingRoundTrip() throws {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "in_progress",
            startedAt: Date(timeIntervalSince1970: 1_705_315_800)
        )

        let response = StartTestResponse(
            questions: [],
            session: session,
            totalQuestions: 20
        )

        let data = try iso8601Encoder.encode(response)
        let decodedResponse = try iso8601Decoder.decode(StartTestResponse.self, from: data)

        XCTAssertEqual(response.totalQuestions, decodedResponse.totalQuestions)
        XCTAssertEqual(response.session.id, decodedResponse.session.id)
    }

    // MARK: - TestSubmission Tests

    func testTestSubmissionInitializationWithDefaultTimeLimitExceeded() {
        let response = try! QuestionResponse.validated(questionId: 1, userAnswer: "42")

        let submission = TestSubmission(
            responses: [response],
            sessionId: 1
        )

        XCTAssertEqual(submission.sessionId, 1)
        XCTAssertEqual(submission.responses.count, 1)
        XCTAssertNil(submission.timeLimitExceeded)
    }

    func testTestSubmissionInitializationWithExplicitTimeLimitExceeded() {
        let response = try! QuestionResponse.validated(questionId: 1, userAnswer: "42")

        let submission = TestSubmission(
            responses: [response],
            sessionId: 1,
            timeLimitExceeded: true
        )

        XCTAssertEqual(submission.sessionId, 1)
        XCTAssertEqual(submission.responses.count, 1)
        XCTAssertEqual(submission.timeLimitExceeded, true)
    }

    func testTestSubmissionDecoding() throws {
        let json = """
        {
            "session_id": 42,
            "responses": [
                {
                    "question_id": 1,
                    "user_answer": "Answer 1",
                    "time_spent_seconds": 30
                },
                {
                    "question_id": 2,
                    "user_answer": "Answer 2",
                    "time_spent_seconds": 45
                }
            ],
            "time_limit_exceeded": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let submission = try JSONDecoder().decode(TestSubmission.self, from: data)

        XCTAssertEqual(submission.sessionId, 42)
        XCTAssertEqual(submission.responses.count, 2)
        XCTAssertEqual(submission.timeLimitExceeded, true)
    }

    func testTestSubmissionCodingKeysMapping() throws {
        let json = """
        {
            "session_id": 100,
            "responses": [],
            "time_limit_exceeded": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let submission = try JSONDecoder().decode(TestSubmission.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(submission.sessionId, 100)
        XCTAssertEqual(submission.timeLimitExceeded, false)
    }

    func testTestSubmissionEquality() {
        let response = try! QuestionResponse.validated(questionId: 1, userAnswer: "42")

        let submission1 = TestSubmission(
            responses: [response],
            sessionId: 1,
            timeLimitExceeded: false
        )

        let submission2 = TestSubmission(
            responses: [response],
            sessionId: 1,
            timeLimitExceeded: false
        )

        XCTAssertEqual(submission1, submission2)
    }

    func testTestSubmissionEncodingRoundTrip() throws {
        let response = try! QuestionResponse.validated(questionId: 1, userAnswer: "Test answer", timeSpentSeconds: 30)

        let submission = TestSubmission(
            responses: [response],
            sessionId: 42,
            timeLimitExceeded: true
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(submission)

        let decoder = JSONDecoder()
        let decodedSubmission = try decoder.decode(TestSubmission.self, from: data)

        XCTAssertEqual(submission.sessionId, decodedSubmission.sessionId)
        XCTAssertEqual(submission.responses.count, decodedSubmission.responses.count)
        XCTAssertEqual(submission.timeLimitExceeded, decodedSubmission.timeLimitExceeded)
    }

    func testTestSubmissionEncodingUsesSnakeCase() throws {
        let submission = TestSubmission(
            responses: [],
            sessionId: 1,
            timeLimitExceeded: true
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(submission)
        let jsonString = try XCTUnwrap(String(data: data, encoding: .utf8))

        // Verify snake_case keys are used in JSON
        XCTAssertTrue(jsonString.contains("session_id"))
        XCTAssertTrue(jsonString.contains("time_limit_exceeded"))

        // Verify camelCase keys are NOT in JSON
        XCTAssertFalse(jsonString.contains("sessionId"))
        XCTAssertFalse(jsonString.contains("timeLimitExceeded"))
    }

    // MARK: - TestSubmitResponse Tests

    func testTestSubmitResponseDecoding() throws {
        let json = """
        {
            "session": {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T11:00:00Z",
                "status": "completed"
            },
            "result": {
                "id": 100,
                "test_session_id": 1,
                "user_id": 42,
                "iq_score": 120,
                "total_questions": 20,
                "correct_answers": 18,
                "accuracy_percentage": 90.0,
                "completed_at": "2024-01-15T11:00:00Z"
            },
            "responses_count": 20,
            "message": "Test completed successfully"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let response = try iso8601Decoder.decode(TestSubmitResponse.self, from: data)

        XCTAssertEqual(response.session.id, 1)
        XCTAssertEqual(response.result.id, 100)
        XCTAssertEqual(response.responsesCount, 20)
        XCTAssertEqual(response.message, "Test completed successfully")
    }

    func testTestSubmitResponseCodingKeysMapping() throws {
        let json = """
        {
            "session": {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "status": "completed"
            },
            "result": {
                "id": 100,
                "test_session_id": 1,
                "user_id": 42,
                "iq_score": 120,
                "total_questions": 20,
                "correct_answers": 18,
                "accuracy_percentage": 90.0,
                "completed_at": "2024-01-15T11:00:00Z"
            },
            "responses_count": 15,
            "message": "Success"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let response = try iso8601Decoder.decode(TestSubmitResponse.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(response.responsesCount, 15)
    }

    func testTestSubmitResponseEquality() throws {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "completed",
            startedAt: Date(),
            timeLimitExceeded: false
        )

        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: 1800,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 100,
            iqScore: 120,
            percentileRank: 85.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 1,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        let response1 = TestSubmitResponse(
            message: "Success",
            responsesCount: 20,
            result: result,
            session: session
        )

        let response2 = TestSubmitResponse(
            message: "Success",
            responsesCount: 20,
            result: result,
            session: session
        )

        XCTAssertEqual(response1, response2)
    }

    // MARK: - TestAbandonResponse Tests

    func testTestAbandonResponseDecoding() throws {
        let json = """
        {
            "session": {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "status": "abandoned"
            },
            "message": "Test abandoned",
            "responses_saved": 5
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let response = try iso8601Decoder.decode(TestAbandonResponse.self, from: data)

        XCTAssertEqual(response.session.id, 1)
        XCTAssertEqual(response.session.status, "abandoned")
        XCTAssertEqual(response.message, "Test abandoned")
        XCTAssertEqual(response.responsesSaved, 5)
    }

    func testTestAbandonResponseCodingKeysMapping() throws {
        let json = """
        {
            "session": {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "status": "abandoned"
            },
            "message": "Abandoned",
            "responses_saved": 10
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let response = try iso8601Decoder.decode(TestAbandonResponse.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(response.responsesSaved, 10)
    }

    func testTestAbandonResponseEquality() throws {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "abandoned",
            startedAt: Date()
        )

        let response1 = TestAbandonResponse(
            message: "Abandoned",
            responsesSaved: 5,
            session: session
        )

        let response2 = TestAbandonResponse(
            message: "Abandoned",
            responsesSaved: 5,
            session: session
        )

        XCTAssertEqual(response1, response2)
    }

    // MARK: - SubmittedTestResult Tests

    func testSubmittedTestResultDecodingWithAllFields() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 42,
            "iq_score": 120,
            "percentile_rank": 85.5,
            "total_questions": 20,
            "correct_answers": 18,
            "accuracy_percentage": 90.0,
            "completion_time_seconds": 1800,
            "completed_at": "2024-01-15T11:00:00Z",
            "response_time_flags": {
                "total_time_seconds": 1800,
                "mean_time_per_question": 90.0,
                "median_time_per_question": 85.0,
                "std_time_per_question": 15.0,
                "anomalies": [],
                "flags": [],
                "validity_concern": false
            },
            "domain_scores": {
                "pattern": {
                    "correct": 3,
                    "total": 4,
                    "pct": 75.0,
                    "percentile": 80.0
                }
            },
            "strongest_domain": "pattern",
            "weakest_domain": "math",
            "confidence_interval": {
                "lower": 115,
                "upper": 125,
                "confidence_level": 0.95,
                "standard_error": 2.5
            }
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let result = try iso8601Decoder.decode(SubmittedTestResult.self, from: data)

        XCTAssertEqual(result.id, 1)
        XCTAssertEqual(result.testSessionId, 10)
        XCTAssertEqual(result.userId, 42)
        XCTAssertEqual(result.iqScore, 120)
        XCTAssertEqual(result.percentileRank, 85.5)
        XCTAssertEqual(result.totalQuestions, 20)
        XCTAssertEqual(result.correctAnswers, 18)
        XCTAssertEqual(result.accuracyPercentage, 90.0)
        XCTAssertEqual(result.completionTimeSeconds, 1800)
        XCTAssertNotNil(result.responseTimeFlags)
        XCTAssertNotNil(result.domainScores)
        XCTAssertEqual(result.strongestDomain, "pattern")
        XCTAssertEqual(result.weakestDomain, "math")
        XCTAssertNotNil(result.confidenceInterval)
    }

    func testSubmittedTestResultDecodingWithRequiredFieldsOnly() throws {
        let json = """
        {
            "id": 2,
            "test_session_id": 20,
            "user_id": 100,
            "iq_score": 110,
            "total_questions": 20,
            "correct_answers": 15,
            "accuracy_percentage": 75.0,
            "completed_at": "2024-01-15T11:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let result = try iso8601Decoder.decode(SubmittedTestResult.self, from: data)

        XCTAssertEqual(result.id, 2)
        XCTAssertEqual(result.iqScore, 110)
        XCTAssertNil(result.percentileRank)
        XCTAssertNil(result.completionTimeSeconds)
        XCTAssertNil(result.responseTimeFlags)
        XCTAssertNil(result.domainScores)
        XCTAssertNil(result.strongestDomain)
        XCTAssertNil(result.weakestDomain)
        XCTAssertNil(result.confidenceInterval)
    }

    func testSubmittedTestResultDecodingCodingKeysMapping() throws {
        let json = """
        {
            "id": 3,
            "test_session_id": 30,
            "user_id": 200,
            "iq_score": 130,
            "percentile_rank": 95.0,
            "total_questions": 20,
            "correct_answers": 19,
            "accuracy_percentage": 95.0,
            "completion_time_seconds": 1500,
            "completed_at": "2024-01-15T11:00:00Z",
            "strongest_domain": "logic",
            "weakest_domain": "spatial"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let result = try iso8601Decoder.decode(SubmittedTestResult.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(result.testSessionId, 30)
        XCTAssertEqual(result.userId, 200)
        XCTAssertEqual(result.iqScore, 130)
        XCTAssertEqual(result.percentileRank, 95.0)
        XCTAssertEqual(result.totalQuestions, 20)
        XCTAssertEqual(result.correctAnswers, 19)
        XCTAssertEqual(result.accuracyPercentage, 95.0)
        XCTAssertEqual(result.completionTimeSeconds, 1500)
        XCTAssertEqual(result.strongestDomain, "logic")
        XCTAssertEqual(result.weakestDomain, "spatial")
    }

    // MARK: - SubmittedTestResult Computed Properties Tests

    func testSubmittedTestResultAccuracyComputed() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.accuracy, 0.9, accuracy: 0.0001)
    }

    func testSubmittedTestResultCompletionTimeFormattedWithTime() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: 1825, // 30:25
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.completionTimeFormatted, "30:25")
    }

    func testSubmittedTestResultCompletionTimeFormattedWithoutTime() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.completionTimeFormatted, "N/A")
    }

    func testSubmittedTestResultPercentileFormattedWithPercentile() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: 84.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.percentileFormatted, "Top 25%")
    }

    func testSubmittedTestResultPercentileFormattedWithoutPercentile() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertNil(result.percentileFormatted)
    }

    func testSubmittedTestResultPercentileDescriptionWithPercentile() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: 84.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.percentileDescription, "84th percentile")
    }

    func testSubmittedTestResultPercentileDescriptionWithoutPercentile() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertNil(result.percentileDescription)
    }

    func testSubmittedTestResultScoreWithConfidenceIntervalPresent() {
        let confidenceInterval = ConfidenceInterval(
            confidenceLevel: 0.95,
            lower: 115,
            standardError: 2.5,
            upper: 125
        )

        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: Components.Schemas.TestResultResponse.ConfidenceIntervalPayload(value1: confidenceInterval),
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.scoreWithConfidenceInterval, "120 (115-125)")
    }

    func testSubmittedTestResultScoreWithConfidenceIntervalAbsent() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.scoreWithConfidenceInterval, "120")
    }

    func testSubmittedTestResultScoreAccessibilityDescriptionWithConfidenceInterval() {
        let confidenceInterval = ConfidenceInterval(
            confidenceLevel: 0.95,
            lower: 115,
            standardError: 2.5,
            upper: 125
        )

        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: Components.Schemas.TestResultResponse.ConfidenceIntervalPayload(value1: confidenceInterval),
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(
            result.scoreAccessibilityDescription,
            "IQ score 120, range 115 to 125"
        )
    }

    func testSubmittedTestResultScoreAccessibilityDescriptionWithoutConfidenceInterval() {
        let result = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result.scoreAccessibilityDescription, "IQ score 120")
    }

    // MARK: - SubmittedTestResult Equatable Tests

    func testSubmittedTestResultEquality() {
        let date = Date()

        let result1 = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: date,
            completionTimeSeconds: 1800,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: 85.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        let result2 = SubmittedTestResult(
            accuracyPercentage: 90.0,
            completedAt: date,
            completionTimeSeconds: 1800,
            confidenceInterval: nil,
            correctAnswers: 18,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: 85.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )

        XCTAssertEqual(result1, result2)
    }

    // MARK: - ResponseTimeFlags Tests

    func testResponseTimeFlagsDecodingWithAllFields() throws {
        let json = """
        {
            "total_time_seconds": 1800,
            "mean_time_per_question": 90.0,
            "median_time_per_question": 85.0,
            "std_time_per_question": 15.0,
            "anomalies": [
                {
                    "question_id": 5,
                    "time_seconds": 300,
                    "anomaly_type": "slow",
                    "z_score": 3.5
                }
            ],
            "flags": ["rushing_detected"],
            "validity_concern": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let flags = try JSONDecoder().decode(ResponseTimeFlags.self, from: data)

        XCTAssertEqual(flags.totalTimeSeconds, 1800)
        XCTAssertEqual(flags.meanTimePerQuestion, 90.0)
        XCTAssertEqual(flags.medianTimePerQuestion, 85.0)
        XCTAssertEqual(flags.stdTimePerQuestion, 15.0)
        XCTAssertEqual(flags.anomalies?.count, 1)
        XCTAssertEqual(flags.flags?.count, 1)
        XCTAssertEqual(flags.validityConcern, true)
    }

    func testResponseTimeFlagsDecodingWithNullFields() throws {
        let json = """
        {
            "total_time_seconds": null,
            "mean_time_per_question": null,
            "median_time_per_question": null,
            "std_time_per_question": null,
            "anomalies": null,
            "flags": null,
            "validity_concern": null
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let flags = try JSONDecoder().decode(ResponseTimeFlags.self, from: data)

        XCTAssertNil(flags.totalTimeSeconds)
        XCTAssertNil(flags.meanTimePerQuestion)
        XCTAssertNil(flags.medianTimePerQuestion)
        XCTAssertNil(flags.stdTimePerQuestion)
        XCTAssertNil(flags.anomalies)
        XCTAssertNil(flags.flags)
        XCTAssertNil(flags.validityConcern)
    }

    func testResponseTimeFlagsCodingKeysMapping() throws {
        let json = """
        {
            "total_time_seconds": 1000,
            "mean_time_per_question": 50.0,
            "median_time_per_question": 48.0,
            "std_time_per_question": 10.0,
            "validity_concern": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let flags = try JSONDecoder().decode(ResponseTimeFlags.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(flags.totalTimeSeconds, 1000)
        XCTAssertEqual(flags.meanTimePerQuestion, 50.0)
        XCTAssertEqual(flags.medianTimePerQuestion, 48.0)
        XCTAssertEqual(flags.stdTimePerQuestion, 10.0)
        XCTAssertEqual(flags.validityConcern, false)
    }

    func testResponseTimeFlagsEquality() {
        let anomaly = ResponseTimeAnomaly(
            questionId: 1,
            timeSeconds: 300,
            anomalyType: "slow",
            zScore: 3.5
        )

        let flags1 = ResponseTimeFlags(
            totalTimeSeconds: 1800,
            meanTimePerQuestion: 90.0,
            medianTimePerQuestion: 85.0,
            stdTimePerQuestion: 15.0,
            anomalies: [anomaly],
            flags: ["rushing"],
            validityConcern: true
        )

        let flags2 = ResponseTimeFlags(
            totalTimeSeconds: 1800,
            meanTimePerQuestion: 90.0,
            medianTimePerQuestion: 85.0,
            stdTimePerQuestion: 15.0,
            anomalies: [anomaly],
            flags: ["rushing"],
            validityConcern: true
        )

        XCTAssertEqual(flags1, flags2)
    }

    // MARK: - ResponseTimeAnomaly Tests

    func testResponseTimeAnomalyDecodingWithAllFields() throws {
        let json = """
        {
            "question_id": 5,
            "time_seconds": 300,
            "anomaly_type": "slow",
            "z_score": 3.5
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let anomaly = try JSONDecoder().decode(ResponseTimeAnomaly.self, from: data)

        XCTAssertEqual(anomaly.questionId, 5)
        XCTAssertEqual(anomaly.timeSeconds, 300)
        XCTAssertEqual(anomaly.anomalyType, "slow")
        XCTAssertEqual(anomaly.zScore, 3.5)
    }

    func testResponseTimeAnomalyDecodingWithNullZScore() throws {
        let json = """
        {
            "question_id": 10,
            "time_seconds": 10,
            "anomaly_type": "fast",
            "z_score": null
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let anomaly = try JSONDecoder().decode(ResponseTimeAnomaly.self, from: data)

        XCTAssertEqual(anomaly.questionId, 10)
        XCTAssertEqual(anomaly.timeSeconds, 10)
        XCTAssertEqual(anomaly.anomalyType, "fast")
        XCTAssertNil(anomaly.zScore)
    }

    func testResponseTimeAnomalyCodingKeysMapping() throws {
        let json = """
        {
            "question_id": 15,
            "time_seconds": 200,
            "anomaly_type": "moderate",
            "z_score": 2.0
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let anomaly = try JSONDecoder().decode(ResponseTimeAnomaly.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(anomaly.questionId, 15)
        XCTAssertEqual(anomaly.timeSeconds, 200)
        XCTAssertEqual(anomaly.anomalyType, "moderate")
        XCTAssertEqual(anomaly.zScore, 2.0)
    }

    func testResponseTimeAnomalyEquality() {
        let anomaly1 = ResponseTimeAnomaly(
            questionId: 1,
            timeSeconds: 300,
            anomalyType: "slow",
            zScore: 3.5
        )

        let anomaly2 = ResponseTimeAnomaly(
            questionId: 1,
            timeSeconds: 300,
            anomalyType: "slow",
            zScore: 3.5
        )

        XCTAssertEqual(anomaly1, anomaly2)
    }

    func testResponseTimeAnomalyEncodingRoundTrip() throws {
        let anomaly = ResponseTimeAnomaly(
            questionId: 5,
            timeSeconds: 250,
            anomalyType: "slow",
            zScore: 2.8
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(anomaly)

        let decoder = JSONDecoder()
        let decodedAnomaly = try decoder.decode(ResponseTimeAnomaly.self, from: data)

        XCTAssertEqual(anomaly.questionId, decodedAnomaly.questionId)
        XCTAssertEqual(anomaly.timeSeconds, decodedAnomaly.timeSeconds)
        XCTAssertEqual(anomaly.anomalyType, decodedAnomaly.anomalyType)
        XCTAssertEqual(anomaly.zScore, decodedAnomaly.zScore)
    }

    // MARK: - Edge Cases and Validation Tests

    func testTestSessionDecodingFailsWithMissingId() throws {
        let json = """
        {
            "user_id": 42,
            "started_at": "2024-01-15T10:30:00Z",
            "status": "in_progress"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try iso8601Decoder.decode(TestSession.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing id")
        }
    }

    func testTestSessionDecodingFailsWithMissingUserId() throws {
        let json = """
        {
            "id": 1,
            "started_at": "2024-01-15T10:30:00Z",
            "status": "in_progress"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try iso8601Decoder.decode(TestSession.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing user_id")
        }
    }

    func testTestSessionDecodingFailsWithMissingStartedAt() throws {
        let json = """
        {
            "id": 1,
            "user_id": 42,
            "status": "in_progress"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try iso8601Decoder.decode(TestSession.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing started_at")
        }
    }

    func testTestSessionDecodingFailsWithMissingStatus() throws {
        let json = """
        {
            "id": 1,
            "user_id": 42,
            "started_at": "2024-01-15T10:30:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try iso8601Decoder.decode(TestSession.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing status")
        }
    }

    func testTestSessionDecodingWithInvalidStatus() throws {
        // Note: Since status is a String (not enum), any value is valid.
        // The backend is responsible for validating status values.
        let json = """
        {
            "id": 1,
            "user_id": 42,
            "started_at": "2024-01-15T10:30:00Z",
            "status": "invalid_status"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        // The session decodes successfully, status is just a string
        XCTAssertEqual(session.status, "invalid_status")
    }

    func testTestSessionDecodingWithZeroIds() throws {
        let json = """
        {
            "id": 0,
            "user_id": 0,
            "started_at": "2024-01-15T10:30:00Z",
            "status": "in_progress"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        XCTAssertEqual(session.id, 0)
        XCTAssertEqual(session.userId, 0)
    }

    func testTestSessionDecodingWithNegativeIds() throws {
        let json = """
        {
            "id": -1,
            "user_id": -100,
            "started_at": "2024-01-15T10:30:00Z",
            "status": "completed"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        XCTAssertEqual(session.id, -1)
        XCTAssertEqual(session.userId, -100)
    }

    func testTestSessionDecodingWithLargeIds() throws {
        let json = """
        {
            "id": 9223372036854775807,
            "user_id": 9223372036854775806,
            "started_at": "2024-01-15T10:30:00Z",
            "status": "abandoned"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let session = try iso8601Decoder.decode(TestSession.self, from: data)

        XCTAssertEqual(session.id, 9_223_372_036_854_775_807)
        XCTAssertEqual(session.userId, 9_223_372_036_854_775_806)
    }

    func testTestSubmissionDecodingFailsWithMissingSessionId() throws {
        let json = """
        {
            "responses": [],
            "time_limit_exceeded": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try JSONDecoder().decode(TestSubmission.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing session_id")
        }
    }

    func testTestSubmissionDecodingFailsWithMissingResponses() throws {
        let json = """
        {
            "session_id": 1,
            "time_limit_exceeded": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try JSONDecoder().decode(TestSubmission.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing responses")
        }
    }

    func testTestSubmissionDecodingWithMissingTimeLimitExceeded() throws {
        // Note: timeLimitExceeded is optional and defaults to nil
        let json = """
        {
            "session_id": 1,
            "responses": []
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let submission = try JSONDecoder().decode(TestSubmission.self, from: data)

        XCTAssertEqual(submission.sessionId, 1)
        XCTAssertEqual(submission.responses.count, 0)
        XCTAssertNil(submission.timeLimitExceeded)
    }

    func testTestSubmissionWithEmptyResponses() {
        let submission = TestSubmission(
            responses: [],
            sessionId: 1,
            timeLimitExceeded: false
        )

        XCTAssertEqual(submission.responses.count, 0)
    }

    func testTestSubmissionWithManyResponses() {
        let responses = (1 ... 100).map { try! QuestionResponse.validated(questionId: $0, userAnswer: "Answer \($0)") }

        let submission = TestSubmission(
            responses: responses,
            sessionId: 1,
            timeLimitExceeded: true
        )

        XCTAssertEqual(submission.responses.count, 100)
    }

    func testSubmittedTestResultDecodingFailsWithMissingId() throws {
        let json = """
        {
            "test_session_id": 1,
            "user_id": 42,
            "iq_score": 120,
            "total_questions": 20,
            "correct_answers": 18,
            "accuracy_percentage": 90.0,
            "completed_at": "2024-01-15T11:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try iso8601Decoder.decode(SubmittedTestResult.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing id")
        }
    }

    func testSubmittedTestResultDecodingFailsWithMissingIqScore() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 1,
            "user_id": 42,
            "total_questions": 20,
            "correct_answers": 18,
            "accuracy_percentage": 90.0,
            "completed_at": "2024-01-15T11:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))

        XCTAssertThrowsError(try iso8601Decoder.decode(SubmittedTestResult.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing iq_score")
        }
    }

    func testSubmittedTestResultWithZeroIqScore() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 42,
            "iq_score": 0,
            "total_questions": 20,
            "correct_answers": 0,
            "accuracy_percentage": 0.0,
            "completed_at": "2024-01-15T11:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let result = try iso8601Decoder.decode(SubmittedTestResult.self, from: data)

        XCTAssertEqual(result.iqScore, 0)
        XCTAssertEqual(result.correctAnswers, 0)
        XCTAssertEqual(result.accuracyPercentage, 0.0)
    }

    func testSubmittedTestResultWithHighIqScore() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 42,
            "iq_score": 160,
            "total_questions": 20,
            "correct_answers": 20,
            "accuracy_percentage": 100.0,
            "completed_at": "2024-01-15T11:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let result = try iso8601Decoder.decode(SubmittedTestResult.self, from: data)

        XCTAssertEqual(result.iqScore, 160)
        XCTAssertEqual(result.correctAnswers, 20)
        XCTAssertEqual(result.accuracyPercentage, 100.0)
    }

    func testSubmittedTestResultWithZeroCompletionTime() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 42,
            "iq_score": 120,
            "total_questions": 20,
            "correct_answers": 18,
            "accuracy_percentage": 90.0,
            "completion_time_seconds": 0,
            "completed_at": "2024-01-15T11:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let result = try iso8601Decoder.decode(SubmittedTestResult.self, from: data)

        XCTAssertEqual(result.completionTimeSeconds, 0)
        XCTAssertEqual(result.completionTimeFormatted, "0:00")
    }

    func testSubmittedTestResultWithVeryLongCompletionTime() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 42,
            "iq_score": 120,
            "total_questions": 20,
            "correct_answers": 18,
            "accuracy_percentage": 90.0,
            "completion_time_seconds": 7200,
            "completed_at": "2024-01-15T11:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let result = try iso8601Decoder.decode(SubmittedTestResult.self, from: data)

        XCTAssertEqual(result.completionTimeSeconds, 7200)
        XCTAssertEqual(result.completionTimeFormatted, "120:00")
    }

    func testSubmittedTestResultPercentileFormattedEdgeCases() {
        // Test 0th percentile
        let result0 = SubmittedTestResult(
            accuracyPercentage: 50.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 10,
            domainScores: nil,
            id: 1,
            iqScore: 70,
            percentileRank: 0.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )
        XCTAssertEqual(result0.percentileFormatted, "Lower 50%")

        // Test 100th percentile
        let result100 = SubmittedTestResult(
            accuracyPercentage: 100.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 20,
            domainScores: nil,
            id: 1,
            iqScore: 160,
            percentileRank: 100.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )
        XCTAssertEqual(result100.percentileFormatted, "Top 2%")

        // Test 50th percentile (median)
        let result50 = SubmittedTestResult(
            accuracyPercentage: 75.0,
            completedAt: Date(),
            completionTimeSeconds: nil,
            confidenceInterval: nil,
            correctAnswers: 15,
            domainScores: nil,
            id: 1,
            iqScore: 100,
            percentileRank: 50.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 10,
            totalQuestions: 20,
            userId: 42,
            weakestDomain: nil
        )
        XCTAssertEqual(result50.percentileFormatted, "Top 50%")
    }

    func testResponseTimeAnomalyWithZeroTime() throws {
        let json = """
        {
            "question_id": 1,
            "time_seconds": 0,
            "anomaly_type": "instant",
            "z_score": -5.0
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let anomaly = try JSONDecoder().decode(ResponseTimeAnomaly.self, from: data)

        XCTAssertEqual(anomaly.timeSeconds, 0)
    }

    func testResponseTimeAnomalyWithNegativeTime() throws {
        let json = """
        {
            "question_id": 1,
            "time_seconds": -10,
            "anomaly_type": "invalid"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let anomaly = try JSONDecoder().decode(ResponseTimeAnomaly.self, from: data)

        XCTAssertEqual(anomaly.timeSeconds, -10)
    }

    func testResponseTimeFlagsWithEmptyArrays() throws {
        let json = """
        {
            "anomalies": [],
            "flags": []
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let flags = try JSONDecoder().decode(ResponseTimeFlags.self, from: data)

        XCTAssertEqual(flags.anomalies?.count, 0)
        XCTAssertEqual(flags.flags?.count, 0)
    }

    func testResponseTimeFlagsWithManyAnomalies() throws {
        let anomaliesJSON = (1 ... 20).map { """
        {
            "question_id": \($0),
            "time_seconds": \($0 * 100),
            "anomaly_type": "slow",
            "z_score": 2.5
        }
        """ }.joined(separator: ",")

        let json = """
        {
            "anomalies": [\(anomaliesJSON)]
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let flags = try JSONDecoder().decode(ResponseTimeFlags.self, from: data)

        XCTAssertEqual(flags.anomalies?.count, 20)
    }

    // MARK: - Test Status Transition Logic Tests

    func testStatusTransitionFromInProgressToCompleted() {
        let session1 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "in_progress",
            startedAt: Date()
        )

        let session2 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "completed",
            startedAt: session1.startedAt,
            timeLimitExceeded: false
        )

        XCTAssertEqual(session1.status, "in_progress")
        XCTAssertNil(session1.completedAt)

        XCTAssertEqual(session2.status, "completed")
        XCTAssertNotNil(session2.completedAt)
    }

    func testStatusTransitionFromInProgressToAbandoned() {
        let session1 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "in_progress",
            startedAt: Date()
        )

        let session2 = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "abandoned",
            startedAt: session1.startedAt
        )

        XCTAssertEqual(session1.status, "in_progress")
        XCTAssertEqual(session2.status, "abandoned")
    }

    func testCompletedSessionHasCompletedAt() {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "completed",
            startedAt: Date(),
            timeLimitExceeded: false
        )

        XCTAssertEqual(session.status, "completed")
        XCTAssertNotNil(session.completedAt)
    }

    func testInProgressSessionNoCompletedAt() {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "in_progress",
            startedAt: Date()
        )

        XCTAssertEqual(session.status, "in_progress")
        XCTAssertNil(session.completedAt)
    }

    func testAbandonedSessionMayNotHaveCompletedAt() {
        let session = MockDataFactory.makeTestSession(
            id: 1,
            userId: 42,
            status: "abandoned",
            startedAt: Date()
        )

        XCTAssertEqual(session.status, "abandoned")
        XCTAssertNil(session.completedAt)
    }

    // MARK: - Complex Nested Structure Tests

    func testTestSubmitResponseWithFullNestedStructure() throws {
        let json = """
        {
            "session": {
                "id": 1,
                "user_id": 42,
                "started_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T11:00:00Z",
                "status": "completed",
                "time_limit_exceeded": false
            },
            "result": {
                "id": 100,
                "test_session_id": 1,
                "user_id": 42,
                "iq_score": 120,
                "percentile_rank": 84.0,
                "total_questions": 20,
                "correct_answers": 18,
                "accuracy_percentage": 90.0,
                "completion_time_seconds": 1800,
                "completed_at": "2024-01-15T11:00:00Z",
                "response_time_flags": {
                    "total_time_seconds": 1800,
                    "mean_time_per_question": 90.0,
                    "median_time_per_question": 85.0,
                    "std_time_per_question": 15.0,
                    "anomalies": [
                        {
                            "question_id": 5,
                            "time_seconds": 300,
                            "anomaly_type": "slow",
                            "z_score": 3.5
                        }
                    ],
                    "flags": ["rushing_detected"],
                    "validity_concern": true
                },
                "domain_scores": {
                    "pattern": {
                        "correct": 3,
                        "total": 4,
                        "pct": 75.0,
                        "percentile": 80.0
                    },
                    "logic": {
                        "correct": 4,
                        "total": 4,
                        "pct": 100.0,
                        "percentile": 95.0
                    }
                },
                "strongest_domain": "logic",
                "weakest_domain": "pattern",
                "confidence_interval": {
                    "lower": 115,
                    "upper": 125,
                    "confidence_level": 0.95,
                    "standard_error": 2.5
                }
            },
            "responses_count": 20,
            "message": "Test completed successfully"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let response = try iso8601Decoder.decode(TestSubmitResponse.self, from: data)

        // Verify session
        XCTAssertEqual(response.session.id, 1)
        XCTAssertEqual(response.session.status, "completed")
        XCTAssertEqual(response.session.timeLimitExceeded, false)

        // Verify result
        XCTAssertEqual(response.result.id, 100)
        XCTAssertEqual(response.result.iqScore, 120)
        XCTAssertEqual(response.result.percentileRank, 84.0)

        // Verify response time flags (OpenAPIObjectContainer cannot be accessed with dot notation)
        XCTAssertNotNil(response.result.responseTimeFlags)

        // Verify domain scores (DomainScoresPayload uses additionalProperties dictionary)
        XCTAssertNotNil(response.result.domainScores)

        // Verify strongest/weakest domains
        XCTAssertEqual(response.result.strongestDomain, "logic")
        XCTAssertEqual(response.result.weakestDomain, "pattern")

        // Verify confidence interval (ConfidenceIntervalPayload wraps the actual schema)
        XCTAssertNotNil(response.result.confidenceInterval)
        XCTAssertEqual(response.result.confidenceInterval?.value1.lower, 115)
        XCTAssertEqual(response.result.confidenceInterval?.value1.upper, 125)

        // Verify top-level fields
        XCTAssertEqual(response.responsesCount, 20)
        XCTAssertEqual(response.message, "Test completed successfully")
    }
}
