import Foundation

enum TestStatus: String, Codable, Equatable {
    case inProgress = "in_progress"
    case completed
    case abandoned
}

struct TestSession: Codable, Identifiable, Equatable {
    let id: Int
    let userId: Int
    let startedAt: Date
    let completedAt: Date?
    let status: TestStatus
    let questions: [Question]?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case status
        case questions
    }
}

struct StartTestResponse: Codable, Equatable {
    let session: TestSession
    let questions: [Question]
    let totalQuestions: Int

    enum CodingKeys: String, CodingKey {
        case session
        case questions
        case totalQuestions = "total_questions"
    }
}

struct TestSubmission: Codable, Equatable {
    let sessionId: Int
    let responses: [QuestionResponse]

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case responses
    }
}

struct TestSubmitResponse: Codable, Equatable {
    let session: TestSession
    let result: SubmittedTestResult
    let responsesCount: Int
    let message: String

    enum CodingKeys: String, CodingKey {
        case session
        case result
        case responsesCount = "responses_count"
        case message
    }
}

struct TestAbandonResponse: Codable, Equatable {
    let session: TestSession
    let message: String
    let responsesSaved: Int

    enum CodingKeys: String, CodingKey {
        case session
        case message
        case responsesSaved = "responses_saved"
    }
}

struct SubmittedTestResult: Codable, Equatable {
    let id: Int
    let testSessionId: Int
    let userId: Int
    let iqScore: Int
    let totalQuestions: Int
    let correctAnswers: Int
    let accuracyPercentage: Double
    let completionTimeSeconds: Int?
    let completedAt: Date

    var accuracy: Double {
        accuracyPercentage / 100.0
    }

    var completionTimeFormatted: String {
        guard let seconds = completionTimeSeconds else { return "N/A" }
        let minutes = seconds / 60
        let secs = seconds % 60
        return String(format: "%d:%02d", minutes, secs)
    }

    enum CodingKeys: String, CodingKey {
        case id
        case testSessionId = "test_session_id"
        case userId = "user_id"
        case iqScore = "iq_score"
        case totalQuestions = "total_questions"
        case correctAnswers = "correct_answers"
        case accuracyPercentage = "accuracy_percentage"
        case completionTimeSeconds = "completion_time_seconds"
        case completedAt = "completed_at"
    }
}
