import Foundation
import SwiftUI

// MARK: - Paginated Test History Response (BCQ-004)

/// Response wrapper for paginated test history endpoint.
/// The backend now returns paginated results with metadata for pagination UI.
struct PaginatedTestHistoryResponse: Codable {
    /// List of test results for the current page
    let results: [TestResult]

    /// Total number of test results available for this user
    let totalCount: Int

    /// Number of results per page (max 100)
    let limit: Int

    /// Offset from the start of the results
    let offset: Int

    /// Whether there are more results beyond this page
    let hasMore: Bool

    enum CodingKeys: String, CodingKey {
        case results
        case totalCount = "total_count"
        case limit
        case offset
        case hasMore = "has_more"
    }
}

// MARK: - Confidence Interval

/// Represents a confidence interval for an IQ score.
///
/// Confidence intervals quantify the uncertainty in score measurement,
/// providing a range within which the true score is likely to fall.
/// This is calculated using the Standard Error of Measurement (SEM)
/// derived from the test's reliability coefficient.
///
/// Example: A score of 108 with CI [101, 115] at 95% confidence means
/// there is a 95% probability the true score falls between 101 and 115.
struct ConfidenceInterval: Codable, Equatable {
    /// Lower bound of the confidence interval (clamped to valid IQ range 40-160)
    let lower: Int

    /// Upper bound of the confidence interval (clamped to valid IQ range 40-160)
    let upper: Int

    /// Confidence level as a decimal (e.g., 0.95 for 95% CI)
    let confidenceLevel: Double

    /// Standard Error of Measurement (SEM) used to calculate the interval
    let standardError: Double

    enum CodingKeys: String, CodingKey {
        case lower
        case upper
        case confidenceLevel = "confidence_level"
        case standardError = "standard_error"
    }

    /// Formatted range string (e.g., "101-115")
    var rangeFormatted: String {
        "\(lower)-\(upper)"
    }

    /// Confidence level as a percentage (e.g., 95 for 0.95)
    var confidencePercentage: Int {
        Int(round(confidenceLevel * 100))
    }

    /// Full description (e.g., "95% confidence interval: 101-115")
    var fullDescription: String {
        "\(confidencePercentage)% confidence interval: \(rangeFormatted)"
    }

    /// Accessibility description for VoiceOver
    var accessibilityDescription: String {
        "Score range from \(lower) to \(upper) with \(confidencePercentage) percent confidence"
    }
}

// MARK: - Domain Score

/// Represents performance breakdown for a single cognitive domain.
struct DomainScore: Codable, Equatable {
    let correct: Int
    let total: Int
    let pct: Double?
    /// Percentile rank (0-100) compared to population, available when population stats are configured
    let percentile: Double?

    /// Formatted percentage string (e.g., "75%")
    var percentageFormatted: String {
        guard let percentage = pct else { return "N/A" }
        return "\(Int(round(percentage)))%"
    }

    /// Accuracy as a decimal (0.0-1.0)
    var accuracy: Double? {
        guard let percentage = pct else { return nil }
        return percentage / 100.0
    }

    /// Formatted percentile string (e.g., "71st")
    var percentileFormatted: String? {
        guard let percentile else { return nil }
        return Int(round(percentile)).ordinalString
    }

    /// Description for accessibility (e.g., "71st percentile")
    var percentileDescription: String? {
        guard let formatted = percentileFormatted else { return nil }
        return "\(formatted) percentile"
    }

    /// Performance level based on percentile
    var performanceLevel: PerformanceLevel? {
        guard let percentile else { return nil }
        switch percentile {
        case 0 ..< 25:
            return .needsWork
        case 25 ..< 50:
            return .belowAverage
        case 50 ..< 75:
            return .average
        case 75 ..< 90:
            return .good
        case 90...:
            return .excellent
        default:
            return nil
        }
    }
}

/// Performance level categories for domain scores
enum PerformanceLevel {
    case needsWork // < 25th percentile
    case belowAverage // 25-50th percentile
    case average // 50-75th percentile
    case good // 75-90th percentile
    case excellent // >= 90th percentile

    var displayName: String {
        switch self {
        case .needsWork: "Needs Work"
        case .belowAverage: "Below Average"
        case .average: "Average"
        case .good: "Good"
        case .excellent: "Excellent"
        }
    }

    var color: Color {
        switch self {
        case .needsWork: ColorPalette.performanceNeedsWork
        case .belowAverage: ColorPalette.performanceBelowAverage
        case .average: ColorPalette.performanceAverage
        case .good: ColorPalette.performanceGood
        case .excellent: ColorPalette.performanceExcellent
        }
    }
}

struct TestResult: Codable, Identifiable, Equatable {
    let id: Int
    let testSessionId: Int
    let userId: Int
    let iqScore: Int
    let percentileRank: Double?
    let totalQuestions: Int
    let correctAnswers: Int
    let accuracyPercentage: Double
    let completionTimeSeconds: Int?
    let completedAt: Date
    let domainScores: [String: DomainScore]?
    /// Confidence interval for the IQ score. Nil when reliability data is insufficient.
    let confidenceInterval: ConfidenceInterval?

    init(
        id: Int,
        testSessionId: Int,
        userId: Int,
        iqScore: Int,
        percentileRank: Double? = nil,
        totalQuestions: Int,
        correctAnswers: Int,
        accuracyPercentage: Double,
        completionTimeSeconds: Int? = nil,
        completedAt: Date,
        domainScores: [String: DomainScore]? = nil,
        confidenceInterval: ConfidenceInterval? = nil
    ) {
        self.id = id
        self.testSessionId = testSessionId
        self.userId = userId
        self.iqScore = iqScore
        self.percentileRank = percentileRank
        self.totalQuestions = totalQuestions
        self.correctAnswers = correctAnswers
        self.accuracyPercentage = accuracyPercentage
        self.completionTimeSeconds = completionTimeSeconds
        self.completedAt = completedAt
        self.domainScores = domainScores
        self.confidenceInterval = confidenceInterval
    }

    var accuracy: Double {
        accuracyPercentage / 100.0
    }

    var completionTimeFormatted: String {
        guard let seconds = completionTimeSeconds else { return "N/A" }
        let minutes = seconds / 60
        let secs = seconds % 60
        return String(format: "%d:%02d", minutes, secs)
    }

    /// Formatted percentile string (e.g., "Top 16%", "Top 50%")
    var percentileFormatted: String? {
        guard let percentile = percentileRank else { return nil }
        // percentileRank is 0-100, representing what % scored below you
        // So if you're at 84th percentile, you're in the top 16%
        let topPercent = Int(round(100 - percentile))
        return "Top \(topPercent)%"
    }

    /// Detailed percentile description (e.g., "84th percentile")
    var percentileDescription: String? {
        guard let percentile = percentileRank else { return nil }
        return "\(Int(round(percentile)).ordinalString) percentile"
    }

    enum CodingKeys: String, CodingKey {
        case id
        case testSessionId = "test_session_id"
        case userId = "user_id"
        case iqScore = "iq_score"
        case percentileRank = "percentile_rank"
        case totalQuestions = "total_questions"
        case correctAnswers = "correct_answers"
        case accuracyPercentage = "accuracy_percentage"
        case completionTimeSeconds = "completion_time_seconds"
        case completedAt = "completed_at"
        case domainScores = "domain_scores"
        case confidenceInterval = "confidence_interval"
    }

    /// Score displayed with confidence interval range when available (e.g., "108 (101-115)")
    var scoreWithConfidenceInterval: String {
        if let ci = confidenceInterval {
            return "\(iqScore) (\(ci.rangeFormatted))"
        }
        return "\(iqScore)"
    }

    /// Accessibility description for the score with confidence interval
    var scoreAccessibilityDescription: String {
        if let ci = confidenceInterval {
            return "IQ score \(iqScore). \(ci.accessibilityDescription)"
        }
        return "IQ score \(iqScore)"
    }
}

// MARK: - Domain Score Helpers

extension TestResult {
    /// All available cognitive domain types
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

    /// Returns domain scores sorted by domain order
    var sortedDomainScores: [(domain: CognitiveDomain, score: DomainScore)]? {
        guard let scores = domainScores else { return nil }

        return CognitiveDomain.allCases.compactMap { domain in
            guard let score = scores[domain.rawValue] else { return nil }
            return (domain, score)
        }
    }

    /// Returns the strongest domain (highest percentage)
    var strongestDomain: (domain: CognitiveDomain, score: DomainScore)? {
        sortedDomainScores?
            .filter { $0.score.pct != nil && $0.score.total > 0 }
            .max { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }
    }

    /// Returns the weakest domain (lowest percentage)
    var weakestDomain: (domain: CognitiveDomain, score: DomainScore)? {
        sortedDomainScores?
            .filter { $0.score.pct != nil && $0.score.total > 0 }
            .min { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }
    }
}
