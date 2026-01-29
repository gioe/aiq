import Foundation

/// Model representing saved test progress for local persistence
struct SavedTestProgress: Codable {
    let sessionId: Int
    let userId: Int
    let questionIds: [Int]
    let userAnswers: [Int: String]
    let currentQuestionIndex: Int
    let savedAt: Date
    /// Timestamp when the test session was originally started (for timer calculation)
    let sessionStartedAt: Date?
    /// Set of question IDs where the stimulus phase has been completed
    let stimulusSeen: Set<Int>

    // MARK: - Initialization

    init(
        sessionId: Int,
        userId: Int,
        questionIds: [Int],
        userAnswers: [Int: String],
        currentQuestionIndex: Int,
        savedAt: Date,
        sessionStartedAt: Date?,
        stimulusSeen: Set<Int>
    ) {
        self.sessionId = sessionId
        self.userId = userId
        self.questionIds = questionIds
        self.userAnswers = userAnswers
        self.currentQuestionIndex = currentQuestionIndex
        self.savedAt = savedAt
        self.sessionStartedAt = sessionStartedAt
        self.stimulusSeen = stimulusSeen
    }

    var isValid: Bool {
        // Progress is only valid if saved within last 24 hours
        let dayAgo = Date().addingTimeInterval(-Constants.Test.progressValidityDuration)
        return savedAt > dayAgo
    }

    /// Check if the test time has expired based on session start time
    var isTimeExpired: Bool {
        guard let startedAt = sessionStartedAt else { return false }
        let elapsedSeconds = Int(Date().timeIntervalSince(startedAt))
        return elapsedSeconds >= TestTimerManager.totalTimeSeconds
    }

    // MARK: - Codable

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sessionId = try container.decode(Int.self, forKey: .sessionId)
        userId = try container.decode(Int.self, forKey: .userId)
        questionIds = try container.decode([Int].self, forKey: .questionIds)
        userAnswers = try container.decode([Int: String].self, forKey: .userAnswers)
        currentQuestionIndex = try container.decode(Int.self, forKey: .currentQuestionIndex)
        savedAt = try container.decode(Date.self, forKey: .savedAt)
        sessionStartedAt = try container.decodeIfPresent(Date.self, forKey: .sessionStartedAt)
        stimulusSeen = try container.decodeIfPresent(Set<Int>.self, forKey: .stimulusSeen) ?? []
    }
}
