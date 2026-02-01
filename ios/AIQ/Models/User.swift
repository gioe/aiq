import AIQAPIClient
import Foundation

// MARK: - User Type Alias

/// User model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.UserResponse` type.
/// UI-specific computed properties are provided via the `User+Extensions.swift` file.
///
/// - Note: The generated type includes required fields (id, email, createdAt, notificationEnabled)
///   and optional fields (firstName, lastName, birthYear, educationLevel, country, region, lastLoginAt).
typealias User = Components.Schemas.UserResponse

// MARK: - Education Level

/// Education level enumeration re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.EducationLevelSchema` type.
/// UI-specific computed properties are provided via an extension below.
///
/// **Available Cases:**
/// - high_school
/// - some_college
/// - associates
/// - bachelors
/// - masters
/// - doctorate
/// - prefer_not_to_say
public typealias EducationLevel = Components.Schemas.EducationLevelSchema

/// UI-specific extension for EducationLevel
public extension Components.Schemas.EducationLevelSchema {
    /// User-friendly display name for the education level
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

/// User profile update model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.UserProfileUpdate` type.
/// Used for updating user profile information (name and notification settings).
///
/// **Generated Properties:**
/// - firstName: String? (mapped from first_name, optional in generated type)
/// - lastName: String? (mapped from last_name, optional in generated type)
/// - notificationEnabled: Bool? (mapped from notification_enabled, optional in generated type)
public typealias UserProfile = Components.Schemas.UserProfileUpdate
