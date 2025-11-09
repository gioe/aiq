import Foundation

/// Model representing saved test progress for local persistence
struct SavedTestProgress: Codable {
    let sessionId: Int
    let userId: Int
    let questionIds: [Int]
    let userAnswers: [Int: String]
    let currentQuestionIndex: Int
    let savedAt: Date

    var isValid: Bool {
        // Progress is only valid if saved within last 24 hours
        let dayAgo = Date().addingTimeInterval(-24 * 60 * 60)
        return savedAt > dayAgo
    }
}
