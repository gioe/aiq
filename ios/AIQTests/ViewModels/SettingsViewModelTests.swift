@testable import AIQ
import AIQAPIClient
import Combine
import XCTest

@MainActor
final class SettingsViewModelTests: XCTestCase {
    var sut: SettingsViewModel!
    var mockAuthManager: MockAuthManager!
    var mockBiometricAuthManager: MockBiometricAuthManager!
    var mockBiometricPreferenceStorage: MockBiometricPreferenceStorage!

    override func setUp() {
        super.setUp()
        mockAuthManager = MockAuthManager()
        mockBiometricAuthManager = MockBiometricAuthManager()
        mockBiometricPreferenceStorage = MockBiometricPreferenceStorage()
        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage
        )
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
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: false
        )
        mockAuthManager.currentUser = mockUser
        mockAuthManager.isAuthenticated = true

        // When - Create new ViewModel
        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage
        )

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

    func testLogout_IsNonThrowing_ByDesign() async {
        // This test documents the architectural decision that logout() does not require error handling.
        //
        // The AuthManagerProtocol.logout() method is intentionally non-throwing because:
        // - Users should always be able to sign out, even if the server is unreachable
        // - AuthManager catches any network errors internally and silently continues
        // - Local state (tokens, user data) is always cleared regardless of server response
        // - This differs from deleteAccount(), which must report failures to the user
        //
        // Contrast with deleteAccount():
        // - deleteAccount() is throwing because the server must confirm deletion
        // - If server deletion fails, the account still exists and user must be informed
        // - Retrying may be necessary, so errors must surface to the UI

        // Given - We can call logout without any error handling infrastructure
        // (no try/catch, no error property to check, no failure callback)

        // When
        await sut.logout()

        // Then - Logout always "succeeds" from the ViewModel's perspective
        XCTAssertTrue(mockAuthManager.logoutCalled, "logout should be called on authManager")
        XCTAssertFalse(sut.isLoggingOut, "isLoggingOut should be false after completion")
        // Note: There is no sut.logoutError property because logout cannot fail at the API level
    }

    func testLogout_Success() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockAuthManager.currentUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: false
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
        // - The error is recorded to Crashlytics via errorRecorder

        // Given
        mockAuthManager.shouldSucceedDeleteAccount = false

        // When
        await sut.deleteAccount()

        // Then - deleteAccountError is set, but BaseViewModel.error remains nil
        XCTAssertNotNil(sut.deleteAccountError, "deleteAccountError should be set after failure")
        XCTAssertNil(sut.error, "BaseViewModel.error should remain nil (separate error channel)")
        XCTAssertFalse(sut.canRetry, "canRetry should be false (delete account is not retryable)")
    }

    // MARK: - Crashlytics Error Recording Tests

    func testDeleteAccount_Failure_RecordsErrorToCrashlytics() async {
        // Given - Set up to capture error recording calls
        var recordedError: Error?
        var recordedContext: CrashlyticsErrorRecorder.ErrorContext?

        let mockErrorRecorder: SettingsViewModel.ErrorRecorder = { error, context in
            recordedError = error
            recordedContext = context
        }

        // Create ViewModel with mock error recorder
        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage,
            errorRecorder: mockErrorRecorder
        )
        mockAuthManager.shouldSucceedDeleteAccount = false

        // When
        await sut.deleteAccount()

        // Then - Verify error was recorded with correct context
        XCTAssertNotNil(recordedError, "Error should be recorded to Crashlytics on delete failure")
        XCTAssertEqual(
            recordedContext,
            .deleteAccount,
            "Error should be recorded with .deleteAccount context"
        )
    }

    func testDeleteAccount_Success_DoesNotRecordError() async {
        // Given - Set up to capture error recording calls
        var errorRecorded = false

        let mockErrorRecorder: SettingsViewModel.ErrorRecorder = { _, _ in
            errorRecorded = true
        }

        // Create ViewModel with mock error recorder
        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage,
            errorRecorder: mockErrorRecorder
        )
        mockAuthManager.shouldSucceedDeleteAccount = true

        // When
        await sut.deleteAccount()

        // Then - No error should be recorded on success
        XCTAssertFalse(errorRecorded, "No error should be recorded when delete succeeds")
    }

    func testDeleteAccount_Failure_RecordsCorrectErrorType() async {
        // Given - Set up to capture the actual error recorded
        var recordedError: Error?

        let mockErrorRecorder: SettingsViewModel.ErrorRecorder = { error, _ in
            recordedError = error
        }

        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage,
            errorRecorder: mockErrorRecorder
        )
        mockAuthManager.shouldSucceedDeleteAccount = false

        // When
        await sut.deleteAccount()

        // Then - The recorded error should match deleteAccountError
        XCTAssertNotNil(recordedError)
        XCTAssertEqual(
            (recordedError as NSError?)?.domain,
            (sut.deleteAccountError as NSError?)?.domain,
            "Recorded error should match deleteAccountError"
        )
        XCTAssertEqual(
            (recordedError as NSError?)?.code,
            (sut.deleteAccountError as NSError?)?.code,
            "Recorded error code should match deleteAccountError code"
        )
    }

    // MARK: - User State Binding Tests

    func testCurrentUserUpdatesWhenAuthManagerChanges() async {
        // Given - Start with no user
        XCTAssertNil(sut.currentUser)

        // When - AuthManager authenticates
        let mockUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "updated@example.com",
            firstName: "Updated",
            id: 2,
            lastName: "User",
            notificationEnabled: false
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
        mockAuthManager.currentUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: false
        )
        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage
        )

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

    // MARK: - Concurrent Operation Tests

    func testLogout_IgnoresSecondCallWhileInProgress() async {
        // Given - Configure mock to have a delay so we can test concurrent calls
        mockAuthManager.logoutDelay = 0.1

        // When - Start first logout
        async let firstLogout: Void = sut.logout()

        // Give time for first call to set isLoggingOut
        try? await Task.sleep(nanoseconds: 10_000_000)

        // Verify first call is in progress
        XCTAssertTrue(sut.isLoggingOut, "First logout should be in progress")

        // Reset the flag to verify second call doesn't trigger logout
        mockAuthManager.logoutCalled = false

        // When - Start second logout while first is still in progress
        async let secondLogout: Void = sut.logout()

        // Then - Second call should return immediately without calling authManager
        await secondLogout
        XCTAssertFalse(
            mockAuthManager.logoutCalled,
            "Second logout should be ignored while first is in progress"
        )

        // Wait for first logout to complete
        await firstLogout
        XCTAssertFalse(sut.isLoggingOut, "isLoggingOut should be false after completion")
    }

    func testDeleteAccount_IgnoresSecondCallWhileInProgress() async {
        // Given - Configure mock to have a delay so we can test concurrent calls
        mockAuthManager.shouldSucceedDeleteAccount = true
        mockAuthManager.deleteAccountDelay = 0.1

        // When - Start first delete
        async let firstDelete: Void = sut.deleteAccount()

        // Give time for first call to set isDeletingAccount
        try? await Task.sleep(nanoseconds: 10_000_000)

        // Verify first call is in progress
        XCTAssertTrue(sut.isDeletingAccount, "First deleteAccount should be in progress")

        // Reset the flag to verify second call doesn't trigger deleteAccount
        mockAuthManager.deleteAccountCalled = false

        // When - Start second delete while first is still in progress
        async let secondDelete: Void = sut.deleteAccount()

        // Then - Second call should return immediately without calling authManager
        await secondDelete
        XCTAssertFalse(
            mockAuthManager.deleteAccountCalled,
            "Second deleteAccount should be ignored while first is in progress"
        )

        // Wait for first delete to complete
        await firstDelete
        XCTAssertFalse(sut.isDeletingAccount, "isDeletingAccount should be false after completion")
    }

    // MARK: - Biometric Toggle Tests

    func testInitialState_LoadsBiometricPreference() {
        // Given
        mockBiometricPreferenceStorage.isBiometricEnabled = true

        // When
        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage
        )

        // Then
        XCTAssertTrue(sut.isBiometricEnabled, "isBiometricEnabled should reflect stored preference on init")
    }

    func testToggleBiometric_EnablesBiometric() {
        // Given
        XCTAssertFalse(sut.isBiometricEnabled)

        // When
        sut.toggleBiometric()

        // Then
        XCTAssertTrue(sut.isBiometricEnabled, "isBiometricEnabled should be true after toggle")
        XCTAssertTrue(mockBiometricPreferenceStorage.isBiometricEnabled, "Storage should be updated")
    }

    func testToggleBiometric_DisablesBiometric() {
        // Given
        mockBiometricPreferenceStorage.isBiometricEnabled = true
        sut = SettingsViewModel(
            authManager: mockAuthManager,
            biometricAuthManager: mockBiometricAuthManager,
            biometricPreferenceStorage: mockBiometricPreferenceStorage
        )
        XCTAssertTrue(sut.isBiometricEnabled)

        // When
        sut.toggleBiometric()

        // Then
        XCTAssertFalse(sut.isBiometricEnabled, "isBiometricEnabled should be false after second toggle")
        XCTAssertFalse(mockBiometricPreferenceStorage.isBiometricEnabled, "Storage should be updated")
    }

    func testIsBiometricAvailable_ReflectsBiometricManager() {
        // Given
        mockBiometricAuthManager.mockIsBiometricAvailable = true

        // Then
        XCTAssertTrue(sut.isBiometricAvailable, "isBiometricAvailable should reflect biometricAuthManager")
    }

    func testBiometricType_ReflectsBiometricManager() {
        // Given
        mockBiometricAuthManager.mockBiometricType = .faceID

        // Then
        XCTAssertEqual(sut.biometricType, .faceID, "biometricType should reflect biometricAuthManager")
    }
}
