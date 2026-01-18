import AIQAPIClient
import Foundation

/// Adapter that bridges the generated OpenAPI client to the existing service interfaces.
///
/// This adapter provides a migration path from the legacy `APIClient` and `APIEndpoint` enum
/// to the generated OpenAPI client. Services can be updated one at a time to use this adapter
/// instead of the legacy client.
///
/// ## Migration Strategy
///
/// The migration from `APIEndpoint` enum to generated operations follows these steps:
///
/// 1. **Phase 1 (Current)**: Add deprecation warnings to `APIEndpoint` and `APIClientProtocol`
/// 2. **Phase 2**: Create this adapter with methods matching the generated operations
/// 3. **Phase 3**: Update individual services to use generated types directly
/// 4. **Phase 4**: Remove deprecated `APIEndpoint` enum and legacy request methods
///
/// ## Usage Example
///
/// Before (using deprecated APIEndpoint):
/// ```swift
/// let response: AuthResponse = try await apiClient.request(
///     endpoint: .login,
///     method: .post,
///     body: LoginRequest(email: email, password: password)
/// )
/// ```
///
/// After (using generated client directly):
/// ```swift
/// let response = try await client.loginUserV1AuthLoginPost(
///     body: .json(.init(email: email, password: password))
/// )
/// ```
///
/// ## Notes
///
/// The generated OpenAPI client provides:
/// - Type-safe operation methods for each API endpoint
/// - Strongly-typed request and response types from `Components.Schemas`
/// - Middleware support for authentication and logging
///
/// See `AIQAPIClientFactory` for creating configured client instances with
/// authentication and logging middleware.
///
/// ## Type Mappings
///
/// Key type correspondences between legacy models and generated schemas
/// (verified against `Types.swift` generated from `openapi.json`):
///
/// | Legacy Type | Generated Schema |
/// |-------------|------------------|
/// | `AuthResponse` | `Components.Schemas.Token` |
/// | `User` | `Components.Schemas.UserResponse` |
/// | `LoginRequest` | `Components.Schemas.UserLogin` |
/// | `RegisterRequest` | `Components.Schemas.UserRegister` |
/// | `TestSessionResponse` | `Components.Schemas.TestSessionResponse` |
/// | `SubmittedTestResult` | `Components.Schemas.TestResultResponse` |
/// | `Question` | `Components.Schemas.QuestionResponse` |
enum OpenAPIClientAdapter {
    // This enum serves as a namespace for migration documentation.
    // The actual client instance is created via AIQAPIClientFactory.
    //
    // Example:
    //
    // let factory = AIQAPIClientFactory(serverURL: URL(string: AppConfig.apiBaseURL)!)
    // let client = factory.makeClient()
    //
    // // Login using generated operation
    // let response = try await client.loginUserV1AuthLoginPost(
    //     body: .json(.init(email: "user@example.com", password: "secret"))
    // )
    //
    // // Handle response
    // switch response {
    // case .ok(let okResponse):
    //     if case .json(let token) = okResponse.body {
    //         // Set tokens in middleware for future requests
    //         await factory.authMiddleware.setTokens(
    //             accessToken: token.accessToken,
    //             refreshToken: token.refreshToken
    //         )
    //     }
    // case .unprocessableContent(let error):
    //     // Handle validation errors
    //     throw mapToAPIError(error)
    // case .undocumented(let statusCode, _):
    //     throw APIError.serverError(statusCode: statusCode, message: nil)
    // }
}
