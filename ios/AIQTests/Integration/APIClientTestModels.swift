import Foundation

// MARK: - Test Data Structures for API Integration Tests

// Note: Models that match app models (TestSession, Question, TestResult, etc.)
// have been removed to avoid conflicts. Use @testable import AIQ to access real models.

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

// Note: Use AIQ.TestSession, AIQ.Question, AIQ.TestResult, etc. from the main app
// instead of defining duplicate test models here

struct TestStartResponse: Codable {
    let session: SessionInfo
    let questions: [QuestionInfo]
    let totalQuestions: Int

    struct SessionInfo: Codable {
        let id: String
        let status: String
        let startedAt: String

        enum CodingKeys: String, CodingKey {
            case id
            case status
            case startedAt = "started_at"
        }
    }

    struct QuestionInfo: Codable {
        let id: String
        let questionText: String
        let questionType: String
        let answerOptions: [String]

        enum CodingKeys: String, CodingKey {
            case id
            case questionText = "question_text"
            case questionType = "question_type"
            case answerOptions = "answer_options"
        }
    }

    enum CodingKeys: String, CodingKey {
        case session
        case questions
        case totalQuestions = "total_questions"
    }
}

struct TestSubmitResponse: Codable {
    let result: ResultInfo

    struct ResultInfo: Codable {
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
}

struct TestHistoryResponse: Codable {
    let results: [HistoryResult]
    let totalTests: Int

    struct HistoryResult: Codable {
        let id: String
        let iqScore: Int
        let totalQuestions: Int
        let correctAnswers: Int
        let completedAt: String

        enum CodingKeys: String, CodingKey {
            case id
            case iqScore = "iq_score"
            case totalQuestions = "total_questions"
            case correctAnswers = "correct_answers"
            case completedAt = "completed_at"
        }
    }

    enum CodingKeys: String, CodingKey {
        case results
        case totalTests = "total_tests"
    }
}

struct QuestionResponse: Codable {
    let questionId: Int
    let userAnswer: String

    enum CodingKeys: String, CodingKey {
        case questionId = "question_id"
        case userAnswer = "user_answer"
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
