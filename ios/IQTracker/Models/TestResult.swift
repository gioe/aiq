import Foundation

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
        case totalQuestions = "total_questions"
        case correctAnswers = "correct_answers"
        case accuracyPercentage = "accuracy_percentage"
        case completionTimeSeconds = "completion_time_seconds"
        case completedAt = "completed_at"
    }
}
