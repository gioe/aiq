import AIQAPIClientCore
import Foundation

// MARK: - Question Extensions

// Extensions for the Question type (Components.Schemas.QuestionResponse)
//
// This file provides UI-specific computed properties for QuestionResponse.
// Core UI properties were migrated from the APIClient package to the app target (TASK-711)
// following the 'bring your own extensions' pattern.
//
// Pattern: Following TASK-368 and TASK-365, we extend generated types rather than duplicating them.

// MARK: - Core UI Properties (migrated from APIClient package, TASK-711)

extension Components.Schemas.QuestionResponse {
    /// Question type with proper capitalization (e.g., "Pattern", "Logic")
    var questionTypeDisplay: String {
        questionType.capitalized
    }

    /// Full question type description (e.g., "Pattern Recognition", "Logical Reasoning")
    var questionTypeFullName: String {
        switch questionType.lowercased() {
        case "pattern":
            "Pattern Recognition"
        case "logic":
            "Logical Reasoning"
        case "spatial":
            "Spatial Reasoning"
        case "math":
            "Mathematical"
        case "verbal":
            "Verbal Reasoning"
        case "memory":
            "Memory"
        default:
            questionType.capitalized
        }
    }

    /// Difficulty level with proper capitalization (e.g., "Easy", "Medium", "Hard")
    var difficultyDisplay: String {
        difficultyLevel.capitalized
    }

    /// Difficulty badge color name for UI display
    /// Returns a string name that can be mapped to SwiftUI Color in the main app
    var difficultyColorName: String {
        switch difficultyLevel.lowercased() {
        case "easy": "green"
        case "medium": "orange"
        case "hard": "red"
        default: "gray"
        }
    }

    /// Accessibility description for the question
    var accessibilityDescription: String {
        "Question \(id): \(questionTypeFullName), \(difficultyDisplay) difficulty"
    }

    /// Accessibility hint for the question
    var accessibilityHint: String {
        "This is a \(difficultyDisplay) \(questionTypeDisplay) question"
    }
}

// MARK: - Protocol Conformance

extension Components.Schemas.QuestionResponse: @retroactive Identifiable {
    // id property already exists on the generated type
}

// MARK: - Optional Property Extensions

extension Components.Schemas.QuestionResponse {
    /// Returns nil — answerOptions is no longer included in the API response schema.
    var answerOptions: [String]? {
        nil
    }

    /// Returns nil — stimulus is no longer included in the API response schema.
    var stimulus: String? {
        nil
    }

    /// Returns nil — explanation is no longer included in the API response schema.
    var explanation: String? {
        nil
    }
}

// MARK: - Additional UI Helpers

extension Components.Schemas.QuestionResponse {
    /// Indicates if this is a multiple choice question.
    /// Returns false — answerOptions is no longer included in the API response schema.
    var isMultipleChoice: Bool {
        guard let options = answerOptions else { return false }
        return options.count >= 2
    }

    /// Indicates if the question has answer options.
    /// Returns false — answerOptions is no longer included in the API response schema.
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

    /// Indicates if this is a memory question with a stimulus to memorize.
    /// Returns false — stimulus is no longer included in the API response schema.
    var isMemoryQuestion: Bool {
        questionTypeEnum == .memory && stimulus != nil && !(stimulus?.isEmpty ?? true)
    }
}

// MARK: - Validation

// QuestionValidationError and QuestionResponseValidationError are defined in Question.swift
