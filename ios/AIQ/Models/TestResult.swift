import Foundation

/// Represents performance breakdown for a single cognitive domain.
struct DomainScore: Codable, Equatable {
    let correct: Int
    let total: Int
    let pct: Double?

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
        domainScores: [String: DomainScore]? = nil
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
        let ordinal = ordinalSuffix(for: Int(round(percentile)))
        return "\(Int(round(percentile)))\(ordinal) percentile"
    }

    private func ordinalSuffix(for number: Int) -> String {
        let ones = number % 10
        let tens = (number % 100) / 10

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
