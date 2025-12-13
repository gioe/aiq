import Foundation

enum TestStatus: String, Codable, Equatable {
    case inProgress = "in_progress"
    case completed
    case abandoned
}

struct TestSession: Codable, Identifiable, Equatable {
    let id: Int
    let userId: Int
    let startedAt: Date
    let completedAt: Date?
    let status: TestStatus
    let questions: [Question]?
    let timeLimitExceeded: Bool?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case status
        case questions
        case timeLimitExceeded = "time_limit_exceeded"
    }
}

struct StartTestResponse: Codable, Equatable {
    let session: TestSession
    let questions: [Question]
    let totalQuestions: Int

    enum CodingKeys: String, CodingKey {
        case session
        case questions
        case totalQuestions = "total_questions"
    }
}

struct TestSubmission: Codable, Equatable {
    let sessionId: Int
    let responses: [QuestionResponse]
    let timeLimitExceeded: Bool

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case responses
        case timeLimitExceeded = "time_limit_exceeded"
    }

    init(sessionId: Int, responses: [QuestionResponse], timeLimitExceeded: Bool = false) {
        self.sessionId = sessionId
        self.responses = responses
        self.timeLimitExceeded = timeLimitExceeded
    }
}

struct TestSubmitResponse: Codable, Equatable {
    let session: TestSession
    let result: SubmittedTestResult
    let responsesCount: Int
    let message: String

    enum CodingKeys: String, CodingKey {
        case session
        case result
        case responsesCount = "responses_count"
        case message
    }
}

struct TestAbandonResponse: Codable, Equatable {
    let session: TestSession
    let message: String
    let responsesSaved: Int

    enum CodingKeys: String, CodingKey {
        case session
        case message
        case responsesSaved = "responses_saved"
    }
}

struct SubmittedTestResult: Codable, Equatable {
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
    let responseTimeFlags: ResponseTimeFlags?
    let domainScores: [String: DomainScore]?

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
        case responseTimeFlags = "response_time_flags"
        case domainScores = "domain_scores"
    }
}

/// Response time analysis flags returned from the backend
struct ResponseTimeFlags: Codable, Equatable {
    let totalTimeSeconds: Int?
    let meanTimePerQuestion: Double?
    let medianTimePerQuestion: Double?
    let stdTimePerQuestion: Double?
    let anomalies: [ResponseTimeAnomaly]?
    let flags: [String]?
    let validityConcern: Bool?

    enum CodingKeys: String, CodingKey {
        case totalTimeSeconds = "total_time_seconds"
        case meanTimePerQuestion = "mean_time_per_question"
        case medianTimePerQuestion = "median_time_per_question"
        case stdTimePerQuestion = "std_time_per_question"
        case anomalies
        case flags
        case validityConcern = "validity_concern"
    }
}

/// Individual response time anomaly
struct ResponseTimeAnomaly: Codable, Equatable {
    let questionId: Int
    let timeSeconds: Int
    let anomalyType: String
    let zScore: Double?

    enum CodingKeys: String, CodingKey {
        case questionId = "question_id"
        case timeSeconds = "time_seconds"
        case anomalyType = "anomaly_type"
        case zScore = "z_score"
    }
}
