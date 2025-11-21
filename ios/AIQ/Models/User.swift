import Foundation

struct User: Codable, Identifiable, Equatable {
    let id: String
    let email: String
    let firstName: String
    let lastName: String
    let createdAt: Date
    let lastLoginAt: Date?
    let notificationEnabled: Bool

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
