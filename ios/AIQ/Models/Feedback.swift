import AIQAPIClient
import Foundation

// MARK: - Feedback Type Aliases

/// Feedback submission model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.FeedbackSubmitRequest` type.
///
/// **Generated Properties:**
/// - name: String
/// - email: String
/// - category: FeedbackCategorySchema
/// - description: String
public typealias Feedback = Components.Schemas.FeedbackSubmitRequest

/// Feedback category enumeration re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.FeedbackCategorySchema` type.
/// UI-specific computed properties are provided via an extension below.
///
/// **Available Cases:**
/// - bug_report
/// - feature_request
/// - general_feedback
/// - question_help
/// - other
public typealias FeedbackCategory = Components.Schemas.FeedbackCategorySchema

/// Response from feedback submission endpoint re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.FeedbackSubmitResponse` type.
///
/// **Generated Properties:**
/// - success: Bool
/// - submissionId: Int (mapped from submission_id)
/// - message: String
public typealias FeedbackSubmitResponse = Components.Schemas.FeedbackSubmitResponse

// MARK: - FeedbackCategory Extension

/// UI-specific extension for FeedbackCategory
extension Components.Schemas.FeedbackCategorySchema {
    /// User-friendly display name for the feedback category
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
