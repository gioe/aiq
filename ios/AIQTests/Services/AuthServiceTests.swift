import Combine
import XCTest

@testable import AIQ

final class AuthServiceTests: XCTestCase {
    var sut: AuthService!
    var mockAPIClient: MockAPIClient!
    var mockSecureStorage: MockSecureStorage!

    override func setUp() async throws {
        try await super.setUp()
        mockAPIClient = MockAPIClient()
        mockSecureStorage = MockSecureStorage()
        sut = AuthService(apiClient: mockAPIClient, secureStorage: mockSecureStorage)
    }

    override func tearDown() {
        sut = nil
        mockAPIClient = nil
        mockSecureStorage = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInit_LoadsExistingTokenFromStorage() async throws {
        // Given
        let existingToken = "existing_access_token"
        try mockSecureStorage.save(existingToken, forKey: SecureStorageKey.accessToken.rawValue)

        // When
        let newSut = AuthService(apiClient: mockAPIClient, secureStorage: mockSecureStorage)

        // Then
        let token = await newSut.getAccessToken()
        XCTAssertEqual(token, existingToken, "Should load existing token from storage on init")

        // Verify setAuthToken was called on API client during init (Critical Issue #1)
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        let lastAuthToken = await mockAPIClient.lastAuthToken
        XCTAssertTrue(setAuthTokenCalled, "setAuthToken should be called during init when token exists")
        XCTAssertEqual(lastAuthToken, existingToken, "API client should receive the existing token")
    }

    func testInit_HandlesNoExistingToken() async throws {
        // Given - no token in storage

        // When
        let newSut = AuthService(apiClient: mockAPIClient, secureStorage: mockSecureStorage)

        // Then
        let token = await newSut.getAccessToken()
        XCTAssertNil(token, "Should return nil when no token exists in storage")
    }

    func testInit_HandlesStorageErrorGracefully() async throws {
        // Given - Storage will throw on retrieve
        mockSecureStorage.setShouldThrowOnRetrieve(true)

        // When - Init should not crash even if storage throws
        let newSut = AuthService(apiClient: mockAPIClient, secureStorage: mockSecureStorage)

        // Then - Should handle gracefully without crashing
        let token = await newSut.getAccessToken()
        XCTAssertNil(token, "Should return nil when storage throws error")

        // setAuthToken should NOT have been called (since no token was retrieved)
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        XCTAssertFalse(setAuthTokenCalled, "setAuthToken should not be called when storage fails")
    }

    func testIsAuthenticated_ReturnsTrueWhenTokenExists() async throws {
        // Given
        let accessToken = "valid_access_token"
        try mockSecureStorage.save(accessToken, forKey: SecureStorageKey.accessToken.rawValue)

        // When
        let isAuthenticated = await sut.isAuthenticated

        // Then
        XCTAssertTrue(isAuthenticated, "Should return true when access token exists")
    }

    func testIsAuthenticated_ReturnsFalseWhenNoToken() async throws {
        // Given - no token in storage

        // When
        let isAuthenticated = await sut.isAuthenticated

        // Then
        XCTAssertFalse(isAuthenticated, "Should return false when no access token exists")
    }

    func testIsAuthenticated_ReturnsFalseOnStorageError() async throws {
        // Given - Storage has a token but will throw on retrieve
        try mockSecureStorage.save("some_token", forKey: SecureStorageKey.accessToken.rawValue)
        mockSecureStorage.setShouldThrowOnRetrieve(true)

        // When
        let isAuthenticated = await sut.isAuthenticated

        // Then - Should return false when storage error occurs (fail-safe behavior)
        XCTAssertFalse(isAuthenticated, "Should return false when storage throws error")
    }

    // MARK: - Login Tests

    func testLogin_Success() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let mockUser = User(
            id: 1,
            email: email,
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)

        // When
        let response = try await sut.login(email: email, password: password)

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .login, "Should call login endpoint")
        XCTAssertEqual(lastMethod, .post, "Should use POST method")
        XCTAssertFalse(lastRequiresAuth ?? true, "Should not require auth for login")

        // Verify request body contains correct fields
        let requestBody = await mockAPIClient.lastBodyAsDictionary
        XCTAssertNotNil(requestBody, "Login request should have a body")
        XCTAssertEqual(requestBody?["email"] as? String, email, "Request body should contain email")
        XCTAssertEqual(requestBody?["password"] as? String, password, "Request body should contain password")

        XCTAssertEqual(response.accessToken, "access_token_123")
        XCTAssertEqual(response.refreshToken, "refresh_token_456")
        XCTAssertEqual(response.user.id, 1)

        // Verify tokens were saved to secure storage
        let savedAccessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        let savedRefreshToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        )
        let savedUserId = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.userId.rawValue
        )

        XCTAssertEqual(savedAccessToken, "access_token_123")
        XCTAssertEqual(savedRefreshToken, "refresh_token_456")
        XCTAssertEqual(savedUserId, "1")

        // Verify current user is set
        let currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser)
        XCTAssertEqual(currentUser?.id, 1)
        XCTAssertEqual(currentUser?.email, email)

        // Verify setAuthToken was called on API client (Critical Issue #1)
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        let lastAuthToken = await mockAPIClient.lastAuthToken
        XCTAssertTrue(setAuthTokenCalled, "setAuthToken should be called after login")
        XCTAssertEqual(lastAuthToken, "access_token_123", "API client should receive the new access token")
    }

    func testLogin_NetworkError() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        await mockAPIClient.setMockError(networkError)

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.login(email: email, password: password)
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testLogin_UnauthorizedError() async throws {
        // Given
        let email = "test@example.com"
        let password = "wrongpassword"
        let unauthorizedError = APIError.unauthorized(message: "Invalid credentials")

        await mockAPIClient.setMockError(unauthorizedError)

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.login(email: email, password: password)
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testLogin_StorageError_StillThrows() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let mockUser = User(
            id: 1,
            email: email,
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)
        mockSecureStorage.setShouldThrowOnSave(true)

        // When/Then
        do {
            _ = try await sut.login(email: email, password: password)
            XCTFail("Should throw storage error")
        } catch {
            // Expected - storage save failed
            XCTAssertTrue(error is MockSecureStorageError)
        }
    }

    func testLogin_PartialStorageSave_AccessTokenSucceeds_RefreshTokenFails() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let mockUser = User(
            id: 1,
            email: email,
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)

        // Configure storage to fail only on refresh token save
        mockSecureStorage.setShouldThrowOnSave(
            forKey: SecureStorageKey.refreshToken.rawValue,
            true
        )

        // When/Then
        do {
            _ = try await sut.login(email: email, password: password)
            XCTFail("Should throw storage error when refresh token save fails")
        } catch {
            // Expected - refresh token save failed
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError")

            // Verify partial state: access token WAS saved before failure
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "access_token_123",
                "Access token should be saved before refresh token failure"
            )

            // Verify refresh token was NOT saved (threw error)
            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertNil(
                savedRefreshToken,
                "Refresh token should not be saved when save fails"
            )

            // Verify userId was NOT saved (saveAuthData stops on first failure)
            let savedUserId = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.userId.rawValue
            )
            XCTAssertNil(
                savedUserId,
                "User ID should not be saved after refresh token failure"
            )

            // CURRENT BEHAVIOR: Storage is left in inconsistent state
            // - Access token exists but refresh token and userId don't
            // - This means isAuthenticated would return true, but token refresh would fail
            // - User would appear authenticated but be unable to make authenticated requests
            //
            // POTENTIAL IMPROVEMENT: Consider implementing rollback/transaction semantics:
            // 1. Save all values to temporary keys first
            // 2. If all saves succeed, rename to actual keys atomically
            // 3. If any save fails, clean up temporary keys
            // OR: Delete successfully saved keys if later saves fail
        }
    }

    func testLogin_PartialStorageSave_RefreshTokenSucceeds_UserIdFails() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let mockUser = User(
            id: 1,
            email: email,
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)

        // Configure storage to fail only on userId save
        mockSecureStorage.setShouldThrowOnSave(
            forKey: SecureStorageKey.userId.rawValue,
            true
        )

        // When/Then
        do {
            _ = try await sut.login(email: email, password: password)
            XCTFail("Should throw storage error when userId save fails")
        } catch {
            // Expected - userId save failed
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError")

            // Verify partial state: both tokens WERE saved before failure
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "access_token_123",
                "Access token should be saved before userId failure"
            )

            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertEqual(
                savedRefreshToken,
                "refresh_token_456",
                "Refresh token should be saved before userId failure"
            )

            // Verify userId was NOT saved (threw error)
            let savedUserId = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.userId.rawValue
            )
            XCTAssertNil(
                savedUserId,
                "User ID should not be saved when save fails"
            )

            // CURRENT BEHAVIOR: Storage is left in inconsistent state
            // - Access token and refresh token exist but userId doesn't
            // - This is less critical than missing refresh token (tokens work for auth)
            // - But userId is missing, which may affect analytics or user tracking
            //
            // POTENTIAL IMPROVEMENT: Same as above - implement rollback/transaction semantics
        }
    }

    // MARK: - Registration Tests

    func testRegister_Success_WithAllFields() async throws {
        // Given
        let email = "newuser@example.com"
        let password = "password123"
        let firstName = "New"
        let lastName = "User"
        let birthYear = 1990
        let educationLevel = EducationLevel.bachelors
        let country = "US"
        let region = "CA"

        let mockUser = User(
            id: 2,
            email: email,
            firstName: firstName,
            lastName: lastName,
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: birthYear,
            educationLevel: educationLevel,
            country: country,
            region: region
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .register)

        // When
        let response = try await sut.register(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName,
            birthYear: birthYear,
            educationLevel: educationLevel,
            country: country,
            region: region
        )

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .register, "Should call register endpoint")
        XCTAssertEqual(lastMethod, .post, "Should use POST method")
        XCTAssertFalse(lastRequiresAuth ?? true, "Should not require auth for registration")

        // Verify request body contains correct fields (with snake_case conversion)
        let requestBody = await mockAPIClient.lastBodyAsDictionary
        XCTAssertNotNil(requestBody, "Register request should have a body")
        XCTAssertEqual(requestBody?["email"] as? String, email, "Request body should contain email")
        XCTAssertEqual(requestBody?["password"] as? String, password, "Request body should contain password")
        XCTAssertEqual(requestBody?["first_name"] as? String, firstName, "Request body should contain first_name")
        XCTAssertEqual(requestBody?["last_name"] as? String, lastName, "Request body should contain last_name")
        XCTAssertEqual(requestBody?["birth_year"] as? Int, birthYear, "Request body should contain birth_year")
        XCTAssertEqual(requestBody?["education_level"] as? String, educationLevel.rawValue, "Request body should contain education_level")
        XCTAssertEqual(requestBody?["country"] as? String, country, "Request body should contain country")
        XCTAssertEqual(requestBody?["region"] as? String, region, "Request body should contain region")

        XCTAssertEqual(response.accessToken, "new_access_token")
        XCTAssertEqual(response.user.id, 2)

        // Verify tokens were saved
        let savedAccessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        XCTAssertEqual(savedAccessToken, "new_access_token")

        // Verify current user is set
        let currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser)
        XCTAssertEqual(currentUser?.id, 2)
        XCTAssertEqual(currentUser?.birthYear, birthYear)
        XCTAssertEqual(currentUser?.educationLevel, educationLevel)

        // Verify setAuthToken was called on API client (Critical Issue #1)
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        let lastAuthToken = await mockAPIClient.lastAuthToken
        XCTAssertTrue(setAuthTokenCalled, "setAuthToken should be called after registration")
        XCTAssertEqual(lastAuthToken, "new_access_token", "API client should receive the new access token")
    }

    func testRegister_Success_WithMinimalFields() async throws {
        // Given
        let email = "minimal@example.com"
        let password = "password123"
        let firstName = "Min"
        let lastName = "User"

        let mockUser = User(
            id: 3,
            email: email,
            firstName: firstName,
            lastName: lastName,
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "minimal_access_token",
            refreshToken: "minimal_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .register)

        // When
        let response = try await sut.register(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName
        )

        // Then
        // Verify request body contains only required fields
        let requestBody = await mockAPIClient.lastBodyAsDictionary
        XCTAssertNotNil(requestBody, "Register request should have a body")
        XCTAssertEqual(requestBody?["email"] as? String, email, "Request body should contain email")
        XCTAssertEqual(requestBody?["password"] as? String, password, "Request body should contain password")
        XCTAssertEqual(requestBody?["first_name"] as? String, firstName, "Request body should contain first_name")
        XCTAssertEqual(requestBody?["last_name"] as? String, lastName, "Request body should contain last_name")
        // Verify optional fields are omitted (not present in JSON, not sent as null)
        XCTAssertNil(requestBody?["birth_year"], "birth_year should be omitted when nil")
        XCTAssertNil(requestBody?["education_level"], "education_level should be omitted when nil")
        XCTAssertNil(requestBody?["country"], "country should be omitted when nil")
        XCTAssertNil(requestBody?["region"], "region should be omitted when nil")

        XCTAssertEqual(response.accessToken, "minimal_access_token")
        XCTAssertEqual(response.user.id, 3)
        XCTAssertNil(response.user.birthYear)
        XCTAssertNil(response.user.educationLevel)
    }

    func testRegister_DuplicateEmail_Error() async throws {
        // Given
        let email = "existing@example.com"
        let password = "password123"
        let firstName = "Test"
        let lastName = "User"
        let conflictError = APIError.unprocessableEntity(message: "Email already exists")

        await mockAPIClient.setMockError(conflictError)

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.register(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName
            )
            XCTFail("Should throw unprocessable entity error")
        } catch {
            assertAPIError(error, is: conflictError)
        }
    }

    func testRegister_ValidationError() async throws {
        // Given
        let email = "invalid-email"
        let password = "weak"
        let firstName = "Test"
        let lastName = "User"
        let validationError = APIError.badRequest(message: "Invalid email format")

        await mockAPIClient.setMockError(validationError)

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.register(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName
            )
            XCTFail("Should throw bad request error")
        } catch {
            assertAPIError(error, is: validationError)
        }
    }

    func testRegister_PartialStorageSave_AccessTokenSucceeds_RefreshTokenFails() async throws {
        // Given
        let email = "newuser@example.com"
        let password = "password123"
        let firstName = "New"
        let lastName = "User"
        let mockUser = User(
            id: 2,
            email: email,
            firstName: firstName,
            lastName: lastName,
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .register)

        // Configure storage to fail only on refresh token save
        mockSecureStorage.setShouldThrowOnSave(
            forKey: SecureStorageKey.refreshToken.rawValue,
            true
        )

        // When/Then
        do {
            _ = try await sut.register(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName
            )
            XCTFail("Should throw storage error when refresh token save fails")
        } catch {
            // Expected - refresh token save failed
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError")

            // Verify partial state: access token WAS saved before failure
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "new_access_token",
                "Access token should be saved before refresh token failure"
            )

            // Verify refresh token was NOT saved (threw error)
            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertNil(
                savedRefreshToken,
                "Refresh token should not be saved when save fails"
            )

            // CURRENT BEHAVIOR: Same as login - storage left in inconsistent state
            // Registration fails to complete, leaving partial auth data in storage
        }
    }

    func testRegister_PartialStorageSave_RefreshTokenSucceeds_UserIdFails() async throws {
        // Given
        let email = "newuser@example.com"
        let password = "password123"
        let firstName = "New"
        let lastName = "User"
        let mockUser = User(
            id: 2,
            email: email,
            firstName: firstName,
            lastName: lastName,
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .register)

        // Configure storage to fail only on userId save
        mockSecureStorage.setShouldThrowOnSave(
            forKey: SecureStorageKey.userId.rawValue,
            true
        )

        // When/Then
        do {
            _ = try await sut.register(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName
            )
            XCTFail("Should throw storage error when userId save fails")
        } catch {
            // Expected - userId save failed
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError")

            // Verify partial state: both tokens WERE saved before failure
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "new_access_token",
                "Access token should be saved before userId failure"
            )

            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertEqual(
                savedRefreshToken,
                "new_refresh_token",
                "Refresh token should be saved before userId failure"
            )

            // CURRENT BEHAVIOR: Same as login - storage left in inconsistent state
            // Both tokens saved but userId missing
        }
    }

    // MARK: - Logout Tests

    func testLogout_Success() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        // Mock successful logout response
        await mockAPIClient.setResponse("success", for: .logout)

        // When
        try await sut.logout()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .logout, "Should call logout endpoint")
        XCTAssertEqual(lastMethod, .post, "Should use POST method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for logout")

        // Verify all tokens were cleared
        let accessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        let refreshToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        )
        let userId = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.userId.rawValue
        )

        XCTAssertNil(accessToken, "Access token should be cleared")
        XCTAssertNil(refreshToken, "Refresh token should be cleared")
        XCTAssertNil(userId, "User ID should be cleared")

        // Verify current user is cleared
        let currentUser = await sut.currentUser
        XCTAssertNil(currentUser, "Current user should be cleared")

        // Verify isAuthenticated returns false
        let isAuthenticated = await sut.isAuthenticated
        XCTAssertFalse(isAuthenticated, "Should not be authenticated after logout")

        // Verify setAuthToken was called with nil to clear API client token (Critical Issue #1)
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        let lastAuthToken = await mockAPIClient.lastAuthToken
        XCTAssertTrue(setAuthTokenCalled, "setAuthToken should be called after logout")
        XCTAssertEqual(lastAuthToken, .some(nil), "API client token should be cleared (set to nil)")
    }

    func testLogout_APIError_StillClearsLocalData() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        // Mock API error (e.g., network error)
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: nil)
        )
        await mockAPIClient.setMockError(networkError)

        // When - Logout should succeed even if API call fails (best effort)
        try await sut.logout()

        // Then - Local data should still be cleared
        let accessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        let refreshToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        )

        XCTAssertNil(accessToken, "Access token should be cleared even on API error")
        XCTAssertNil(refreshToken, "Refresh token should be cleared even on API error")

        let isAuthenticated = await sut.isAuthenticated
        XCTAssertFalse(isAuthenticated, "Should not be authenticated after logout")
    }

    func testLogout_WhenNotAuthenticated() async throws {
        // Given - No tokens in storage

        // Mock logout response
        await mockAPIClient.setResponse("success", for: .logout)

        // When
        try await sut.logout()

        // Then - Should still call API and clear data (no-op)
        let deleteAllCalled = mockSecureStorage.deleteAllCalled
        XCTAssertTrue(deleteAllCalled, "Should call deleteAll even when not authenticated")
    }

    func testLogout_StorageDeleteError_StillClearsInMemoryState() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        // Simulate login to set current user in memory
        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token",
            refreshToken: "refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockAPIClient.setResponse(mockAuthResponse, for: .login)
        _ = try await sut.login(email: "test@example.com", password: "password")

        // Verify user is set
        var currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser, "User should be set after login")

        // Now configure storage to fail on deleteAll
        mockSecureStorage.setShouldThrowOnDeleteAll(true)
        await mockAPIClient.reset()
        await mockAPIClient.setResponse("success", for: .logout)

        // When - Logout should handle storage error gracefully
        try await sut.logout()

        // Then - In-memory state should still be cleared
        currentUser = await sut.currentUser
        XCTAssertNil(currentUser, "Current user should be cleared even if storage deleteAll fails")

        // Verify setAuthToken(nil) was still called
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        let lastAuthToken = await mockAPIClient.lastAuthToken
        XCTAssertTrue(setAuthTokenCalled, "setAuthToken should be called even if storage fails")
        XCTAssertEqual(lastAuthToken, .some(nil), "API client token should be cleared")
    }

    // MARK: - Token Refresh Tests

    func testRefreshToken_Success() async throws {
        // Given
        let oldRefreshToken = "old_refresh_token"
        try mockSecureStorage.save("old_access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save(oldRefreshToken, forKey: SecureStorageKey.refreshToken.rawValue)

        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .refreshToken)

        // When
        let response = try await sut.refreshToken()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth
        let lastCustomHeaders = await mockAPIClient.lastCustomHeaders

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .refreshToken, "Should call refreshToken endpoint")
        XCTAssertEqual(lastMethod, .post, "Should use POST method")
        XCTAssertFalse(lastRequiresAuth ?? true, "Should not require auth (uses custom header)")
        XCTAssertNotNil(lastCustomHeaders, "Should include custom headers")
        XCTAssertEqual(
            lastCustomHeaders?["Authorization"],
            "Bearer \(oldRefreshToken)",
            "Should send refresh token in Authorization header"
        )

        // Verify request body is nil (refresh token sent in header, not body)
        let lastBody = await mockAPIClient.lastBody
        XCTAssertNil(lastBody, "Refresh token request should not have a body (token is in header)")

        XCTAssertEqual(response.accessToken, "new_access_token")
        XCTAssertEqual(response.refreshToken, "new_refresh_token")

        // Verify new tokens were saved
        let savedAccessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        let savedRefreshToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        )

        XCTAssertEqual(savedAccessToken, "new_access_token")
        XCTAssertEqual(savedRefreshToken, "new_refresh_token")

        // Verify setAuthToken was called on API client (Critical Issue #1)
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        let lastAuthToken = await mockAPIClient.lastAuthToken
        XCTAssertTrue(setAuthTokenCalled, "setAuthToken should be called after token refresh")
        XCTAssertEqual(lastAuthToken, "new_access_token", "API client should receive the new access token")
    }

    func testRefreshToken_NoRefreshToken_ThrowsError() async throws {
        // Given - No refresh token in storage

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.refreshToken()
            XCTFail("Should throw noRefreshToken error")
        } catch {
            assertAuthError(error, is: .noRefreshToken)
        }

        // API should not be called
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertFalse(requestCalled, "API should not be called when no refresh token")
    }

    func testRefreshToken_ExpiredRefreshToken_Error() async throws {
        // Given
        try mockSecureStorage.save("expired_refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        let unauthorizedError = APIError.unauthorized(message: "Refresh token expired")
        await mockAPIClient.setMockError(unauthorizedError)

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.refreshToken()
            XCTFail("Should throw unauthorized error")
        } catch {
            assertAPIError(error, is: unauthorizedError)
        }
    }

    func testRefreshToken_NetworkError() async throws {
        // Given
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: nil)
        )
        await mockAPIClient.setMockError(networkError)

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.refreshToken()
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testRefreshToken_PartialStorageSave_AccessTokenSucceeds_RefreshTokenFails() async throws {
        // Given
        try mockSecureStorage.save("old_refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "refreshed_access_token",
            refreshToken: "refreshed_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .refreshToken)

        // Configure storage to fail only on refresh token save
        mockSecureStorage.setShouldThrowOnSave(
            forKey: SecureStorageKey.refreshToken.rawValue,
            true
        )

        // When/Then
        do {
            _ = try await sut.refreshToken()
            XCTFail("Should throw storage error when refresh token save fails")
        } catch {
            // Expected - refresh token save failed
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError")

            // Verify partial state: new access token WAS saved before failure
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "refreshed_access_token",
                "New access token should be saved before refresh token failure"
            )

            // Verify refresh token was NOT updated (threw error)
            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertEqual(
                savedRefreshToken,
                "old_refresh_token",
                "Refresh token should remain as old value when save fails"
            )

            // CURRENT BEHAVIOR: Critical inconsistency in token refresh scenario
            // - New access token saved but refresh token NOT updated
            // - Access token and refresh token are now mismatched/out of sync
            // - Next API call uses new access token but old refresh token
            // - When access token expires, refresh will fail (old refresh token invalid)
            // - This is MORE CRITICAL than login/register failures because it affects
            //   already-authenticated users and will force re-login
            //
            // POTENTIAL IMPROVEMENT: Token refresh atomicity is critical for user experience
        }
    }

    func testRefreshToken_PartialStorageSave_RefreshTokenSucceeds_UserIdFails() async throws {
        // Given
        try mockSecureStorage.save("old_refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "refreshed_access_token",
            refreshToken: "refreshed_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .refreshToken)

        // Configure storage to fail only on userId save
        mockSecureStorage.setShouldThrowOnSave(
            forKey: SecureStorageKey.userId.rawValue,
            true
        )

        // When/Then
        do {
            _ = try await sut.refreshToken()
            XCTFail("Should throw storage error when userId save fails")
        } catch {
            // Expected - userId save failed
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError")

            // Verify partial state: both tokens WERE updated successfully
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "refreshed_access_token",
                "Access token should be saved before userId failure"
            )

            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertEqual(
                savedRefreshToken,
                "refreshed_refresh_token",
                "Refresh token should be saved before userId failure"
            )

            // CURRENT BEHAVIOR: Both tokens updated successfully but userId save failed
            // - This is less critical than refresh token failure (tokens are in sync)
            // - But userId storage failed, which may affect analytics/tracking
        }
    }

    // MARK: - Delete Account Tests

    func testDeleteAccount_Success() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        // Mock successful delete response (can be nil/empty response)
        await mockAPIClient.setResponse(String?.none, for: .deleteAccount)

        // When
        try await sut.deleteAccount()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .deleteAccount, "Should call deleteAccount endpoint")
        XCTAssertEqual(lastMethod, .delete, "Should use DELETE method")
        XCTAssertTrue(lastRequiresAuth ?? false, "Should require auth for delete account")

        // Verify all tokens were cleared
        let accessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        let refreshToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        )

        XCTAssertNil(accessToken, "Access token should be cleared")
        XCTAssertNil(refreshToken, "Refresh token should be cleared")

        // Verify current user is cleared
        let currentUser = await sut.currentUser
        XCTAssertNil(currentUser, "Current user should be cleared")

        // Verify isAuthenticated returns false
        let isAuthenticated = await sut.isAuthenticated
        XCTAssertFalse(isAuthenticated, "Should not be authenticated after account deletion")
    }

    func testDeleteAccount_APIError_StillClearsLocalData() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        // Mock API error
        let serverError = APIError.serverError(statusCode: 500, message: "Server error")
        await mockAPIClient.setMockError(serverError)

        // When - Delete account should succeed even if API call fails
        try await sut.deleteAccount()

        // Then - Local data should still be cleared (account is deleted on server or will be)
        let accessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        let refreshToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        )

        XCTAssertNil(accessToken, "Access token should be cleared even on API error")
        XCTAssertNil(refreshToken, "Refresh token should be cleared even on API error")

        let isAuthenticated = await sut.isAuthenticated
        XCTAssertFalse(isAuthenticated, "Should not be authenticated after delete account")
    }

    // MARK: - Get Access Token Tests

    func testGetAccessToken_ReturnsToken() async throws {
        // Given
        let expectedToken = "test_access_token"
        try mockSecureStorage.save(expectedToken, forKey: SecureStorageKey.accessToken.rawValue)

        // When
        let token = await sut.getAccessToken()

        // Then
        XCTAssertEqual(token, expectedToken, "Should return stored access token")
    }

    func testGetAccessToken_ReturnsNilWhenNoToken() async throws {
        // Given - No token in storage

        // When
        let token = await sut.getAccessToken()

        // Then
        XCTAssertNil(token, "Should return nil when no token in storage")
    }

    func testGetAccessToken_HandlesStorageError() async throws {
        // Given
        mockSecureStorage.setShouldThrowOnRetrieve(true)

        // When
        let token = await sut.getAccessToken()

        // Then
        XCTAssertNil(token, "Should return nil when storage throws error")
    }

    // MARK: - Current User Tests

    func testCurrentUser_SetAfterLogin() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let mockUser = User(
            id: 1,
            email: email,
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: 1990,
            educationLevel: .masters,
            country: "US",
            region: "CA"
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token",
            refreshToken: "refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)

        // When
        _ = try await sut.login(email: email, password: password)

        // Then
        let currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser)
        XCTAssertEqual(currentUser?.id, 1)
        XCTAssertEqual(currentUser?.email, email)
        XCTAssertEqual(currentUser?.firstName, "Test")
        XCTAssertEqual(currentUser?.lastName, "User")
        XCTAssertEqual(currentUser?.birthYear, 1990)
        XCTAssertEqual(currentUser?.educationLevel, .masters)
        XCTAssertEqual(currentUser?.country, "US")
        XCTAssertEqual(currentUser?.region, "CA")
    }

    func testCurrentUser_ClearedAfterLogout() async throws {
        // Given - Setup authenticated state with user
        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token",
            refreshToken: "refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)
        _ = try await sut.login(email: "test@example.com", password: "password")

        // Verify user is set
        var currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser)

        // When
        await mockAPIClient.setResponse("success", for: .logout)
        try await sut.logout()

        // Then
        currentUser = await sut.currentUser
        XCTAssertNil(currentUser, "Current user should be cleared after logout")
    }

    // MARK: - Edge Cases

    func testMultipleSuccessiveLogins_OverwritesTokens() async throws {
        // Given
        let firstUser = User(
            id: 1,
            email: "first@example.com",
            firstName: "First",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let firstResponse = AuthResponse(
            accessToken: "first_access_token",
            refreshToken: "first_refresh_token",
            tokenType: "Bearer",
            user: firstUser
        )

        let secondUser = User(
            id: 2,
            email: "second@example.com",
            firstName: "Second",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let secondResponse = AuthResponse(
            accessToken: "second_access_token",
            refreshToken: "second_refresh_token",
            tokenType: "Bearer",
            user: secondUser
        )

        await mockAPIClient.setResponse(firstResponse, for: .login)

        // When - First login
        _ = try await sut.login(email: "first@example.com", password: "password1")

        var currentUser = await sut.currentUser
        XCTAssertEqual(currentUser?.id, 1)

        // When - Second login (different user)
        await mockAPIClient.reset()
        await mockAPIClient.setResponse(secondResponse, for: .login)
        _ = try await sut.login(email: "second@example.com", password: "password2")

        // Then - Should overwrite with second user
        currentUser = await sut.currentUser
        XCTAssertEqual(currentUser?.id, 2)
        XCTAssertEqual(currentUser?.email, "second@example.com")

        let accessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        XCTAssertEqual(accessToken, "second_access_token")
    }

    func testConcurrentTokenRefresh_ThreadSafety() async throws {
        // Given
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .refreshToken)

        // When - Perform multiple concurrent refresh operations
        async let refresh1 = sut.refreshToken()
        async let refresh2 = sut.refreshToken()
        async let refresh3 = sut.refreshToken()

        // Then - All should succeed without race conditions
        let results = try await [refresh1, refresh2, refresh3]

        XCTAssertEqual(results.count, 3)
        for result in results {
            XCTAssertEqual(result.accessToken, "new_access_token")
        }
    }

    func testLogin_WithEmptyStrings_CallsAPIWithEmptyStrings() async throws {
        // Given - API will likely return an error, but we should still call it
        let mockAuthResponse = AuthResponse(
            accessToken: "token",
            refreshToken: "refresh",
            tokenType: "Bearer",
            user: User(
                id: 1,
                email: "",
                firstName: "Test",
                lastName: "User",
                createdAt: Date(),
                lastLoginAt: Date(),
                notificationEnabled: true,
                birthYear: nil,
                educationLevel: nil,
                country: nil,
                region: nil
            )
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)

        // When
        _ = try await sut.login(email: "", password: "")

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "Should call API even with empty strings")
    }

    func testConcurrentLogin_ThreadSafety() async throws {
        // Given - Multiple concurrent login attempts (Critical Issue #4)
        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: Date(),
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "concurrent_access_token",
            refreshToken: "concurrent_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .login)

        // When - Perform multiple concurrent login operations (simulates rapid button taps)
        async let login1 = sut.login(email: "test@example.com", password: "password")
        async let login2 = sut.login(email: "test@example.com", password: "password")
        async let login3 = sut.login(email: "test@example.com", password: "password")

        // Then - All should succeed without race conditions or crashes
        let results = try await [login1, login2, login3]

        XCTAssertEqual(results.count, 3, "All concurrent logins should complete")
        for result in results {
            XCTAssertEqual(result.accessToken, "concurrent_access_token")
        }

        // Verify final state is consistent
        let savedToken = try mockSecureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
        XCTAssertEqual(savedToken, "concurrent_access_token", "Storage should have consistent token")

        let currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser, "Current user should be set")
        XCTAssertEqual(currentUser?.id, 1)
    }

    func testConcurrentRegister_ThreadSafety() async throws {
        // Given - Multiple concurrent registration attempts (Critical Issue #4)
        let mockUser = User(
            id: 1,
            email: "newuser@example.com",
            firstName: "New",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "concurrent_register_token",
            refreshToken: "concurrent_register_refresh",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockAPIClient.setResponse(mockAuthResponse, for: .register)

        // When - Perform multiple concurrent register operations
        async let register1 = sut.register(
            email: "newuser@example.com",
            password: "password123",
            firstName: "New",
            lastName: "User"
        )
        async let register2 = sut.register(
            email: "newuser@example.com",
            password: "password123",
            firstName: "New",
            lastName: "User"
        )
        async let register3 = sut.register(
            email: "newuser@example.com",
            password: "password123",
            firstName: "New",
            lastName: "User"
        )

        // Then - All should succeed without race conditions or crashes
        let results = try await [register1, register2, register3]

        XCTAssertEqual(results.count, 3, "All concurrent registrations should complete")
        for result in results {
            XCTAssertEqual(result.accessToken, "concurrent_register_token")
        }

        // Verify final state is consistent
        let savedToken = try mockSecureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
        XCTAssertEqual(savedToken, "concurrent_register_token", "Storage should have consistent token")

        let currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser, "Current user should be set")
        XCTAssertEqual(currentUser?.id, 1)
    }
}

// MARK: - Helper Extensions

extension MockSecureStorage {
    func setShouldThrowOnSave(_ value: Bool) {
        shouldThrowOnSave = value
    }

    func setShouldThrowOnRetrieve(_ value: Bool) {
        shouldThrowOnRetrieve = value
    }

    func setShouldThrowOnDelete(_ value: Bool) {
        shouldThrowOnDelete = value
    }

    func setShouldThrowOnDeleteAll(_ value: Bool) {
        shouldThrowOnDeleteAll = value
    }
}

// MARK: - Error Assertion Helpers

/// Helper to assert specific APIError cases with stronger type checking
/// Fails the test if the error is not exactly the expected APIError case
extension XCTestCase {
    func assertAPIError(
        _ error: Error,
        is expectedCase: APIError,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        guard let apiError = error as? APIError else {
            XCTFail(
                "Expected APIError but got \(type(of: error)): \(error)",
                file: file,
                line: line
            )
            return
        }

        switch (apiError, expectedCase) {
        case let (.networkError(actualError), .networkError(expectedError)):
            // For network errors, just verify it's a network error (underlying error may differ)
            XCTAssertNotNil(actualError, "Network error should have underlying error", file: file, line: line)
            _ = expectedError // Silence unused warning
        case let (.unauthorized(actualMsg), .unauthorized(expectedMsg)):
            XCTAssertEqual(actualMsg, expectedMsg, "Unauthorized message mismatch", file: file, line: line)
        case let (.badRequest(actualMsg), .badRequest(expectedMsg)):
            XCTAssertEqual(actualMsg, expectedMsg, "Bad request message mismatch", file: file, line: line)
        case let (.unprocessableEntity(actualMsg), .unprocessableEntity(expectedMsg)):
            XCTAssertEqual(actualMsg, expectedMsg, "Unprocessable entity message mismatch", file: file, line: line)
        case let (.serverError(actualCode, actualMsg), .serverError(expectedCode, expectedMsg)):
            XCTAssertEqual(actualCode, expectedCode, "Server error code mismatch", file: file, line: line)
            XCTAssertEqual(actualMsg, expectedMsg, "Server error message mismatch", file: file, line: line)
        case let (.notFound(actualMsg), .notFound(expectedMsg)):
            XCTAssertEqual(actualMsg, expectedMsg, "Not found message mismatch", file: file, line: line)
        default:
            XCTFail(
                "APIError case mismatch: expected \(expectedCase), got \(apiError)",
                file: file,
                line: line
            )
        }
    }

    func assertAuthError(
        _ error: Error,
        is expectedCase: AuthError,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        guard let authError = error as? AuthError else {
            XCTFail(
                "Expected AuthError but got \(type(of: error)): \(error)",
                file: file,
                line: line
            )
            return
        }

        switch (authError, expectedCase) {
        case (.noRefreshToken, .noRefreshToken),
             (.invalidCredentials, .invalidCredentials),
             (.sessionExpired, .sessionExpired):
            break // Match
        default:
            XCTFail(
                "AuthError case mismatch: expected \(expectedCase), got \(authError)",
                file: file,
                line: line
            )
        }
    }
}
