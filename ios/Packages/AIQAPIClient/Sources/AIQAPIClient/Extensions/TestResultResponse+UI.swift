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

// MARK: - Optional Property Extensions

public extension Components.Schemas.TestResultResponse {
    /// Formatted percentile rank string (e.g., "85th percentile")
    /// Returns nil if percentileRank is not available
    var percentileRankFormatted: String? {
        guard let rank = percentileRank else { return nil }
        let roundedRank = Int(round(rank))
        let suffix = switch roundedRank % 100 {
        case 11, 12, 13:
            "th"
        default:
            switch roundedRank % 10 {
            case 1: "st"
            case 2: "nd"
            case 3: "rd"
            default: "th"
            }
        }
        return "\(roundedRank)\(suffix) percentile"
    }

    /// Formatted completion time string (e.g., "5m 30s")
    /// Returns nil if completionTimeSeconds is not available
    var completionTimeFormatted: String? {
        guard let seconds = completionTimeSeconds else { return nil }
        let minutes = seconds / 60
        let remainingSeconds = seconds % 60
        if minutes > 0 {
            return remainingSeconds > 0 ? "\(minutes)m \(remainingSeconds)s" : "\(minutes)m"
        } else {
            return "\(remainingSeconds)s"
        }
    }

    /// Display text for the strongest cognitive domain
    /// Returns nil if strongestDomain is not available
    var strongestDomainDisplay: String? {
        strongestDomain
    }

    /// Display text for the weakest cognitive domain
    /// Returns nil if weakestDomain is not available
    var weakestDomainDisplay: String? {
        weakestDomain
    }
}
