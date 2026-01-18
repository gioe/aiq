// MARK: - QuestionResponse UI Extensions

//
// Extends the generated QuestionResponse type with UI-specific computed properties.
// These extensions add display helpers and formatting for questions.
//
// Pattern: Each extension file follows the naming convention `<TypeName>+UI.swift`.
//
// NOTE: Optional properties like `answerOptions` and `explanation` are not generated
// by the Swift OpenAPI Generator due to limitations with `anyOf: [type, null]` patterns.
// When this limitation is resolved, additional helpers can be added here.

import Foundation
import SwiftUI

public extension Components.Schemas.QuestionResponse {
    // MARK: - Question Type Display

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

    // MARK: - Difficulty Display

    /// Difficulty level with proper capitalization (e.g., "Easy", "Medium", "Hard")
    var difficultyDisplay: String {
        difficultyLevel.capitalized
    }

    /// Difficulty badge color for UI display
    var difficultyColor: Color {
        switch difficultyLevel.lowercased() {
        case "easy":
            .green
        case "medium":
            .orange
        case "hard":
            .red
        default:
            .gray
        }
    }

    // MARK: - Accessibility

    /// Accessibility description for the question
    var accessibilityDescription: String {
        "Question \(id): \(questionTypeFullName), \(difficultyDisplay) difficulty"
    }

    /// Accessibility hint for the question
    var accessibilityHint: String {
        "This is a \(difficultyLevel) \(questionType) question"
    }
}
