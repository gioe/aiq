import Combine
import XCTest

@testable import AIQ

@MainActor
final class SettingsViewModelTests: XCTestCase {
    var sut: SettingsViewModel!
    var mockAuthManager: MockAuthManager!

    override func setUp() {
        super.setUp()
        mockAuthManager = MockAuthManager()
        sut = SettingsViewModel(authManager: mockAuthManager)
    }

    override func tearDown() {
        sut = nil
        mockAuthManager = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        XCTAssertNil(sut.currentUser, "currentUser should be nil initially when authManager has no user")
        XCTAssertFalse(sut.showLogoutConfirmation, "showLogoutConfirmation should be false initially")
        XCTAssertFalse(sut.showDeleteAccountConfirmation, "showDeleteAccountConfirmation should be false initially")
        XCTAssertNil(sut.deleteAccountError, "deleteAccountError should be nil initially")
        XCTAssertFalse(sut.isLoggingOut, "isLoggingOut should be false initially")
        XCTAssertFalse(sut.isDeletingAccount, "isDeletingAccount should be false initially")
        XCTAssertFalse(sut.showOnboarding, "showOnboarding should be false initially")
    }

    func testInitialState_WithAuthenticatedUser() {
        // Given - Set up authenticated user on mock
        let mockUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        mockAuthManager.currentUser = mockUser
        mockAuthManager.isAuthenticated = true

        // When - Create new ViewModel
        sut = SettingsViewModel(authManager: mockAuthManager)

        // Then
        XCTAssertNotNil(sut.currentUser, "currentUser should be set from authManager")
        XCTAssertEqual(sut.currentUser?.email, "test@example.com")
    }

    // MARK: - Dialog State Tests

    func testShowLogoutDialog() {
        // Given
        XCTAssertFalse(sut.showLogoutConfirmation)

        // When
        sut.showLogoutDialog()

        // Then
        XCTAssertTrue(sut.showLogoutConfirmation, "showLogoutConfirmation should be true after calling showLogoutDialog")
    }

    func testShowDeleteAccountDialog() {
        // Given
        XCTAssertFalse(sut.showDeleteAccountConfirmation)

        // When
        sut.showDeleteAccountDialog()

        // Then
        XCTAssertTrue(
            sut.showDeleteAccountConfirmation,
            "showDeleteAccountConfirmation should be true after calling showDeleteAccountDialog"
        )
    }

    func testShowOnboardingFlow() {
        // Given
        XCTAssertFalse(sut.showOnboarding)

        // When
        sut.showOnboardingFlow()

        // Then
        XCTAssertTrue(sut.showOnboarding, "showOnboarding should be true after calling showOnboardingFlow")
    }

    // MARK: - Logout Tests

    func testLogout_Success() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockAuthManager.currentUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )

        // When
        await sut.logout()

        // Then
        XCTAssertTrue(mockAuthManager.logoutCalled, "logout should be called on authManager")
        XCTAssertFalse(sut.isLoggingOut, "isLoggingOut should be false after logout completes")
    }

    func testLogout_SetsLoadingStateDuringOperation() async {
        // Given
        var loadingStates: [Bool] = []
        let cancellable = sut.$isLoggingOut
            .dropFirst() // Skip initial value
            .sink { loadingStates.append($0) }

        // When
        await sut.logout()

        // Then
        cancellable.cancel()
        XCTAssertTrue(loadingStates.contains(true), "isLoggingOut should be true during logout")
        XCTAssertFalse(sut.isLoggingOut, "isLoggingOut should be false after logout")
    }

    // MARK: - Delete Account Tests

    func testDeleteAccount_Success() async {
        // Given
        mockAuthManager.shouldSucceedDeleteAccount = true

        // When
        await sut.deleteAccount()

        // Then
        XCTAssertTrue(mockAuthManager.deleteAccountCalled, "deleteAccount should be called on authManager")
        XCTAssertFalse(sut.isDeletingAccount, "isDeletingAccount should be false after success")
        XCTAssertNil(sut.deleteAccountError, "deleteAccountError should be nil after success")
    }

    func testDeleteAccount_Failure() async {
        // Given
        mockAuthManager.shouldSucceedDeleteAccount = false

        // When
        await sut.deleteAccount()

        // Then
        XCTAssertTrue(mockAuthManager.deleteAccountCalled, "deleteAccount should be called on authManager")
        XCTAssertFalse(sut.isDeletingAccount, "isDeletingAccount should be false after failure")
        XCTAssertNotNil(sut.deleteAccountError, "deleteAccountError should be set after failure")
    }

    func testDeleteAccount_SetsLoadingStateDuringOperation() async {
        // Given
        mockAuthManager.shouldSucceedDeleteAccount = true
        mockAuthManager.deleteAccountDelay = 0.05

        var loadingStates: [Bool] = []
        let cancellable = sut.$isDeletingAccount
            .dropFirst() // Skip initial value
            .sink { loadingStates.append($0) }

        // When
        await sut.deleteAccount()

        // Then
        cancellable.cancel()
        XCTAssertTrue(loadingStates.contains(true), "isDeletingAccount should be true during operation")
        XCTAssertFalse(sut.isDeletingAccount, "isDeletingAccount should be false after completion")
    }

    // MARK: - Error Handling Tests

    func testClearDeleteAccountError() {
        // Given
        sut.deleteAccountError = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )
        XCTAssertNotNil(sut.deleteAccountError)

        // When
        sut.clearDeleteAccountError()

        // Then
        XCTAssertNil(sut.deleteAccountError, "deleteAccountError should be nil after clearing")
    }

    func testDeleteAccountError_IsIndependentFromBaseViewModelError() async {
        // This test documents the architectural decision that deleteAccountError
        // is intentionally separate from BaseViewModel.error because:
        // - Delete account requires a specific alert title ("Delete Account Failed")
        // - Delete account should not trigger retry logic
        // - AuthManager already records the error to Crashlytics

        // Given
        mockAuthManager.shouldSucceedDeleteAccount = false

        // When
        await sut.deleteAccount()

        // Then - deleteAccountError is set, but BaseViewModel.error remains nil
        XCTAssertNotNil(sut.deleteAccountError, "deleteAccountError should be set after failure")
        XCTAssertNil(sut.error, "BaseViewModel.error should remain nil (separate error channel)")
        XCTAssertFalse(sut.canRetry, "canRetry should be false (delete account is not retryable)")
    }

    // MARK: - User State Binding Tests

    func testCurrentUserUpdatesWhenAuthManagerChanges() async {
        // Given - Start with no user
        XCTAssertNil(sut.currentUser)

        // When - AuthManager authenticates
        let mockUser = User(
            id: 2,
            email: "updated@example.com",
            firstName: "Updated",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        mockAuthManager.currentUser = mockUser
        mockAuthManager.isAuthenticated = true

        // Give time for Combine to propagate
        try? await Task.sleep(nanoseconds: 10_000_000)

        // Then
        XCTAssertNotNil(sut.currentUser, "currentUser should update when authManager changes")
        XCTAssertEqual(sut.currentUser?.email, "updated@example.com")
    }

    // MARK: - Integration Tests

    func testCompleteLogoutFlow() async {
        // Given - Authenticated user
        mockAuthManager.isAuthenticated = true
        mockAuthManager.currentUser = User(
            id: 1,
            email: "test@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        sut = SettingsViewModel(authManager: mockAuthManager)

        // When - Show dialog then confirm logout
        sut.showLogoutDialog()
        XCTAssertTrue(sut.showLogoutConfirmation)

        await sut.logout()

        // Then
        XCTAssertTrue(mockAuthManager.logoutCalled)
        XCTAssertFalse(mockAuthManager.isAuthenticated)
    }

    func testCompleteDeleteAccountFlow_Success() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockAuthManager.shouldSucceedDeleteAccount = true

        // When - Show dialog then confirm delete
        sut.showDeleteAccountDialog()
        XCTAssertTrue(sut.showDeleteAccountConfirmation)

        await sut.deleteAccount()

        // Then
        XCTAssertTrue(mockAuthManager.deleteAccountCalled)
        XCTAssertNil(sut.deleteAccountError)
    }

    func testCompleteDeleteAccountFlow_Failure_WithRetry() async {
        // Given
        mockAuthManager.shouldSucceedDeleteAccount = false

        // When - First attempt fails
        await sut.deleteAccount()

        // Then
        XCTAssertNotNil(sut.deleteAccountError)

        // When - Clear error and retry with success
        sut.clearDeleteAccountError()
        mockAuthManager.shouldSucceedDeleteAccount = true
        mockAuthManager.deleteAccountCalled = false

        await sut.deleteAccount()

        // Then
        XCTAssertTrue(mockAuthManager.deleteAccountCalled)
        XCTAssertNil(sut.deleteAccountError)
    }
}
