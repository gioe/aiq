import AIQAPIClientCore
import Foundation
import SwiftUI

// MARK: - TestResult Extensions

// Extensions for the TestResult type (Components.Schemas.TestResultResponse)
//
// This file provides UI-specific computed properties for TestResultResponse.
// All formatting properties live here following the bring-your-own-extensions pattern (TASK-113).
//
// Pattern: Following TASK-368 and TASK-365, we extend generated types rather than duplicating them.
//
// **Note:** The regenerated TestResultResponse (as of the is_admin spec update) only includes
// required fields: id, testSessionId, userId, iqScore, totalQuestions, correctAnswers,
// accuracyPercentage, completedAt. Optional fields (percentileRank, completionTimeSeconds,
// domainScores, confidenceInterval, strongestDomain, weakestDomain, modelScores) have been
// removed from the OpenAPI spec's required fields and are no longer generated.

// MARK: - Protocol Conformance

extension Components.Schemas.TestResultResponse: @retroactive Identifiable {
    // id property already exists on the generated type
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
    /// Returns nil — percentileRank is no longer included in the API response schema.
    var percentileRank: Double? {
        nil
    }

    /// Returns nil — completionTimeSeconds is no longer included in the API response schema.
    var completionTimeSeconds: Int? {
        nil
    }

    /// Returns nil — strongestDomain is no longer included in the API response schema.
    var strongestDomain: String? {
        nil
    }

    /// Returns nil — weakestDomain is no longer included in the API response schema.
    var weakestDomain: String? {
        nil
    }

    /// Formatted percentile rank string (e.g., "85th percentile")
    /// Returns nil — percentileRank is no longer included in the API response schema.
    var percentileRankFormatted: String? {
        nil
    }

    /// Formatted completion time in M:SS format (e.g., "5:30")
    /// Returns nil — completionTimeSeconds is no longer included in the API response schema.
    var completionTimeFormatted: String? {
        nil
    }

    /// Display text for the strongest cognitive domain
    /// Returns nil — strongestDomain is no longer included in the API response schema.
    var strongestDomainDisplay: String? {
        nil
    }

    /// Display text for the weakest cognitive domain
    /// Returns nil — weakestDomain is no longer included in the API response schema.
    var weakestDomainDisplay: String? {
        nil
    }
}

// MARK: - Additional UI Helpers

extension Components.Schemas.TestResultResponse {
    /// Converts the OpenAPI-generated confidence interval to the local ConfidenceInterval type.
    /// Returns nil — confidenceInterval is no longer included in the API response schema.
    var confidenceIntervalConverted: ConfidenceInterval? {
        nil
    }

    /// Formatted percentile string (e.g., "Top 16%")
    /// Returns nil — percentileRank is no longer included in the API response schema.
    var percentileFormatted: String? {
        nil
    }

    /// Detailed percentile description (e.g., "84th percentile")
    /// Returns nil — percentileRank is no longer included in the API response schema.
    var percentileDescription: String? {
        nil
    }

    /// Score displayed with confidence interval range when available (e.g., "108 (101-115)")
    var scoreWithConfidenceInterval: String {
        "\(iqScore)"
    }

    /// Accessibility description for the score with confidence interval
    var scoreAccessibilityDescription: String {
        "AIQ score \(iqScore)"
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

    /// Returns nil — domainScores is no longer included in the API response schema.
    var domainScoresConverted: [String: DomainScore]? {
        nil
    }

    /// Returns nil — domainScores is no longer included in the API response schema.
    var sortedDomainScoresWithMetadata: [(domain: CognitiveDomain, score: DomainScore)]? {
        nil
    }

    /// Returns nil — domainScores is no longer included in the API response schema.
    var sortedDomainScores: [(domain: CognitiveDomain, score: DomainScore)]? {
        nil
    }

    /// Returns nil — domainScores is no longer included in the API response schema.
    var strongestCognitiveDomain: (domain: CognitiveDomain, score: DomainScore)? {
        nil
    }

    /// Returns nil — domainScores is no longer included in the API response schema.
    var weakestCognitiveDomain: (domain: CognitiveDomain, score: DomainScore)? {
        nil
    }
}

// MARK: - Model Score Helpers

extension Components.Schemas.TestResultResponse {
    /// Known LLM vendor prefixes for grouping models by provider
    enum ModelVendor: String, CaseIterable {
        case openai
        case anthropic
        case google
        case meta
        case unknown

        var displayName: String {
            switch self {
            case .openai: "OpenAI"
            case .anthropic: "Anthropic"
            case .google: "Google"
            case .meta: "Meta"
            case .unknown: "Unknown"
            }
        }

        /// Determine vendor from a model name string
        static func from(modelName: String) -> ModelVendor {
            let lowered = modelName.lowercased()
            if lowered.contains("gpt") || lowered.contains("o1") || lowered.contains("o3") || lowered.contains("o4") {
                return .openai
            } else if lowered.contains("claude") {
                return .anthropic
            } else if lowered.contains("gemini") || lowered.contains("gemma") {
                return .google
            } else if lowered.contains("llama") {
                return .meta
            }
            return .unknown
        }
    }

    /// Returns nil — modelScores is no longer included in the API response schema.
    var modelScoresConverted: [String: ModelScore]? {
        nil
    }

    /// Returns nil — modelScores is no longer included in the API response schema.
    var vendorGroupedScores: [(
        vendor: ModelVendor,
        models: [(model: String, score: ModelScore)],
        aggregate: ModelScore
    )]? {
        nil
    }
}
