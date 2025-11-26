import Foundation

struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct RegisterRequest: Codable {
    let email: String
    let password: String
    let firstName: String
    let lastName: String

    // Optional demographic data for norming study (P13-001)
    let birthYear: Int?
    let educationLevel: EducationLevel?
    let country: String?
    let region: String?

    enum CodingKeys: String, CodingKey {
        case email
        case password
        case firstName = "first_name"
        case lastName = "last_name"
        case birthYear = "birth_year"
        case educationLevel = "education_level"
        case country
        case region
    }
}

struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let user: User

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case user
    }
}
