import Foundation

/// Education level enumeration for demographic data (P13-001)
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

struct User: Codable, Identifiable, Equatable {
    let id: Int
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
