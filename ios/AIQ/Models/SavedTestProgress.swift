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
}
