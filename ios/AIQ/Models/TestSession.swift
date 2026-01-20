import AIQAPIClient
import Foundation

// MARK: - Test Session Type Aliases

/// Test session model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.TestSessionResponse` type.
/// UI-specific computed properties are provided via the `TestSession+Extensions.swift` file.
///
/// **Generated Properties:**
/// - id: Int
/// - userId: Int (mapped from user_id)
/// - status: String (raw string like "in_progress", "completed", "abandoned")
/// - startedAt: Date (mapped from started_at)
/// - completedAt: May have limited availability depending on OpenAPI generator version
/// - timeLimitExceeded: Bool (has default value of false)
///
/// **Note:** The generated type uses String for status instead of an enum.
/// Extensions provide a statusEnum property for type-safe status checks.
public typealias TestSession = Components.Schemas.TestSessionResponse

/// Response when starting a new test
///
/// Maps to `Components.Schemas.StartTestResponse` in the OpenAPI spec.
///
/// **Generated Properties:**
/// - session: TestSessionResponse
/// - questions: [QuestionResponse]
/// - totalQuestions: Int (mapped from total_questions)
public typealias StartTestResponse = Components.Schemas.StartTestResponse

/// Response when submitting a test
///
/// Maps to `Components.Schemas.SubmitTestResponse` in the OpenAPI spec.
///
/// **Generated Properties:**
/// - session: TestSessionResponse
/// - result: TestResultResponse
/// - responsesCount: Int (mapped from responses_count)
/// - message: String
public typealias TestSubmitResponse = Components.Schemas.SubmitTestResponse

/// Response when abandoning a test
///
/// Maps to `Components.Schemas.TestSessionAbandonResponse` in the OpenAPI spec.
///
/// **Generated Properties:**
/// - session: TestSessionResponse
/// - message: String
/// - responsesSaved: Int (mapped from responses_saved)
public typealias TestAbandonResponse = Components.Schemas.TestSessionAbandonResponse

// MARK: - Test Status Enum

/// Test status enumeration for type-safe status checks
///
/// This enum mirrors the backend's test status values and provides
/// type-safe helpers for working with the status string property.
enum TestStatus: String, Codable, Equatable {
    case inProgress = "in_progress"
    case completed
    case abandoned
}

// MARK: - Test Submission

/// Test submission request re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.ResponseSubmission` type.
/// This is a request DTO sent to the backend when submitting test answers.
///
/// **Generated Properties:**
/// - sessionId: Int (mapped from session_id)
/// - responses: [ResponseItem] - Array of user responses to questions
/// - timeLimitExceeded: Bool (mapped from time_limit_exceeded) - Whether the time limit was exceeded
///
/// **Note:** The generated type has a different initializer parameter order than the manual type.
/// The generated initializer is: `ResponseSubmission(responses:, sessionId:, timeLimitExceeded:)`
public typealias TestSubmission = Components.Schemas.ResponseSubmission

// MARK: - Response Time Analysis

/// Response time analysis flags returned from the backend
///
/// These types remain manual as they may not be fully covered by the OpenAPI spec.
struct ResponseTimeFlags: Codable, Equatable {
    let totalTimeSeconds: Int?
    let meanTimePerQuestion: Double?
    let medianTimePerQuestion: Double?
    let stdTimePerQuestion: Double?
    let anomalies: [ResponseTimeAnomaly]?
    let flags: [String]?
    let validityConcern: Bool?

    enum CodingKeys: String, CodingKey {
        case totalTimeSeconds = "total_time_seconds"
        case meanTimePerQuestion = "mean_time_per_question"
        case medianTimePerQuestion = "median_time_per_question"
        case stdTimePerQuestion = "std_time_per_question"
        case anomalies
        case flags
        case validityConcern = "validity_concern"
    }
}

/// Individual response time anomaly
struct ResponseTimeAnomaly: Codable, Equatable {
    let questionId: Int
    let timeSeconds: Int
    let anomalyType: String
    let zScore: Double?

    enum CodingKeys: String, CodingKey {
        case questionId = "question_id"
        case timeSeconds = "time_seconds"
        case anomalyType = "anomaly_type"
        case zScore = "z_score"
    }
}
