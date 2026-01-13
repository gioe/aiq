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

enum QuestionValidationError: Error, LocalizedError {
    case emptyQuestionText

    var errorDescription: String? {
        switch self {
        case .emptyQuestionText:
            "Question text cannot be empty"
        }
    }
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

    /// Creates a Question with validation
    /// - Throws: `QuestionValidationError.emptyQuestionText` if questionText is empty
    init(
        id: Int,
        questionText: String,
        questionType: QuestionType,
        difficultyLevel: DifficultyLevel,
        answerOptions: [String]? = nil,
        explanation: String? = nil
    ) throws {
        guard !questionText.isEmpty else {
            throw QuestionValidationError.emptyQuestionText
        }

        self.id = id
        self.questionText = questionText
        self.questionType = questionType
        self.difficultyLevel = difficultyLevel
        self.answerOptions = answerOptions
        self.explanation = explanation
    }

    /// Custom decoder with validation
    /// - Throws: `QuestionValidationError.emptyQuestionText` if questionText is empty
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let id = try container.decode(Int.self, forKey: .id)
        let questionText = try container.decode(String.self, forKey: .questionText)
        let questionType = try container.decode(QuestionType.self, forKey: .questionType)
        let difficultyLevel = try container.decode(DifficultyLevel.self, forKey: .difficultyLevel)
        let answerOptions = try container.decodeIfPresent([String].self, forKey: .answerOptions)
        let explanation = try container.decodeIfPresent(String.self, forKey: .explanation)

        // Validate questionText is not empty
        guard !questionText.isEmpty else {
            throw QuestionValidationError.emptyQuestionText
        }

        self.id = id
        self.questionText = questionText
        self.questionType = questionType
        self.difficultyLevel = difficultyLevel
        self.answerOptions = answerOptions
        self.explanation = explanation
    }

    // Helper computed properties
    var isMultipleChoice: Bool {
        answerOptions != nil && !(answerOptions?.isEmpty ?? true)
    }

    var hasOptions: Bool {
        isMultipleChoice
    }
}

enum QuestionResponseValidationError: Error, LocalizedError {
    case negativeTimeSpent

    var errorDescription: String? {
        switch self {
        case .negativeTimeSpent:
            "Time spent cannot be negative"
        }
    }
}

struct QuestionResponse: Codable, Equatable {
    let questionId: Int
    let userAnswer: String
    let timeSpentSeconds: Int?

    enum CodingKeys: String, CodingKey {
        case questionId = "question_id"
        case userAnswer = "user_answer"
        case timeSpentSeconds = "time_spent_seconds"
    }

    /// Creates a QuestionResponse with validation
    /// - Throws: `QuestionResponseValidationError.negativeTimeSpent` if timeSpentSeconds is negative
    init(questionId: Int, userAnswer: String, timeSpentSeconds: Int? = nil) throws {
        if let timeSpent = timeSpentSeconds, timeSpent < 0 {
            throw QuestionResponseValidationError.negativeTimeSpent
        }

        self.questionId = questionId
        self.userAnswer = userAnswer
        self.timeSpentSeconds = timeSpentSeconds
    }

    /// Custom decoder with validation
    /// - Throws: `QuestionResponseValidationError.negativeTimeSpent` if timeSpentSeconds is negative
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let questionId = try container.decode(Int.self, forKey: .questionId)
        let userAnswer = try container.decode(String.self, forKey: .userAnswer)
        let timeSpentSeconds = try container.decodeIfPresent(Int.self, forKey: .timeSpentSeconds)

        // Validate timeSpentSeconds is not negative
        if let timeSpent = timeSpentSeconds, timeSpent < 0 {
            throw QuestionResponseValidationError.negativeTimeSpent
        }

        self.questionId = questionId
        self.userAnswer = userAnswer
        self.timeSpentSeconds = timeSpentSeconds
    }
}
