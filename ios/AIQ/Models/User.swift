import Foundation

/// Education level enumeration for demographic data (P13-001)
enum EducationLevel: String, Codable, CaseIterable {
    case highSchool = "high_school"
    case someCollege = "some_college"
    case associates = "associates"
    case bachelors = "bachelors"
    case masters = "masters"
    case doctorate = "doctorate"
    case preferNotToSay = "prefer_not_to_say"

    var displayName: String {
        switch self {
        case .highSchool: return "High School"
        case .someCollege: return "Some College"
        case .associates: return "Associate's Degree"
        case .bachelors: return "Bachelor's Degree"
        case .masters: return "Master's Degree"
        case .doctorate: return "Doctorate"
        case .preferNotToSay: return "Prefer not to say"
        }
    }
}

struct User: Codable, Identifiable, Equatable {
    let id: String
    let email: String
    let firstName: String
    let lastName: String
    let createdAt: Date
    let lastLoginAt: Date?
    let notificationEnabled: Bool

    // Optional demographic data for norming study (P13-001)
    let birthYear: Int?
    let educationLevel: EducationLevel?
    let country: String?
    let region: String?

    var fullName: String {
        "\(firstName) \(lastName)"
    }

    enum CodingKeys: String, CodingKey {
        case id
        case email
        case firstName = "first_name"
        case lastName = "last_name"
        case createdAt = "created_at"
        case lastLoginAt = "last_login_at"
        case notificationEnabled = "notification_enabled"
        case birthYear = "birth_year"
        case educationLevel = "education_level"
        case country
        case region
    }
}

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
