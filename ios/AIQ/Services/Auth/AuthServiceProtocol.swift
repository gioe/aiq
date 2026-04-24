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

    /// Exchange an Apple identity token for AIQ tokens and persist the session.
    func loginWithApple(identityToken: String) async throws -> AuthResponse

    /// Exchange a Google identity token for AIQ tokens and persist the session.
    func loginWithGoogle(identityToken: String) async throws -> AuthResponse

    /// Attach a completed guest test result to the authenticated account.
    func claimGuestResult(claimToken: String) async throws -> GuestClaimResponse

    /// Refresh the access token using refresh token
    func refreshToken() async throws -> AuthResponse

    /// Logout the current user
    func logout() async throws

    /// Delete the user account and all associated data
    func deleteAccount() async throws

    /// Get the current access token
    func getAccessToken() -> String?

    /// Check if user is authenticated
    var isAuthenticated: Bool { get }

    /// Get the current user
    var currentUser: User? { get }

    /// Awaits completion of any async initialization work (e.g. token restoration).
    /// Call this before making API requests to guarantee middleware is ready.
    func awaitInitialization() async
}

extension AuthServiceProtocol {
    func awaitInitialization() async {}
}
