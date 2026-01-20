import AIQAPIClient
import Foundation

/// Response schema for checking active test session status re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.TestSessionStatusResponse` type.
/// This response is returned when checking if a user has an active test session.
/// It includes the session details, question count, and optionally the questions
/// themselves if the session is in progress.
///
/// **Generated Properties:**
/// - session: TestSessionResponse - The active test session details
/// - questionsCount: Int (mapped from questions_count) - Number of questions answered in this session
/// - questions: [QuestionResponse]? - Questions for this session (if session is in_progress)
public typealias TestSessionStatusResponse = Components.Schemas.TestSessionStatusResponse
