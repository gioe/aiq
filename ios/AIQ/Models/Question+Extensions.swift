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
    public static func == (lhs: Components.Schemas.QuestionResponse, rhs: Components.Schemas.QuestionResponse) -> Bool {
        lhs.id == rhs.id &&
            lhs.questionText == rhs.questionText &&
            lhs.questionType == rhs.questionType &&
            lhs.difficultyLevel == rhs.difficultyLevel
        // Note: answerOptions and explanation are not generated due to anyOf nullable limitation
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
    /// **Note:** Returns `false` as a conservative default because the generated type does not
    /// include the `answerOptions` property. This should be updated when the generator limitation
    /// is resolved or the API provides this information differently.
    var isMultipleChoice: Bool {
        // Conservative default - cannot determine without answerOptions property
        false
    }

    /// Indicates if the question has answer options
    ///
    /// **Note:** Returns `false` as a conservative default because the generated type does not
    /// include the `answerOptions` property.
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
