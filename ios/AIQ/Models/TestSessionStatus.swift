import Foundation

/// Response schema for checking active test session status
///
/// This response is returned when checking if a user has an active test session.
/// It includes the session details, question count, and optionally the questions
/// themselves if the session is in progress.
///
/// **Properties:**
/// - session: The active test session (uses TestSession typealias)
/// - questionsCount: Number of questions answered in this session
/// - questions: Questions for this session (if session is in_progress)
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
