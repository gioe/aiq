import APIClient
import Foundation
import SwiftUI

// MARK: - TestResult Extensions

// Extensions for the TestResult type (Components.Schemas.TestResultResponse)
//
// This file provides UI-specific computed properties beyond what's available in the
// APIClient package. The core formatting properties (accuracy, accuracyFormatted,
// scoreRatio, accessibilityDescription) are in TestResultResponse+UI.swift in the package.
//
// Pattern: Following TASK-368 and TASK-365, we extend generated types rather than duplicating them.
//
// **Important Notes:**
// - The generated type does not include optional properties like `percentileRank`,
//   `completionTimeSeconds`, `domainScores`, `confidenceInterval` due to OpenAPI generator limitations.
// - Until the generator is updated, these properties cannot be accessed.
// - This is a known limitation tracked in the OpenAPI migration documentation.

// MARK: - Protocol Conformance

extension Components.Schemas.TestResultResponse: Identifiable {
    // id property already exists on the generated type
}

extension Components.Schemas.TestResultResponse: Equatable {
    // swiftlint:disable:next line_length
    public static func == (lhs: Components.Schemas.TestResultResponse, rhs: Components.Schemas.TestResultResponse) -> Bool {
        lhs.id == rhs.id &&
            lhs.testSessionId == rhs.testSessionId &&
            lhs.userId == rhs.userId &&
            lhs.iqScore == rhs.iqScore &&
            lhs.totalQuestions == rhs.totalQuestions &&
            lhs.correctAnswers == rhs.correctAnswers &&
            lhs.accuracyPercentage == rhs.accuracyPercentage &&
            lhs.completedAt == rhs.completedAt
        // Note: Optional properties not included due to generator limitations
    }
}

// MARK: - Formatting Properties (migrated from APIClient package, TASK-711)

extension Components.Schemas.TestResultResponse {
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
        return "AIQ score \(iqScore). \(answeredText), with \(accuracyFormatted) accuracy."
    }
}

// MARK: - Optional Property Extensions (migrated from APIClient package, TASK-711)

extension Components.Schemas.TestResultResponse {
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

    /// Formatted completion time in M:SS format (e.g., "5:30")
    /// Returns nil if completionTimeSeconds is not available
    var completionTimeFormatted: String? {
        guard let seconds = completionTimeSeconds else { return nil }
        let minutes = seconds / 60
        let remainingSeconds = seconds % 60
        return String(format: "%d:%02d", minutes, remainingSeconds)
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

// MARK: - Additional UI Helpers

extension Components.Schemas.TestResultResponse {
    /// Converts the OpenAPI-generated confidence interval to the local ConfidenceInterval type.
    ///
    /// The generated type wraps optional types in a `Payload` struct with a `value1` property
    /// due to how the OpenAPI generator handles `anyOf: [type, null]`.
    var confidenceIntervalConverted: ConfidenceInterval? {
        guard let payload = confidenceInterval?.value1 else { return nil }
        return ConfidenceInterval(
            confidenceLevel: payload.confidenceLevel,
            lower: payload.lower,
            standardError: payload.standardError,
            upper: payload.upper
        )
    }

    /// Formatted percentile string (e.g., "Top 16%")
    var percentileFormatted: String? {
        guard let rankValue = percentileRank else { return nil }
        let percentile = Int(round(rankValue))

        if percentile >= 98 {
            return "Top 2%"
        } else if percentile >= 95 {
            return "Top 5%"
        } else if percentile >= 90 {
            return "Top 10%"
        } else if percentile >= 75 {
            return "Top 25%"
        } else if percentile >= 50 {
            return "Top 50%"
        } else {
            return "Lower 50%"
        }
    }

    /// Detailed percentile description (e.g., "84th percentile")
    var percentileDescription: String? {
        guard let rankValue = percentileRank else { return nil }
        let percentile = Int(round(rankValue))
        return "\(percentile.ordinalString) percentile"
    }

    /// Score displayed with confidence interval range when available (e.g., "108 (101-115)")
    var scoreWithConfidenceInterval: String {
        if let ci = confidenceIntervalConverted {
            return "\(iqScore) (\(ci.rangeFormatted))"
        }
        return "\(iqScore)"
    }

    /// Accessibility description for the score with confidence interval
    var scoreAccessibilityDescription: String {
        if let ci = confidenceIntervalConverted {
            return "AIQ score \(iqScore), range \(ci.lower) to \(ci.upper)"
        }
        return "AIQ score \(iqScore)"
    }
}

// MARK: - Domain Score Helpers

extension Components.Schemas.TestResultResponse {
    /// Cognitive domain types
    ///
    /// This enum is maintained here for UI purposes and matches the question types
    /// used throughout the app.
    enum CognitiveDomain: String, CaseIterable {
        case pattern
        case logic
        case spatial
        case math
        case verbal
        case memory

        var displayName: String {
            switch self {
            case .pattern: "Pattern Recognition"
            case .logic: "Logical Reasoning"
            case .spatial: "Spatial Reasoning"
            case .math: "Mathematical"
            case .verbal: "Verbal Reasoning"
            case .memory: "Memory"
            }
        }
    }

    /// Converts the OpenAPI domain scores payload to a dictionary for UI usage.
    ///
    /// The generated `domainScores` property is of type `DomainScoresPayload?` which wraps
    /// an `additionalProperties` dictionary. This computed property converts it to the
    /// `[String: DomainScore]` format expected by UI components.
    ///
    /// **Note:** Returns nil because `domainScores.additionalProperties` contains raw JSON
    /// that requires more sophisticated decoding. For now, UI should handle nil gracefully.
    var domainScoresConverted: [String: DomainScore]? {
        nil
    }

    /// Returns domain scores sorted by domain order with full metadata.
    ///
    /// **Note:** Returns nil because domain score conversion is not yet implemented.
    var sortedDomainScoresWithMetadata: [(domain: CognitiveDomain, score: DomainScore)]? {
        nil
    }
}
