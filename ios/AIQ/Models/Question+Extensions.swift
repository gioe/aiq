import AIQAPIClient
import Foundation

// MARK: - Question Extensions

// Extensions for the Question type (Components.Schemas.QuestionResponse)
//
// This file provides additional extensions beyond what's available in the AIQAPIClient package.
// The core UI properties (questionTypeDisplay, difficultyColor, etc.) are provided in
// QuestionResponse+UI.swift in the AIQAPIClient package.
//
// Pattern: Following TASK-368 and TASK-365, we extend generated types rather than duplicating them.

// MARK: - Protocol Conformance

extension Components.Schemas.QuestionResponse: Identifiable {
    // id property already exists on the generated type
}

extension Components.Schemas.QuestionResponse: Equatable {
    /// Equality comparison for Question
    ///
    /// - Warning: This comparison is incomplete because `answerOptions` and `explanation` are not
    ///   generated due to Swift OpenAPI Generator limitations with `anyOf: [type, null]` patterns.
    ///   Questions with different answer options may compare as equal if other fields match.
    ///   This is acceptable for preview/test purposes but should not be relied upon for
    ///   production equality checks where answer options matter.
    public static func == (lhs: Components.Schemas.QuestionResponse, rhs: Components.Schemas.QuestionResponse) -> Bool {
        lhs.id == rhs.id &&
            lhs.questionText == rhs.questionText &&
            lhs.questionType == rhs.questionType &&
            lhs.difficultyLevel == rhs.difficultyLevel
        // Note: answerOptions and explanation not compared due to generator limitation (anyOf nullable)
    }
}

// MARK: - Additional UI Helpers

extension Components.Schemas.QuestionResponse {
    /// **IMPORTANT LIMITATION:** The generated type does not include `answerOptions` or `explanation`
    /// properties due to Swift OpenAPI Generator limitations with `anyOf: [type, null]` patterns.
    ///
    /// Until the generator supports nullable properties, we cannot determine if a question has
    /// answer options. As a workaround, we assume:
    /// - Multiple choice questions must have their options rendered by the UI from another source
    /// - Or the API contract must be updated to make these fields required (with empty array/string defaults)
    ///
    /// For now, we provide conservative defaults:

    /// Indicates if this is a multiple choice question
    ///
    /// - Warning: This property always returns `false` because the generated type does not include
    ///   the `answerOptions` property due to Swift OpenAPI Generator limitations with nullable types.
    ///   **Do not rely on this property for production logic.** If multiple-choice detection is needed,
    ///   either:
    ///   1. Update the API to provide a dedicated `isMultipleChoice` field
    ///   2. Make `answerOptions` a required field (with empty array default)
    ///   3. Track usage via analytics to determine if this property is actually needed
    ///
    /// - Returns: Always `false` (conservative default)
    @available(*, deprecated, message: "Returns false due to generator limitation - see documentation")
    var isMultipleChoice: Bool {
        // Conservative default - cannot determine without answerOptions property
        // If this is needed in production, update API contract per documentation above
        false
    }

    /// Indicates if the question has answer options
    ///
    /// - Warning: This property always returns `false` because the generated type does not include
    ///   the `answerOptions` property. See `isMultipleChoice` documentation for details.
    @available(*, deprecated, message: "Returns false due to generator limitation - see documentation")
    var hasOptions: Bool {
        isMultipleChoice
    }

    /// Converts the string-based questionType to the QuestionType enum
    ///
    /// The generated type uses a String for questionType, but we want type-safe enum usage.
    var questionTypeEnum: QuestionType? {
        QuestionType(rawValue: questionType)
    }
}

// MARK: - Validation

// QuestionValidationError and QuestionResponseValidationError are defined in Question.swift
