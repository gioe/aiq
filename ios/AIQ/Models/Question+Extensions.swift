import AIQAPIClient
import Foundation

// MARK: - Question Extensions

// Extensions for the Question type (Components.Schemas.QuestionResponse)
//
// This file provides additional extensions beyond what's available in the AIQAPIClient package.
// The core UI properties (questionTypeDisplay, difficultyColorName, etc.) are provided in
// QuestionResponse+UI.swift in the AIQAPIClient package.
//
// Pattern: Following TASK-368 and TASK-365, we extend generated types rather than duplicating them.

// MARK: - Protocol Conformance

extension Components.Schemas.QuestionResponse: Identifiable {
    // id property already exists on the generated type
}

extension Components.Schemas.QuestionResponse: Equatable {
    /// Equality comparison for Question
    public static func == (lhs: Components.Schemas.QuestionResponse, rhs: Components.Schemas.QuestionResponse) -> Bool {
        lhs.id == rhs.id &&
            lhs.questionText == rhs.questionText &&
            lhs.questionType == rhs.questionType &&
            lhs.difficultyLevel == rhs.difficultyLevel &&
            lhs.answerOptions == rhs.answerOptions &&
            lhs.explanation == rhs.explanation &&
            lhs.stimulus == rhs.stimulus
    }
}

// MARK: - Additional UI Helpers

extension Components.Schemas.QuestionResponse {
    /// Indicates if this is a multiple choice question
    ///
    /// A question is considered multiple choice if it has answer options available.
    /// - Returns: `true` if the question has at least 2 answer options, `false` otherwise
    var isMultipleChoice: Bool {
        guard let options = answerOptions else { return false }
        return options.count >= 2
    }

    /// Indicates if the question has answer options
    ///
    /// - Returns: `true` if answerOptions is non-nil and non-empty
    var hasOptions: Bool {
        guard let options = answerOptions else { return false }
        return !options.isEmpty
    }

    /// Converts the string-based questionType to the QuestionType enum
    ///
    /// The generated type uses a String for questionType, but we want type-safe enum usage.
    var questionTypeEnum: QuestionType? {
        QuestionType(rawValue: questionType)
    }

    /// Indicates if this is a memory question with a stimulus to memorize
    ///
    /// Memory questions have a two-phase flow:
    /// 1. Show stimulus content for memorization
    /// 2. Hide stimulus and show the question
    ///
    /// - Returns: `true` if this is a memory question with non-empty stimulus content
    var isMemoryQuestion: Bool {
        questionTypeEnum == .memory && stimulus != nil && !(stimulus?.isEmpty ?? true)
    }
}

// MARK: - Validation

// QuestionValidationError and QuestionResponseValidationError are defined in Question.swift
