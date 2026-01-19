import AIQAPIClient
import Foundation

// MARK: - Question Type Alias

/// Question model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.QuestionResponse` type.
/// UI-specific computed properties are provided via the `Question+Extensions.swift` file.
///
/// **Generated Properties:**
/// - id: Int
/// - questionText: String (mapped from question_text)
/// - questionType: String (raw string like "pattern", "logic")
/// - difficultyLevel: String (raw string like "easy", "medium", "hard")
/// - answerOptions: May have limited availability depending on OpenAPI generator version
/// - explanation: May have limited availability depending on OpenAPI generator version
///
/// **Note:** The generated type uses String for questionType and difficultyLevel instead of enums.
/// Extensions handle string comparisons for these properties.
public typealias Question = Components.Schemas.QuestionResponse

// MARK: - Question Type Enum

/// Cognitive domain types for questions
///
/// This enum provides type-safe values for question types. The backend returns
/// these as strings in the `questionType` property.
enum QuestionType: String, Codable, Equatable {
    case pattern
    case logic
    case spatial
    case math
    case verbal
    case memory
}

// MARK: - Difficulty Level Enum

/// Difficulty levels for questions
///
/// This enum provides type-safe values for difficulty levels. The backend returns
/// these as strings in the `difficultyLevel` property.
enum DifficultyLevel: String, Codable, Equatable {
    case easy
    case medium
    case hard
}

// MARK: - Question Response

/// User's response to a question
///
/// This is a request DTO sent to the backend when submitting test answers.
/// It remains a manual model as it's not part of the OpenAPI response types.
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

// MARK: - Validation Errors

enum QuestionValidationError: Error, LocalizedError {
    case emptyQuestionText

    var errorDescription: String? {
        switch self {
        case .emptyQuestionText:
            "Question text cannot be empty"
        }
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
