import Combine
import XCTest

@testable import AIQ
import AIQAPIClient

final class AuthServiceTests: XCTestCase {
    var sut: AuthService!
    var mockService: MockOpenAPIService!
    var mockSecureStorage: MockSecureStorage!

    override func setUp() async throws {
        try await super.setUp()
        mockService = MockOpenAPIService()
        mockSecureStorage = MockSecureStorage()
        sut = AuthService(apiService: mockService, secureStorage: mockSecureStorage)
    }

    // MARK: - Initialization Tests

    func testInit_LoadsExistingTokenFromStorage() async throws {
        // Given
        let existingToken = "existing_access_token"
        let existingRefreshToken = "existing_refresh_token"
        try mockSecureStorage.save(existingToken, forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save(existingRefreshToken, forKey: SecureStorageKey.refreshToken.rawValue)

        // When
        let newSut = AuthService(apiService: mockService, secureStorage: mockSecureStorage)

        // Then
        let token = await newSut.getAccessToken()
        XCTAssertEqual(token, existingToken, "Should load existing token from storage on init")

        // Verify setTokens was called on API service during init
        let setTokensCalled = await mockService.setTokensCalled
        let lastAccessToken = await mockService.lastAccessToken
        let lastRefreshToken = await mockService.lastRefreshToken
        XCTAssertTrue(setTokensCalled, "setTokens should be called during init when tokens exist")
        XCTAssertEqual(lastAccessToken, existingToken, "API service should receive the existing access token")
        XCTAssertEqual(lastRefreshToken, existingRefreshToken, "API service should receive the existing refresh token")
    }

    func testInit_HandlesNoExistingToken() async throws {
        // Given - no token in storage

        // When
        let newSut = AuthService(apiService: mockService, secureStorage: mockSecureStorage)

        // Then
        let token = await newSut.getAccessToken()
        XCTAssertNil(token, "Should return nil when no token exists in storage")
    }

    func testInit_HandlesStorageErrorGracefully() async throws {
        // Given - Storage will throw on retrieve
        mockSecureStorage.setShouldThrowOnRetrieve(true)

        // When - Init should not crash even if storage throws
        let newSut = AuthService(apiService: mockService, secureStorage: mockSecureStorage)

        // Then - Should handle gracefully without crashing
        let token = await newSut.getAccessToken()
        XCTAssertNil(token, "Should return nil when storage throws error")

        // setTokens should NOT have been called (since no tokens were retrieved)
        let setTokensCalled = await mockService.setTokensCalled
        XCTAssertFalse(setTokensCalled, "setTokens should not be called when storage fails")
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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse

        // When
        let response = try await sut.login(email: email, password: password)

        // Then
        let loginCalled = await mockService.loginCalled
        let lastLoginEmail = await mockService.lastLoginEmail
        let lastLoginPassword = await mockService.lastLoginPassword

        XCTAssertTrue(loginCalled, "Login should be called")
        XCTAssertEqual(lastLoginEmail, email, "Should pass correct email")
        XCTAssertEqual(lastLoginPassword, password, "Should pass correct password")

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

        // Verify setTokens was called on API service
        let setTokensCalled = await mockService.setTokensCalled
        let lastAccessToken = await mockService.lastAccessToken
        let lastRefreshToken = await mockService.lastRefreshToken
        XCTAssertTrue(setTokensCalled, "setTokens should be called after login")
        XCTAssertEqual(lastAccessToken, "access_token_123", "API service should receive the new access token")
        XCTAssertEqual(lastRefreshToken, "refresh_token_456", "API service should receive the new refresh token")
    }

    func testLogin_NetworkError() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Network error"])
        )

        await mockService.loginError = networkError

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

        await mockService.loginError = unauthorizedError

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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse
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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse

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
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError, got \(type(of: error))")

            // Verify rollback behavior: access token should be removed (rolled back)
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertNil(
                savedAccessToken,
                "Access token should be rolled back when refresh token save fails"
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

            // BTS-229: Verify API service state after partial save failure
            // EXPECTED BEHAVIOR: setTokens() should NOT be called at all when storage fails
            // The implementation correctly defers apiService.setTokens() until after all saves succeed
            // This maintains atomicity between storage and apiService state
            let setTokensCalled = await mockService.setTokensCalled
            XCTAssertFalse(
                setTokensCalled,
                "API service setTokens should not be called when storage save fails"
            )

            // Verify currentUser was NOT set
            let currentUser = await sut.currentUser
            XCTAssertNil(currentUser, "Current user should not be set when storage save fails")
        }
    }

    func testLogin_PartialStorageSave_WithExistingAuth_RollsBackToOldToken() async throws {
        // Given - User already has valid auth from a previous login
        try mockSecureStorage.save("old_access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("old_refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        // Reset mock to track new calls
        await mockService.reset()

        let email = "test@example.com"
        let password = "password123"
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse

        // Configure storage to fail on refresh token save (after access token succeeds)
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

            // BTS-229: Verify storage is rolled back to OLD state
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "old_access_token",
                "Access token should be rolled back to old value when partial save fails"
            )

            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertEqual(
                savedRefreshToken,
                "old_refresh_token",
                "Refresh token should remain as old value when save fails"
            )

            // BTS-229: Verify apiService.setTokens() was NOT called with new tokens
            // CRITICAL: apiService should still have old tokens, not new tokens
            // The implementation correctly does NOT call setTokens on partial failure
            let setTokensCalled = await mockService.setTokensCalled
            XCTAssertFalse(
                setTokensCalled,
                "API service setTokens should not be called when storage rollback occurs"
            )

            // Note: In a real scenario, apiService would still have "old_access_token" and "old_refresh_token"
            // This test verifies that we don't UPDATE it with the new tokens
            // The lack of setTokens calls means apiService state is preserved
        }
    }

    func testLogin_PartialStorageSave_RefreshTokenSucceeds_UserIdFails() async throws {
        // Given
        let email = "test@example.com"
        let password = "password123"
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token_123",
            refreshToken: "refresh_token_456",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse

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
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError, got \(type(of: error))")

            // Verify rollback behavior: both tokens should be rolled back
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertNil(
                savedAccessToken,
                "Access token should be rolled back when userId save fails"
            )

            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertNil(
                savedRefreshToken,
                "Refresh token should be rolled back when userId save fails"
            )

            // Verify userId was NOT saved (threw error)
            let savedUserId = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.userId.rawValue
            )
            XCTAssertNil(
                savedUserId,
                "User ID should not be saved when save fails"
            )

            // BTS-229: Verify API service state
            let setTokensCalled = await mockService.setTokensCalled
            XCTAssertFalse(
                setTokensCalled,
                "API service setTokens should not be called when storage save fails"
            )

            // Verify currentUser was NOT set
            let currentUser = await sut.currentUser
            XCTAssertNil(currentUser, "Current user should not be set when storage save fails")
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

        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: firstName,
            id: 2,
            lastName: lastName,
            notificationEnabled: false
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.registerResponse = mockAuthResponse

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
        let registerCalled = await mockService.registerCalled
        let lastRegisterEmail = await mockService.lastRegisterEmail
        let lastRegisterPassword = await mockService.lastRegisterPassword
        let lastRegisterFirstName = await mockService.lastRegisterFirstName
        let lastRegisterLastName = await mockService.lastRegisterLastName

        XCTAssertTrue(registerCalled, "Register should be called")
        XCTAssertEqual(lastRegisterEmail, email, "Should pass correct email")
        XCTAssertEqual(lastRegisterPassword, password, "Should pass correct password")
        XCTAssertEqual(lastRegisterFirstName, firstName, "Should pass correct first name")
        XCTAssertEqual(lastRegisterLastName, lastName, "Should pass correct last name")

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
        // Note: birthYear and educationLevel are not available in the generated UserResponse type

        // Verify setTokens was called on API service
        let setTokensCalled = await mockService.setTokensCalled
        let lastAccessToken = await mockService.lastAccessToken
        let lastRefreshToken = await mockService.lastRefreshToken
        XCTAssertTrue(setTokensCalled, "setTokens should be called after registration")
        XCTAssertEqual(lastAccessToken, "new_access_token", "API service should receive the new access token")
        XCTAssertEqual(lastRefreshToken, "new_refresh_token", "API service should receive the new refresh token")
    }

    func testRegister_Success_WithMinimalFields() async throws {
        // Given
        let email = "minimal@example.com"
        let password = "password123"
        let firstName = "Min"
        let lastName = "User"

        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: firstName,
            id: 3,
            lastName: lastName,
            notificationEnabled: false
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "minimal_access_token",
            refreshToken: "minimal_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.registerResponse = mockAuthResponse

        // When
        let response = try await sut.register(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName
        )

        // Then
        let registerCalled = await mockService.registerCalled
        XCTAssertTrue(registerCalled, "Register should be called")

        XCTAssertEqual(response.accessToken, "minimal_access_token")
        XCTAssertEqual(response.user.id, 3)
        // Note: birthYear and educationLevel are not available in the generated UserResponse type
    }

    func testRegister_DuplicateEmail_Error() async throws {
        // Given
        let email = "existing@example.com"
        let password = "password123"
        let firstName = "Test"
        let lastName = "User"
        let conflictError = APIError.unprocessableEntity(message: "Email already exists")

        await mockService.registerError = conflictError

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

        await mockService.registerError = validationError

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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: firstName,
            id: 2,
            lastName: lastName,
            notificationEnabled: false
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.registerResponse = mockAuthResponse

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
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError, got \(type(of: error))")

            // Verify rollback behavior: access token should be removed (rolled back)
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertNil(
                savedAccessToken,
                "Access token should be rolled back when refresh token save fails"
            )

            // Verify refresh token was NOT saved (threw error)
            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertNil(
                savedRefreshToken,
                "Refresh token should not be saved when save fails"
            )

            // BTS-229: Verify API service state after partial save failure
            let setTokensCalled = await mockService.setTokensCalled
            XCTAssertFalse(
                setTokensCalled,
                "API service setTokens should not be called when storage save fails"
            )

            // Verify currentUser was NOT set
            let currentUser = await sut.currentUser
            XCTAssertNil(currentUser, "Current user should not be set when storage save fails")
        }
    }

    func testRegister_PartialStorageSave_RefreshTokenSucceeds_UserIdFails() async throws {
        // Given
        let email = "newuser@example.com"
        let password = "password123"
        let firstName = "New"
        let lastName = "User"
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: firstName,
            id: 2,
            lastName: lastName,
            notificationEnabled: false
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.registerResponse = mockAuthResponse

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
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError, got \(type(of: error))")

            // Verify rollback behavior: both tokens should be rolled back
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertNil(
                savedAccessToken,
                "Access token should be rolled back when userId save fails"
            )

            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertNil(
                savedRefreshToken,
                "Refresh token should be rolled back when userId save fails"
            )

            // BTS-229: Verify API service state after partial save failure
            let setTokensCalled = await mockService.setTokensCalled
            XCTAssertFalse(
                setTokensCalled,
                "API service setTokens should not be called when storage save fails"
            )

            // Verify currentUser was NOT set
            let currentUser = await sut.currentUser
            XCTAssertNil(currentUser, "Current user should not be set when storage save fails")
        }
    }

    // MARK: - Logout Tests

    func testLogout_Success() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        // When
        try await sut.logout()

        // Then
        let logoutCalled = await mockService.logoutCalled
        XCTAssertTrue(logoutCalled, "Logout should be called")

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

        // Verify clearTokens was called on API service
        let clearTokensCalled = await mockService.clearTokensCalled
        XCTAssertTrue(clearTokensCalled, "clearTokens should be called after logout")
    }

    func testLogout_APIError_StillClearsLocalData() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        // Mock API error (e.g., network error)
        let networkError = APIError.networkError(
            NSError(domain: "Test", code: -1, userInfo: nil)
        )
        await mockService.logoutError = networkError

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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token",
            refreshToken: "refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )
        await mockService.loginResponse = mockAuthResponse
        _ = try await sut.login(email: "test@example.com", password: "password")

        // Verify user is set
        var currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser, "User should be set after login")

        // Now configure storage to fail on deleteAll
        mockSecureStorage.setShouldThrowOnDeleteAll(true)
        await mockService.reset()

        // When - Logout should handle storage error gracefully
        try await sut.logout()

        // Then - In-memory state should still be cleared
        currentUser = await sut.currentUser
        XCTAssertNil(currentUser, "Current user should be cleared even if storage deleteAll fails")

        // Verify clearTokens was still called
        let clearTokensCalled = await mockService.clearTokensCalled
        XCTAssertTrue(clearTokensCalled, "clearTokens should be called even if storage fails")
    }

    // MARK: - Token Refresh Tests

    func testRefreshToken_Success() async throws {
        // Given
        let oldRefreshToken = "old_refresh_token"
        try mockSecureStorage.save("old_access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save(oldRefreshToken, forKey: SecureStorageKey.refreshToken.rawValue)

        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.refreshTokenResponse = mockAuthResponse

        // When
        let response = try await sut.refreshToken()

        // Then
        let refreshTokenCalled = await mockService.refreshTokenCalled
        XCTAssertTrue(refreshTokenCalled, "RefreshToken should be called")

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

        // Verify setTokens was called on API service
        let setTokensCalled = await mockService.setTokensCalled
        let lastAccessToken = await mockService.lastAccessToken
        let lastRefreshToken = await mockService.lastRefreshToken
        XCTAssertTrue(setTokensCalled, "setTokens should be called after token refresh")
        XCTAssertEqual(lastAccessToken, "new_access_token", "API service should receive the new access token")
        XCTAssertEqual(lastRefreshToken, "new_refresh_token", "API service should receive the new refresh token")
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
        let refreshTokenCalled = await mockService.refreshTokenCalled
        XCTAssertFalse(refreshTokenCalled, "API should not be called when no refresh token")
    }

    func testRefreshToken_ExpiredRefreshToken_Error() async throws {
        // Given
        try mockSecureStorage.save("expired_refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        let unauthorizedError = APIError.unauthorized(message: "Refresh token expired")
        await mockService.refreshTokenError = unauthorizedError

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
        await mockService.refreshTokenError = networkError

        // When/Then - Using stronger error assertion (Critical Issue #3)
        do {
            _ = try await sut.refreshToken()
            XCTFail("Should throw network error")
        } catch {
            assertAPIError(error, is: networkError)
        }
    }

    func testRefreshToken_PartialStorageSave_AccessTokenSucceeds_RefreshTokenFails() async throws {
        // Given - Setup existing auth state
        try mockSecureStorage.save("old_access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("old_refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "refreshed_access_token",
            refreshToken: "refreshed_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.refreshTokenResponse = mockAuthResponse

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
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError, got \(type(of: error))")

            // Verify rollback behavior: access token should be restored to old value
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "old_access_token",
                "Access token should be rolled back to old value when refresh token save fails"
            )

            // Verify refresh token remains unchanged (save failed, so rollback kept it)
            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertEqual(
                savedRefreshToken,
                "old_refresh_token",
                "Refresh token should remain as old value when save fails"
            )

            // Verify userId remains unchanged
            let savedUserId = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.userId.rawValue
            )
            XCTAssertEqual(
                savedUserId,
                "1",
                "User ID should remain unchanged when refresh token save fails"
            )

            // BTS-229: Verify API service state
            // CRITICAL: When rollback occurs, apiService should preserve old tokens (not update to new tokens)
            let setTokensCalled = await mockService.setTokensCalled
            XCTAssertFalse(
                setTokensCalled,
                "API service setTokens should not be called when storage rollback occurs"
            )

            // Verify currentUser was NOT updated
            let currentUser = await sut.currentUser
            XCTAssertNil(currentUser, "Current user should not be updated when storage save fails")
        }
    }

    func testRefreshToken_PartialStorageSave_RefreshTokenSucceeds_UserIdFails() async throws {
        // Given - Setup existing auth state
        try mockSecureStorage.save("old_access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("old_refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "refreshed_access_token",
            refreshToken: "refreshed_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.refreshTokenResponse = mockAuthResponse

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
            XCTAssertTrue(error is MockSecureStorageError, "Should throw MockSecureStorageError, got \(type(of: error))")

            // Verify rollback behavior: both tokens should be restored to old values
            let savedAccessToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.accessToken.rawValue
            )
            XCTAssertEqual(
                savedAccessToken,
                "old_access_token",
                "Access token should be rolled back to old value when userId save fails"
            )

            let savedRefreshToken = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.refreshToken.rawValue
            )
            XCTAssertEqual(
                savedRefreshToken,
                "old_refresh_token",
                "Refresh token should be rolled back to old value when userId save fails"
            )

            // Verify userId remains unchanged
            let savedUserId = try? mockSecureStorage.retrieve(
                forKey: SecureStorageKey.userId.rawValue
            )
            XCTAssertEqual(
                savedUserId,
                "1",
                "User ID should remain unchanged when save fails"
            )

            // BTS-229: Verify API service state
            let setTokensCalled = await mockService.setTokensCalled
            XCTAssertFalse(
                setTokensCalled,
                "API service setTokens should not be called when storage rollback occurs"
            )

            // Verify currentUser was NOT updated
            let currentUser = await sut.currentUser
            XCTAssertNil(currentUser, "Current user should not be updated when storage save fails")
        }
    }

    // MARK: - Delete Account Tests

    func testDeleteAccount_Success() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        // When
        try await sut.deleteAccount()

        // Then
        let deleteAccountCalled = await mockService.deleteAccountCalled
        XCTAssertTrue(deleteAccountCalled, "DeleteAccount should be called")

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

    func testDeleteAccount_204NoContent_ClearsLocalData() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        // OpenAPIService now handles 204 properly, so no error needed - just succeeds

        // When - Should succeed (204 No Content is handled by OpenAPIService)
        try await sut.deleteAccount()

        // Then - Local data should be cleared
        let accessToken = try mockSecureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
        let refreshToken = try mockSecureStorage.retrieve(forKey: SecureStorageKey.refreshToken.rawValue)

        XCTAssertNil(accessToken, "Access token should be cleared on 204 No Content")
        XCTAssertNil(refreshToken, "Refresh token should be cleared on 204 No Content")

        let isAuthenticated = await sut.isAuthenticated
        XCTAssertFalse(isAuthenticated, "Should not be authenticated after account deletion")
    }

    func testDeleteAccount_APIError_ThrowsAndPreservesLocalData() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)
        try mockSecureStorage.save("1", forKey: SecureStorageKey.userId.rawValue)

        // Mock API error
        let serverError = APIError.serverError(statusCode: 500, message: "Server error")
        await mockService.deleteAccountError = serverError

        // When/Then - Delete account should throw error when API fails
        do {
            try await sut.deleteAccount()
            XCTFail("Should throw error when delete account API fails")
        } catch {
            // Verify it's the correct error type (wrapped in AuthError.accountDeletionFailed)
            guard case let AuthError.accountDeletionFailed(underlyingError) = error else {
                XCTFail("Expected AuthError.accountDeletionFailed, got \(error)")
                return
            }

            // Verify underlying error is the API error
            XCTAssertTrue(underlyingError is APIError, "Underlying error should be APIError")
        }

        // Local data should NOT be cleared when API call fails (GDPR compliance - don't mislead user)
        let accessToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.accessToken.rawValue
        )
        let refreshToken = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.refreshToken.rawValue
        )
        let userId = try mockSecureStorage.retrieve(
            forKey: SecureStorageKey.userId.rawValue
        )

        XCTAssertEqual(accessToken, "access_token", "Access token should be preserved when API fails")
        XCTAssertEqual(refreshToken, "refresh_token", "Refresh token should be preserved when API fails")
        XCTAssertEqual(userId, "1", "User ID should be preserved when API fails")

        let isAuthenticated = await sut.isAuthenticated
        XCTAssertTrue(isAuthenticated, "Should still be authenticated when delete account API fails")
    }

    func testDeleteAccount_NetworkError_ThrowsAccountDeletionFailed() async throws {
        // Given - Setup authenticated state
        try mockSecureStorage.save("access_token", forKey: SecureStorageKey.accessToken.rawValue)
        try mockSecureStorage.save("refresh_token", forKey: SecureStorageKey.refreshToken.rawValue)

        // Mock network error
        let networkError = APIError.networkError(
            NSError(domain: NSURLErrorDomain, code: NSURLErrorNotConnectedToInternet, userInfo: nil)
        )
        await mockService.deleteAccountError = networkError

        // When/Then - Delete account should throw error when network fails
        do {
            try await sut.deleteAccount()
            XCTFail("Should throw error when network fails")
        } catch {
            // Verify it's the correct error type
            guard case let AuthError.accountDeletionFailed(underlyingError) = error else {
                XCTFail("Expected AuthError.accountDeletionFailed, got \(error)")
                return
            }

            // Verify underlying error is the network error
            XCTAssertTrue(underlyingError is APIError, "Underlying error should be APIError")
        }

        // User should remain authenticated - they need to know deletion didn't happen
        let isAuthenticated = await sut.isAuthenticated
        XCTAssertTrue(isAuthenticated, "Should still be authenticated when network fails during delete")
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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: email,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token",
            refreshToken: "refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse

        // When
        _ = try await sut.login(email: email, password: password)

        // Then
        let currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser)
        XCTAssertEqual(currentUser?.id, 1)
        XCTAssertEqual(currentUser?.email, email)
        XCTAssertEqual(currentUser?.firstName, "Test")
        XCTAssertEqual(currentUser?.lastName, "User")
    }

    func testCurrentUser_ClearedAfterLogout() async throws {
        // Given - Setup authenticated state with user
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "access_token",
            refreshToken: "refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse
        _ = try await sut.login(email: "test@example.com", password: "password")

        // Verify user is set
        var currentUser = await sut.currentUser
        XCTAssertNotNil(currentUser)

        // When
        try await sut.logout()

        // Then
        currentUser = await sut.currentUser
        XCTAssertNil(currentUser, "Current user should be cleared after logout")
    }

    // MARK: - Edge Cases

    func testMultipleSuccessiveLogins_OverwritesTokens() async throws {
        // Given
        let firstUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "first@example.com",
            firstName: "First",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let firstResponse = AuthResponse(
            accessToken: "first_access_token",
            refreshToken: "first_refresh_token",
            tokenType: "Bearer",
            user: firstUser
        )

        let secondUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "second@example.com",
            firstName: "Second",
            id: 2,
            lastName: "User",
            notificationEnabled: true
        )
        let secondResponse = AuthResponse(
            accessToken: "second_access_token",
            refreshToken: "second_refresh_token",
            tokenType: "Bearer",
            user: secondUser
        )

        await mockService.loginResponse = firstResponse

        // When - First login
        _ = try await sut.login(email: "first@example.com", password: "password1")

        var currentUser = await sut.currentUser
        XCTAssertEqual(currentUser?.id, 1)

        // When - Second login (different user)
        await mockService.reset()
        await mockService.loginResponse = secondResponse
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

        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "new_access_token",
            refreshToken: "new_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.refreshTokenResponse = mockAuthResponse

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
            user: Components.Schemas.UserResponse(
                createdAt: Date(),
                email: "",
                firstName: "Test",
                id: 1,
                lastName: "User",
                notificationEnabled: true
            )
        )

        await mockService.loginResponse = mockAuthResponse

        // When
        _ = try await sut.login(email: "", password: "")

        // Then
        let loginCalled = await mockService.loginCalled
        XCTAssertTrue(loginCalled, "Should call API even with empty strings")
    }

    func testConcurrentLogin_ThreadSafety() async throws {
        // Given - Multiple concurrent login attempts (Critical Issue #4)
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "concurrent_access_token",
            refreshToken: "concurrent_refresh_token",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.loginResponse = mockAuthResponse

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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "newuser@example.com",
            firstName: "New",
            id: 1,
            lastName: "User",
            notificationEnabled: false
        )
        let mockAuthResponse = AuthResponse(
            accessToken: "concurrent_register_token",
            refreshToken: "concurrent_register_refresh",
            tokenType: "Bearer",
            user: mockUser
        )

        await mockService.registerResponse = mockAuthResponse

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
        case (.accountDeletionFailed, .accountDeletionFailed):
            break // Match (underlying errors may differ)
        default:
            XCTFail(
                "AuthError case mismatch: expected \(expectedCase), got \(authError)",
                file: file,
                line: line
            )
        }
    }
}
