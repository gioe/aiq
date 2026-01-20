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

/// User's response to a question re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.ResponseItem` type.
/// This is a request DTO sent to the backend when submitting test answers.
///
/// **Generated Properties:**
/// - questionId: Int (mapped from question_id)
/// - userAnswer: String (mapped from user_answer)
/// - timeSpentSeconds: Int? (mapped from time_spent_seconds, optional)
///
/// **Note:** The generated type does not include validation for negative timeSpentSeconds.
/// Use the factory method `QuestionResponse.validated(...)` to create instances with validation.
public typealias QuestionResponse = Components.Schemas.ResponseItem

/// Factory extension for QuestionResponse with validation
extension Components.Schemas.ResponseItem {
    /// Creates a validated QuestionResponse
    /// - Parameters:
    ///   - questionId: The ID of the question being answered
    ///   - userAnswer: The user's answer
    ///   - timeSpentSeconds: Optional time spent on the question in seconds
    /// - Throws: `QuestionResponseValidationError.negativeTimeSpent` if timeSpentSeconds is negative
    /// - Returns: A validated ResponseItem instance
    static func validated(
        questionId: Int,
        userAnswer: String,
        timeSpentSeconds: Int? = nil
    ) throws -> Components.Schemas.ResponseItem {
        // Validate timeSpentSeconds is not negative
        if let timeSpent = timeSpentSeconds, timeSpent < 0 {
            throw QuestionResponseValidationError.negativeTimeSpent
        }

        return Components.Schemas.ResponseItem(
            questionId: questionId,
            timeSpentSeconds: timeSpentSeconds,
            userAnswer: userAnswer
        )
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
