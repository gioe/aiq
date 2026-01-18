// MARK: - TestResultResponse UI Extensions

//
// This file extends the generated TestResultResponse type with UI-specific computed properties.
// These extensions add formatting, display helpers, and accessibility descriptions that the
// generated code doesn't include.
//
// Pattern: Each extension file follows the naming convention `<TypeName>+UI.swift` and adds
// computed properties for formatting, display text, colors, and accessibility.
//
// Note: These extensions are added to the AIQAPIClient package (not the main app) because
// the generated types have `internal` access. Extensions must be in the same module.
//
// IMPORTANT: The Swift OpenAPI Generator currently does not generate optional properties
// that use the `anyOf: [type, null]` pattern in OpenAPI specs. Only required properties
// are present in the generated types. When the generator adds support for nullable types,
// additional computed properties can be added here.
//
// NOTE: Date formatting should be done in the UI layer using the main app's Date+Extensions
// which provides cached, locale-aware formatters. This package provides raw computed values.

import Foundation

// MARK: - Formatting Extensions

public extension Components.Schemas.TestResultResponse {
    /// Accuracy as a decimal value (0.0-1.0), useful for progress views and charts
    var accuracy: Double {
        accuracyPercentage / 100.0
    }

    /// Formatted accuracy percentage string (e.g., "75%")
    var accuracyFormatted: String {
        "\(Int(round(accuracyPercentage)))%"
    }

    /// IQ score formatted as a string
    var iqScoreFormatted: String {
        "\(iqScore)"
    }

    /// Score ratio formatted as "X/Y" (e.g., "18/20")
    var scoreRatio: String {
        "\(correctAnswers)/\(totalQuestions)"
    }

    /// Accessibility description for the test result
    var accessibilityDescription: String {
        let answeredText = "You answered \(correctAnswers) of \(totalQuestions) correctly"
        return "IQ score \(iqScore). \(answeredText), with \(accuracyFormatted) accuracy."
    }
}
