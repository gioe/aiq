import Foundation

/// Response schema for checking active test session status
struct TestSessionStatusResponse: Codable, Equatable {
    /// The active test session details
    let session: TestSession
    /// Number of questions answered in this session
    let questionsCount: Int
    /// Questions for this session (if session is in_progress)
    let questions: [Question]?

    enum CodingKeys: String, CodingKey {
        case session
        case questionsCount = "questions_count"
        case questions
    }
}
