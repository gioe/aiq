import AIQAPIClient
import Foundation

// MARK: - Auth Request Types

/// Login request type alias
///
/// Maps to `Components.Schemas.UserLogin` in the OpenAPI spec.
/// This is a request DTO containing email and password for user authentication.
public typealias LoginRequest = Components.Schemas.UserLogin

/// Register request type alias
///
/// Maps to `Components.Schemas.UserRegister` in the OpenAPI spec.
/// This is a request DTO containing user registration data including required fields
/// (email, password, firstName, lastName) and optional demographic data.
public typealias RegisterRequest = Components.Schemas.UserRegister

// MARK: - Auth Response Type

/// Authentication response type alias
///
/// Maps to `Components.Schemas.Token` in the OpenAPI spec.
/// Contains authentication tokens (access_token, refresh_token, token_type) and
/// the authenticated user's information.
///
/// **Generated Properties:**
/// - accessToken: String (mapped from access_token)
/// - refreshToken: String (mapped from refresh_token)
/// - tokenType: String (mapped from token_type)
/// - user: UserResponse (the authenticated user's data)
public typealias AuthResponse = Components.Schemas.Token
