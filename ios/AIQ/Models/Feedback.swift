import Foundation

/// Feedback submission model
struct Feedback: Codable, Equatable {
    let name: String
    let email: String
    let category: FeedbackCategory
    let description: String

    enum CodingKeys: String, CodingKey {
        case name
        case email
        case category
        case description
    }
}

/// Categories for feedback submissions
enum FeedbackCategory: String, Codable, CaseIterable {
    case bugReport = "bug_report"
    case featureRequest = "feature_request"
    case generalFeedback = "general_feedback"
    case questionHelp = "question_help"
    case other

    var displayName: String {
        switch self {
        case .bugReport:
            "Bug Report"
        case .featureRequest:
            "Feature Request"
        case .generalFeedback:
            "General Feedback"
        case .questionHelp:
            "Question/Help"
        case .other:
            "Other"
        }
    }
}

/// Response from feedback submission endpoint
struct FeedbackSubmitResponse: Decodable {
    let success: Bool
    let submissionId: Int?
    let message: String

    enum CodingKeys: String, CodingKey {
        case success
        case submissionId = "submission_id"
        case message
    }
}
