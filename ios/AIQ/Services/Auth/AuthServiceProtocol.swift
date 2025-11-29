import Foundation

/// Protocol defining authentication service interface
protocol AuthServiceProtocol: AnyObject {
    /// Register a new user
    func register( // swiftlint:disable:this function_parameter_count
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear: Int?,
        educationLevel: EducationLevel?,
        country: String?,
        region: String?
    ) async throws -> AuthResponse

    /// Login with email and password
    func login(email: String, password: String) async throws -> AuthResponse

    /// Refresh the access token using refresh token
    func refreshToken() async throws -> AuthResponse

    /// Logout the current user
    func logout() async throws

    /// Get the current access token
    func getAccessToken() -> String?

    /// Check if user is authenticated
    var isAuthenticated: Bool { get }

    /// Get the current user
    var currentUser: User? { get }
}
