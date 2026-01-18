import AIQAPIClient
import Foundation

// MARK: - User Type Alias

/// User model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.UserResponse` type.
/// UI-specific computed properties are provided via the `User+Extensions.swift` file.
///
/// - Note: The generated type includes required fields only: id, email, firstName, lastName,
///   createdAt, notificationEnabled. Optional demographic fields (birthYear, educationLevel,
///   country, region, lastLoginAt) are added via custom decoding in extensions.
typealias User = Components.Schemas.UserResponse

// MARK: - Education Level

/// Education level enumeration for demographic data (P13-001)
///
/// This enum is not generated from the OpenAPI spec, so we maintain it manually.
/// It's used for optional demographic data collection in the user registration flow.
enum EducationLevel: String, Codable, CaseIterable {
    case highSchool = "high_school"
    case someCollege = "some_college"
    case associates
    case bachelors
    case masters // swiftlint:disable:this inclusive_language
    case doctorate
    case preferNotToSay = "prefer_not_to_say"

    var displayName: String {
        switch self {
        case .highSchool: "High School"
        case .someCollege: "Some College"
        case .associates: "Associate's Degree"
        case .bachelors: "Bachelor's Degree"
        case .masters: "Master's Degree"
        case .doctorate: "Doctorate"
        case .preferNotToSay: "Prefer not to say"
        }
    }
}

// MARK: - User Profile

/// User profile update model
///
/// Used for updating user profile information (name and notification settings).
/// This remains a manual model as it's a request DTO, not part of the OpenAPI response types.
struct UserProfile: Codable, Equatable {
    let firstName: String
    let lastName: String
    let notificationEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case firstName = "first_name"
        case lastName = "last_name"
        case notificationEnabled = "notification_enabled"
    }
}
