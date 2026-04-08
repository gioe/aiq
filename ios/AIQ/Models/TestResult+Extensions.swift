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
// **Important Notes:**
// - The generated type does not include optional properties like `percentileRank`,
//   `completionTimeSeconds`, `domainScores`, `confidenceInterval` due to OpenAPI generator limitations.
// - Until the generator is updated, these properties cannot be accessed.
// - This is a known limitation tracked in the OpenAPI migration documentation.

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
    /// an `additionalProperties: [String: OpenAPIObjectContainer]` dictionary. Each container
    /// is round-tripped through JSON to produce a typed `DomainScore` value.
    var domainScoresConverted: [String: DomainScore]? {
        guard let payload = domainScores else { return nil }
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()
        var result: [String: DomainScore] = [:]
        for (key, value) in payload.additionalProperties {
            guard let data = try? encoder.encode(value),
                  let score = try? decoder.decode(DomainScore.self, from: data)
            else { continue }
            result[key] = score
        }
        return result.isEmpty ? nil : result
    }

    /// Returns domain scores sorted by `CognitiveDomain.allCases` order with full metadata.
    ///
    /// Only domains present in `domainScoresConverted` are included, so the count may be
    /// less than six when the backend omits certain domains.
    var sortedDomainScoresWithMetadata: [(domain: CognitiveDomain, score: DomainScore)]? {
        guard let scores = domainScoresConverted, !scores.isEmpty else { return nil }
        let sorted = CognitiveDomain.allCases.compactMap { domain -> (domain: CognitiveDomain, score: DomainScore)? in
            guard let score = scores[domain.rawValue] else { return nil }
            return (domain: domain, score: score)
        }
        return sorted.isEmpty ? nil : sorted
    }

    /// Domain scores sorted by `CognitiveDomain.allCases` order.
    ///
    /// Convenience alias for `sortedDomainScoresWithMetadata`.
    var sortedDomainScores: [(domain: CognitiveDomain, score: DomainScore)]? {
        sortedDomainScoresWithMetadata
    }

    /// The domain with the highest accuracy score, excluding domains with zero questions.
    var strongestCognitiveDomain: (domain: CognitiveDomain, score: DomainScore)? {
        sortedDomainScoresWithMetadata?
            .filter { $0.score.total > 0 }
            .max { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }
    }

    /// The domain with the lowest accuracy score, excluding domains with zero questions.
    var weakestCognitiveDomain: (domain: CognitiveDomain, score: DomainScore)? {
        sortedDomainScoresWithMetadata?
            .filter { $0.score.total > 0 }
            .min { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }
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

    /// Converts the OpenAPI model scores payload to a typed dictionary.
    ///
    /// Same pattern as `domainScoresConverted` — round-trips each `OpenAPIObjectContainer`
    /// through JSON to produce a typed `ModelScore`.
    var modelScoresConverted: [String: ModelScore]? {
        guard let payload = modelScores else { return nil }
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()
        var result: [String: ModelScore] = [:]
        for (key, value) in payload.additionalProperties {
            guard let data = try? encoder.encode(value),
                  let score = try? decoder.decode(ModelScore.self, from: data)
            else { continue }
            result[key] = score
        }
        return result.isEmpty ? nil : result
    }

    /// Model scores sorted alphabetically by model name.
    var sortedModelScores: [(model: String, score: ModelScore)]? {
        guard let scores = modelScoresConverted, !scores.isEmpty else { return nil }
        return scores.sorted { $0.key < $1.key }.map { (model: $0.key, score: $0.value) }
    }

    /// Model scores grouped by vendor with aggregate stats per vendor.
    var vendorGroupedScores: [(
        vendor: ModelVendor,
        models: [(model: String, score: ModelScore)],
        aggregate: ModelScore
    )]? {
        guard let scores = modelScoresConverted, !scores.isEmpty else { return nil }

        var groups: [ModelVendor: [(model: String, score: ModelScore)]] = [:]
        for (model, score) in scores {
            let vendor = ModelVendor.from(modelName: model)
            groups[vendor, default: []].append((model: model, score: score))
        }

        return groups.map { vendor, models in
            let sortedModels = models.sorted { $0.model < $1.model }
            let totalCorrect = models.reduce(0) { $0 + $1.score.correct }
            let totalQuestions = models.reduce(0) { $0 + $1.score.total }
            let pct = totalQuestions > 0 ? (Double(totalCorrect) / Double(totalQuestions)) * 100.0 : nil
            let aggregate = ModelScore(correct: totalCorrect, total: totalQuestions, pct: pct)
            return (vendor: vendor, models: sortedModels, aggregate: aggregate)
        }
        .sorted { ($0.aggregate.pct ?? 0) > ($1.aggregate.pct ?? 0) }
    }
}
