import Foundation

// MARK: - Test Data Structures for API Integration Tests

// Note: Models that match app models (TestSession, Question, TestResult, etc.)
// have been removed to avoid conflicts. Use @testable import AIQ to access real models.

struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct RegistrationRequest: Codable {
    let email: String
    let password: String
    let firstName: String
    let lastName: String

    enum CodingKeys: String, CodingKey {
        case email
        case password
        case firstName = "first_name"
        case lastName = "last_name"
    }
}

struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let user: UserProfile

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case user
    }
}

struct UserProfile: Codable {
    let id: String
    let email: String
    let firstName: String
    let lastName: String

    enum CodingKeys: String, CodingKey {
        case id
        case email
        case firstName = "first_name"
        case lastName = "last_name"
    }
}

// Note: Use AIQ.TestSession, AIQ.Question, AIQ.TestResult, etc. from the main app
// instead of defining duplicate test models here
