import Combine
import XCTest

@testable import AIQ

@MainActor
final class AuthManagerDeleteAccountTests: XCTestCase {
    var sut: AuthManager!
    fileprivate var mockAuthService: MockAuthService!

    override func setUp() async throws {
        try await super.setUp()
        mockAuthService = MockAuthService()
    }

    override func tearDown() {
        sut = nil
        mockAuthService = nil
        super.tearDown()
    }

    // MARK: - Delete Account Tests

    func testDeleteAccount_Success() async throws {
        // Given - user is authenticated (set mock state before creating AuthManager)
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
        mockAuthService.isAuthenticated = true
        mockAuthService.currentUser = mockUser
        mockAuthService.shouldSucceedDeleteAccount = true
        sut = AuthManager(authService: mockAuthService)

        // When
        try await sut.deleteAccount()

        // Then
        XCTAssertTrue(mockAuthService.deleteAccountCalled, "deleteAccount should be called on auth service")
        XCTAssertFalse(sut.isAuthenticated, "user should not be authenticated after deleting account")
        XCTAssertNil(sut.currentUser, "current user should be nil after deleting account")
        XCTAssertFalse(sut.isLoading, "should not be loading after completion")
        XCTAssertNil(sut.authError, "should not have error on success")
    }

    func testDeleteAccount_Failure() async throws {
        // Given - set mock state before creating AuthManager
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
        mockAuthService.isAuthenticated = true
        mockAuthService.currentUser = mockUser
        mockAuthService.shouldSucceedDeleteAccount = false
        sut = AuthManager(authService: mockAuthService)

        // When
        do {
            try await sut.deleteAccount()
            XCTFail("Should throw error")
        } catch {
            // Then
            XCTAssertTrue(mockAuthService.deleteAccountCalled, "deleteAccount should be called on auth service")
            XCTAssertNotNil(sut.authError, "should have error on failure")
            XCTAssertFalse(sut.isLoading, "should not be loading after error")
            // User should still be authenticated on failure
            XCTAssertTrue(sut.isAuthenticated, "user should still be authenticated on delete failure")
            XCTAssertNotNil(sut.currentUser, "current user should not be nil on delete failure")
        }
    }

    func testDeleteAccount_SetsLoadingState() async throws {
        // Given
        mockAuthService.shouldSucceedDeleteAccount = true
        mockAuthService.deleteAccountDelay = 0.1
        sut = AuthManager(authService: mockAuthService)

        // When
        let expectation = expectation(description: "Loading state should be set")
        var loadingStateObserved = false

        let cancellable = sut.$isLoading.sink { isLoading in
            if isLoading {
                loadingStateObserved = true
                expectation.fulfill()
            }
        }

        Task {
            try? await sut.deleteAccount()
        }

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertTrue(loadingStateObserved, "loading state should be set during delete account")
        cancellable.cancel()
    }

    func testDeleteAccount_CompletesSuccessfully() async throws {
        // Given
        mockAuthService.shouldSucceedDeleteAccount = true
        sut = AuthManager(authService: mockAuthService)

        // When
        try await sut.deleteAccount()

        // Then
        XCTAssertTrue(mockAuthService.deleteAccountCalled, "deleteAccount should complete")
        XCTAssertFalse(sut.isAuthenticated, "user should not be authenticated")
    }
}

// MARK: - Mock Auth Service

private class MockAuthService: AuthServiceProtocol {
    var shouldSucceedDeleteAccount = true
    var deleteAccountDelay: TimeInterval = 0
    var deleteAccountCalled = false

    var isAuthenticated: Bool = false
    var currentUser: User?

    func register(
        email _: String,
        password _: String,
        firstName _: String,
        lastName _: String,
        birthYear _: Int?,
        educationLevel _: EducationLevel?,
        country _: String?,
        region _: String?
    ) async throws -> AuthResponse {
        fatalError("Not implemented for this test")
    }

    func login(email _: String, password _: String) async throws -> AuthResponse {
        fatalError("Not implemented for this test")
    }

    func refreshToken() async throws -> AuthResponse {
        fatalError("Not implemented for this test")
    }

    func logout() async throws {
        // No-op for this test
    }

    func deleteAccount() async throws {
        deleteAccountCalled = true

        if deleteAccountDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(deleteAccountDelay * 1_000_000_000))
        }

        if !shouldSucceedDeleteAccount {
            throw NSError(
                domain: "MockAuthService",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Failed to delete account"]
            )
        }
    }

    func getAccessToken() -> String? {
        nil
    }
}
