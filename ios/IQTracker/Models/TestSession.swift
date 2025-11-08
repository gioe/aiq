import Foundation

enum TestStatus: String, Codable {
    case inProgress = "in_progress"
    case completed
    case abandoned
}

struct TestSession: Codable, Identifiable {
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

struct StartTestResponse: Codable {
    let session: TestSession
    let questions: [Question]
    let totalQuestions: Int

    enum CodingKeys: String, CodingKey {
        case session
        case questions
        case totalQuestions = "total_questions"
    }
}

struct TestSubmission: Codable {
    let sessionId: Int
    let responses: [QuestionResponse]

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case responses
    }
}
