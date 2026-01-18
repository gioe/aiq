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

import Foundation
import SwiftUI

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

    /// Formatted date string for completedAt (e.g., "Jan 15, 2024")
    var completedAtFormatted: String {
        completedAt.toShortString()
    }

    /// Relative date string for completedAt (e.g., "2 days ago")
    var completedAtRelative: String {
        completedAt.toRelativeString()
    }

    /// Score ratio formatted as "X/Y" (e.g., "18/20")
    var scoreRatio: String {
        "\(correctAnswers)/\(totalQuestions)"
    }

    /// Accessibility description for the test result
    var accessibilityDescription: String {
        let answeredText = "You answered \(correctAnswers) out of \(totalQuestions) questions correctly"
        return "IQ score \(iqScore). \(answeredText), achieving \(accuracyFormatted) accuracy."
    }
}

// MARK: - Int Ordinal Extension

extension Int {
    /// Returns the ordinal suffix for a number (e.g., "st", "nd", "rd", "th")
    private var ordinalSuffix: String {
        let ones = self % 10
        let tens = (self / 10) % 10

        if tens == 1 {
            return "th"
        }

        switch ones {
        case 1: return "st"
        case 2: return "nd"
        case 3: return "rd"
        default: return "th"
        }
    }

    /// Returns the number with its ordinal suffix (e.g., "1st", "2nd", "23rd")
    var ordinalString: String {
        "\(self)\(ordinalSuffix)"
    }
}

// MARK: - Date Formatting Extension

extension Date {
    /// Format: "Jan 15, 2024"
    func toShortString() -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: self)
    }

    /// Format: "2 days ago", "Just now", etc.
    func toRelativeString() -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full
        return formatter.localizedString(for: self, relativeTo: Date())
    }
}
