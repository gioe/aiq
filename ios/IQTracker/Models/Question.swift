import Foundation

enum QuestionType: String, Codable, Equatable {
    case pattern
    case logic
    case spatial
    case math
    case verbal
    case memory
}

enum DifficultyLevel: String, Codable, Equatable {
    case easy
    case medium
    case hard
}

struct Question: Codable, Identifiable, Equatable {
    let id: Int
    let questionText: String
    let questionType: QuestionType
    let difficultyLevel: DifficultyLevel
    let answerOptions: [String]?
    let explanation: String?

    enum CodingKeys: String, CodingKey {
        case id
        case questionText = "question_text"
        case questionType = "question_type"
        case difficultyLevel = "difficulty_level"
        case answerOptions = "answer_options"
        case explanation
    }

    // Helper computed properties
    var isMultipleChoice: Bool {
        answerOptions != nil && !(answerOptions?.isEmpty ?? true)
    }

    var hasOptions: Bool {
        isMultipleChoice
    }
}

struct QuestionResponse: Codable, Equatable {
    let questionId: Int
    let userAnswer: String

    enum CodingKeys: String, CodingKey {
        case questionId = "question_id"
        case userAnswer = "user_answer"
    }
}
