@testable import AIQ
import UserNotifications
import XCTest

@MainActor
final class NotificationSettingsViewModelTests: XCTestCase {
    var sut: NotificationSettingsViewModel!
    var mockNotificationService: MockNotificationService!
    var mockNotificationManager: MockNotificationManager!

    override func setUp() async throws {
        try await super.setUp()
        mockNotificationService = MockNotificationService()
        mockNotificationManager = MockNotificationManager()
        sut = NotificationSettingsViewModel(
            notificationService: mockNotificationService,
            notificationManager: mockNotificationManager
        )
    }

    // MARK: - Initialization Tests

    func testInit_SetsDefaultValues() {
        // Then
        XCTAssertFalse(sut.areNotificationsEnabled)
        XCTAssertFalse(sut.systemPermissionGranted)
        XCTAssertFalse(sut.isCheckingPermission)
        XCTAssertFalse(sut.isLoading)
        XCTAssertNil(sut.error)
    }

    // MARK: - Load Notification Preferences Tests

    func testLoadNotificationPreferences_Success_UpdatesState() async {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Success"
        )
        await mockNotificationService.setGetPreferencesResponse(mockResponse)

        // When
        await sut.loadNotificationPreferences()

        // Then
        let serviceCallCount = await mockNotificationService.getPreferencesCallCount
        XCTAssertEqual(serviceCallCount, 1)
        XCTAssertTrue(sut.areNotificationsEnabled)
        XCTAssertFalse(sut.isLoading)
        XCTAssertNil(sut.error)
    }

    func testLoadNotificationPreferences_Failure_SetsError() async {
        // Given
        let expectedError = APIError.networkError(URLError(.notConnectedToInternet))
        await mockNotificationService.setGetPreferencesError(expectedError)

        // When
        await sut.loadNotificationPreferences()

        // Then
        let serviceCallCount = await mockNotificationService.getPreferencesCallCount
        XCTAssertEqual(serviceCallCount, 1)
        XCTAssertNotNil(sut.error)
        XCTAssertFalse(sut.isLoading)
    }

    func testLoadNotificationPreferences_SetsLoadingState() async {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Success"
        )
        await mockNotificationService.setGetPreferencesResponse(mockResponse)

        // When
        let loadTask = Task {
            await sut.loadNotificationPreferences()
        }

        // Give the task a moment to start (loading should be true)
        try? await Task.sleep(nanoseconds: 10_000_000) // 10ms

        // Then - Should eventually complete
        await loadTask.value
        XCTAssertFalse(sut.isLoading)
    }

    // MARK: - Toggle Notifications Tests

    func testToggleNotifications_EnableWhenDisabled_Success() async {
        // Given
        sut.areNotificationsEnabled = false
        sut.systemPermissionGranted = true

        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Enabled"
        )
        await mockNotificationService.setUpdatePreferencesResponse(mockResponse)

        // When
        await sut.toggleNotifications()

        // Then
        let serviceCallCount = await mockNotificationService.updatePreferencesCallCount
        XCTAssertEqual(serviceCallCount, 1)

        let lastEnabled = await mockNotificationService.lastPreferencesEnabled
        XCTAssertEqual(lastEnabled, true)
        XCTAssertTrue(sut.areNotificationsEnabled)
        XCTAssertFalse(sut.isLoading)
    }

    func testToggleNotifications_DisableWhenEnabled_Success() async {
        // Given
        sut.areNotificationsEnabled = true
        sut.systemPermissionGranted = true

        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Disabled"
        )
        await mockNotificationService.setUpdatePreferencesResponse(mockResponse)

        // When
        await sut.toggleNotifications()

        // Then
        let serviceCallCount = await mockNotificationService.updatePreferencesCallCount
        XCTAssertEqual(serviceCallCount, 1)

        let lastEnabled = await mockNotificationService.lastPreferencesEnabled
        XCTAssertEqual(lastEnabled, false)
        XCTAssertFalse(sut.areNotificationsEnabled)
    }

    func testToggleNotifications_Failure_SetsError() async {
        // Given
        sut.areNotificationsEnabled = false
        sut.systemPermissionGranted = true

        let expectedError = APIError.serverError(statusCode: 500)
        await mockNotificationService.setUpdatePreferencesError(expectedError)

        // When
        await sut.toggleNotifications()

        // Then
        XCTAssertNotNil(sut.error)
        XCTAssertFalse(sut.isLoading)
    }

    // MARK: - System Permission Tests

    func testCheckSystemPermission_WhenAuthorized_UpdatesPermissionState() async {
        // Given
        mockNotificationManager.mockAuthorizationStatus = .authorized

        // When
        await sut.checkSystemPermission()

        // Then
        XCTAssertFalse(sut.isCheckingPermission)
        XCTAssertTrue(sut.systemPermissionGranted)
        XCTAssertTrue(mockNotificationManager.checkAuthorizationStatusCalled)
    }

    func testCheckSystemPermission_WhenDenied_UpdatesPermissionState() async {
        // Given
        mockNotificationManager.mockAuthorizationStatus = .denied

        // When
        await sut.checkSystemPermission()

        // Then
        XCTAssertFalse(sut.isCheckingPermission)
        XCTAssertFalse(sut.systemPermissionGranted)
        XCTAssertTrue(mockNotificationManager.checkAuthorizationStatusCalled)
    }

    func testRequestSystemPermission_WhenGranted_UpdatesState() async {
        // Given
        mockNotificationManager.mockAuthorizationGranted = true
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Success"
        )
        await mockNotificationService.setUpdatePreferencesResponse(mockResponse)

        // When
        await sut.requestSystemPermission()

        // Then
        XCTAssertTrue(mockNotificationManager.requestAuthorizationCalled)
        XCTAssertTrue(sut.systemPermissionGranted)
    }

    func testRequestSystemPermission_WhenDenied_DoesNotEnableNotifications() async {
        // Given
        mockNotificationManager.mockAuthorizationGranted = false

        // When
        await sut.requestSystemPermission()

        // Then
        XCTAssertTrue(mockNotificationManager.requestAuthorizationCalled)
        XCTAssertFalse(sut.systemPermissionGranted)
        // Should not attempt to toggle notifications when permission denied
        let updateCount = await mockNotificationService.updatePreferencesCallCount
        XCTAssertEqual(updateCount, 0)
    }

    // MARK: - Computed Properties Tests

    func testCanToggle_WhenNotLoading_ReturnsTrue() {
        // Given
        sut.isLoading = false
        sut.isCheckingPermission = false

        // When
        let canToggle = sut.canToggle

        // Then
        XCTAssertTrue(canToggle)
    }

    func testCanToggle_WhenLoading_ReturnsFalse() {
        // Given
        // Use setValue to bypass @Published and set internal state for testing
        sut.setLoading(true)

        // When
        let canToggle = sut.canToggle

        // Then
        XCTAssertFalse(canToggle)
    }

    func testCanToggle_WhenCheckingPermission_ReturnsFalse() {
        // Given
        sut.isCheckingPermission = true

        // When
        let canToggle = sut.canToggle

        // Then
        XCTAssertFalse(canToggle)
    }

    func testStatusMessage_WhenEnabledButNoPermission_ReturnsWarning() {
        // Given
        sut.areNotificationsEnabled = true
        sut.systemPermissionGranted = false

        // When
        let message = sut.statusMessage

        // Then
        XCTAssertNotNil(message)
        XCTAssertEqual(message, "viewmodel.notification.permission.warning".localized)
    }

    func testStatusMessage_WhenEnabledWithPermission_ReturnsNil() {
        // Given
        sut.areNotificationsEnabled = true
        sut.systemPermissionGranted = true

        // When
        let message = sut.statusMessage

        // Then
        XCTAssertNil(message)
    }

    func testStatusMessage_WhenDisabled_ReturnsNil() {
        // Given
        sut.areNotificationsEnabled = false
        sut.systemPermissionGranted = false

        // When
        let message = sut.statusMessage

        // Then
        XCTAssertNil(message)
    }

    func testShowPermissionWarning_WhenEnabledButNoPermission_ReturnsTrue() {
        // Given
        sut.areNotificationsEnabled = true
        sut.systemPermissionGranted = false

        // When
        let showWarning = sut.showPermissionWarning

        // Then
        XCTAssertTrue(showWarning)
    }

    func testShowPermissionWarning_WhenEnabledWithPermission_ReturnsFalse() {
        // Given
        sut.areNotificationsEnabled = true
        sut.systemPermissionGranted = true

        // When
        let showWarning = sut.showPermissionWarning

        // Then
        XCTAssertFalse(showWarning)
    }

    func testShowPermissionWarning_WhenDisabled_ReturnsFalse() {
        // Given
        sut.areNotificationsEnabled = false
        sut.systemPermissionGranted = false

        // When
        let showWarning = sut.showPermissionWarning

        // Then
        XCTAssertFalse(showWarning)
    }

    // MARK: - Error Handling Tests

    func testLoadNotificationPreferences_NetworkError_SetsRetryableError() async {
        // Given
        let networkError = APIError.networkError(URLError(.notConnectedToInternet))
        await mockNotificationService.setGetPreferencesError(networkError)

        // When
        await sut.loadNotificationPreferences()

        // Then
        XCTAssertNotNil(sut.error)
        XCTAssertTrue(sut.canRetry)
    }

    func testToggleNotifications_Unauthorized_SetsNonRetryableError() async {
        // Given
        sut.areNotificationsEnabled = false
        sut.systemPermissionGranted = true

        let authError = APIError.unauthorized()
        await mockNotificationService.setUpdatePreferencesError(authError)

        // When
        await sut.toggleNotifications()

        // Then
        XCTAssertNotNil(sut.error)
        XCTAssertFalse(sut.canRetry)
    }

    // MARK: - Integration Tests

    func testLoadThenToggle_Success() async {
        // Given - Load preferences first
        let loadResponse = NotificationPreferencesResponse(
            notificationEnabled: false,
            message: "Loaded"
        )
        await mockNotificationService.setGetPreferencesResponse(loadResponse)

        await sut.loadNotificationPreferences()

        // Verify initial state
        XCTAssertFalse(sut.areNotificationsEnabled)

        // Given - Toggle notifications
        let toggleResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Toggled"
        )
        await mockNotificationService.setUpdatePreferencesResponse(toggleResponse)
        sut.systemPermissionGranted = true

        // When
        await sut.toggleNotifications()

        // Then
        XCTAssertTrue(sut.areNotificationsEnabled)
        let updateCount = await mockNotificationService.updatePreferencesCallCount
        XCTAssertEqual(updateCount, 1)
    }

    func testRetry_AfterLoadFailure_Success() async {
        // Given - First attempt fails
        let networkError = APIError.networkError(URLError(.notConnectedToInternet))
        await mockNotificationService.setGetPreferencesError(networkError)

        await sut.loadNotificationPreferences()
        XCTAssertNotNil(sut.error)

        // Given - Retry succeeds
        await mockNotificationService.setGetPreferencesError(nil)
        let successResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Success"
        )
        await mockNotificationService.setGetPreferencesResponse(successResponse)

        // When
        await sut.retry()

        // Then
        XCTAssertNil(sut.error)
        XCTAssertTrue(sut.areNotificationsEnabled)
    }

    // MARK: - Edge Cases

    func testToggleNotifications_MultipleRapidCalls_HandlesCorrectly() async {
        // Given
        sut.systemPermissionGranted = true
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Success"
        )
        await mockNotificationService.setUpdatePreferencesResponse(mockResponse)

        // When - Make multiple rapid calls
        await sut.toggleNotifications()
        await sut.toggleNotifications()
        await sut.toggleNotifications()

        // Then - All calls should complete (though state may toggle)
        let updateCount = await mockNotificationService.updatePreferencesCallCount
        XCTAssertEqual(updateCount, 3)
        XCTAssertFalse(sut.isLoading)
    }

    func testLoadNotificationPreferences_CalledMultipleTimes_HandlesCorrectly() async {
        // Given
        let mockResponse = NotificationPreferencesResponse(
            notificationEnabled: true,
            message: "Success"
        )
        await mockNotificationService.setGetPreferencesResponse(mockResponse)

        // When
        await sut.loadNotificationPreferences()
        await sut.loadNotificationPreferences()
        await sut.loadNotificationPreferences()

        // Then
        let getCount = await mockNotificationService.getPreferencesCallCount
        XCTAssertEqual(getCount, 3)
        XCTAssertFalse(sut.isLoading)
    }

    // MARK: - BaseViewModel Integration Tests

    func testInheritsFromBaseViewModel_HasLoadingState() {
        // When
        sut.setLoading(true)

        // Then
        XCTAssertTrue(sut.isLoading)
    }

    func testInheritsFromBaseViewModel_HasErrorHandling() async {
        // Given
        let error = APIError.serverError(statusCode: 500)
        await mockNotificationService.setGetPreferencesError(error)

        // When
        await sut.loadNotificationPreferences()

        // Then
        XCTAssertNotNil(sut.error)
        XCTAssertTrue(sut.canRetry) // Server errors are retryable
    }

    func testInheritsFromBaseViewModel_ClearError() async {
        // Given
        let error = APIError.serverError(statusCode: 500)
        await mockNotificationService.setGetPreferencesError(error)
        await sut.loadNotificationPreferences()
        XCTAssertNotNil(sut.error)

        // When
        sut.clearError()

        // Then
        XCTAssertNil(sut.error)
    }

    // MARK: - Permission Request Tracking Tests

    func testRequestSystemPermission_FirstTime_RequestsAuthorization() async {
        // Given - Permission not yet requested
        mockNotificationManager.hasRequestedNotificationPermission = false
        mockNotificationManager.setAuthorizationStatus(.notDetermined)

        // When
        await sut.requestSystemPermission()

        // Then - Should call requestAuthorization
        XCTAssertTrue(mockNotificationManager.requestAuthorizationCalled, "Should request authorization for first time")
    }

    func testRequestSystemPermission_AlreadyRequested_StatusDenied_OpensSettings() async {
        // Given - Permission already requested and denied
        mockNotificationManager.hasRequestedNotificationPermission = true
        mockNotificationManager.setAuthorizationStatus(.denied)

        // When
        await sut.requestSystemPermission()

        // Then - Should NOT call requestAuthorization again, just opens settings
        // Note: We can't easily test if openSystemSettings was called without more mocking,
        // but we can verify requestAuthorization was NOT called
        XCTAssertEqual(
            mockNotificationManager.requestAuthorizationCallCount,
            0,
            "Should not request authorization again when already denied"
        )
    }

    func testRequestSystemPermission_AlreadyRequested_StatusAuthorized_NoAction() async {
        // Given - Permission already requested and granted
        mockNotificationManager.hasRequestedNotificationPermission = true
        mockNotificationManager.setAuthorizationStatus(.authorized)

        // When
        await sut.requestSystemPermission()

        // Then - Should not request authorization again
        XCTAssertEqual(
            mockNotificationManager.requestAuthorizationCallCount,
            0,
            "Should not request authorization again when already authorized"
        )
        XCTAssertTrue(sut.systemPermissionGranted, "systemPermissionGranted should be true")
    }

    func testRequestSystemPermission_EdgeCase_FlagSetButStatusNotDetermined() async {
        // Given - Edge case: flag is set but status is .notDetermined
        // This can happen if app was reinstalled or UserDefaults persisted but system permission was reset
        mockNotificationManager.hasRequestedNotificationPermission = true
        mockNotificationManager.setAuthorizationStatus(.notDetermined)

        // When
        await sut.requestSystemPermission()

        // Then - Should allow re-requesting (handles edge case gracefully)
        XCTAssertTrue(
            mockNotificationManager.requestAuthorizationCalled,
            "Should allow re-requesting for edge case (app reinstall)"
        )
    }

    func testRequestSystemPermission_Success_EnablesBackend() async {
        // Given - Permission not requested, backend disabled
        mockNotificationManager.hasRequestedNotificationPermission = false
        mockNotificationManager.setAuthorizationStatus(.notDetermined)
        mockNotificationManager.mockAuthorizationGranted = true
        await mockNotificationService.setUpdatePreferencesResponse(NotificationPreferencesResponse(notificationEnabled: true, message: "Success"))
        sut.areNotificationsEnabled = false

        // When
        await sut.requestSystemPermission()

        // Then - Should enable in backend after granting permission
        XCTAssertTrue(sut.areNotificationsEnabled, "Should enable in backend after permission granted")
    }

    func testRequestSystemPermission_Denied_DoesNotEnableBackend() async {
        // Given - Permission not requested, backend disabled, user will deny
        mockNotificationManager.hasRequestedNotificationPermission = false
        mockNotificationManager.setAuthorizationStatus(.notDetermined)
        mockNotificationManager.mockAuthorizationGranted = false // User denies
        sut.areNotificationsEnabled = false

        // When
        await sut.requestSystemPermission()

        // Then - Should NOT enable in backend after denial
        XCTAssertFalse(sut.areNotificationsEnabled, "Should not enable in backend after permission denied")
        XCTAssertFalse(sut.systemPermissionGranted, "systemPermissionGranted should be false")
    }

    func testToggleNotifications_WhenEnabled_NoPermission_RequestsPermission() async {
        // Given - Notifications disabled, no system permission
        sut.areNotificationsEnabled = false
        mockNotificationManager.setAuthorizationStatus(.notDetermined)
        mockNotificationManager.hasRequestedNotificationPermission = false

        // When
        await sut.toggleNotifications()

        // Then - Should request system permission instead of toggling
        XCTAssertTrue(mockNotificationManager.requestAuthorizationCalled, "Should request permission first")
    }

    // MARK: - Permission Recovery Banner Tests (BTS-239)

    func testShowPermissionRecoveryBanner_WhenDenied_ReturnsTrue() {
        // Given
        mockNotificationManager.setAuthorizationStatus(.denied)

        // When
        let showBanner = sut.showPermissionRecoveryBanner

        // Then
        XCTAssertTrue(showBanner, "Should show recovery banner when permission is denied")
    }

    func testShowPermissionRecoveryBanner_WhenNotDetermined_ReturnsFalse() {
        // Given
        mockNotificationManager.setAuthorizationStatus(.notDetermined)

        // When
        let showBanner = sut.showPermissionRecoveryBanner

        // Then
        XCTAssertFalse(showBanner, "Should not show recovery banner when permission not determined")
    }

    func testShowPermissionRecoveryBanner_WhenAuthorized_ReturnsFalse() {
        // Given
        mockNotificationManager.setAuthorizationStatus(.authorized)

        // When
        let showBanner = sut.showPermissionRecoveryBanner

        // Then
        XCTAssertFalse(showBanner, "Should not show recovery banner when permission is authorized")
    }

    func testShowPermissionRecoveryBanner_WhenProvisional_ReturnsFalse() {
        // Given
        mockNotificationManager.setAuthorizationStatus(.provisional)

        // When
        let showBanner = sut.showPermissionRecoveryBanner

        // Then
        XCTAssertFalse(showBanner, "Should not show recovery banner when permission is provisional")
    }

    func testShowPermissionRecoveryBanner_WhenEphemeral_ReturnsFalse() {
        // Given
        mockNotificationManager.setAuthorizationStatus(.ephemeral)

        // When
        let showBanner = sut.showPermissionRecoveryBanner

        // Then
        XCTAssertFalse(showBanner, "Should not show recovery banner when permission is ephemeral")
    }

    func testShowPermissionRecoveryBanner_ReactsToStatusChanges() async {
        // Given - Initially not determined
        mockNotificationManager.setAuthorizationStatus(.notDetermined)
        XCTAssertFalse(sut.showPermissionRecoveryBanner, "Should not show banner initially")

        // When - User denies permission
        mockNotificationManager.setAuthorizationStatus(.denied)
        await sut.checkSystemPermission()

        // Then - Banner should appear
        XCTAssertTrue(sut.showPermissionRecoveryBanner, "Should show banner after denial")

        // When - User enables permission in Settings
        mockNotificationManager.setAuthorizationStatus(.authorized)
        await sut.checkSystemPermission()

        // Then - Banner should disappear
        XCTAssertFalse(sut.showPermissionRecoveryBanner, "Should hide banner after authorization")
    }

    // MARK: - Settings Redirect Alert Tests (BTS-239)

    func testShowSettingsRedirectAlert_InitialValue_IsFalse() {
        // Then
        XCTAssertFalse(sut.showSettingsRedirectAlert, "showSettingsRedirectAlert should start as false")
    }

    func testRequestSystemPermission_AlreadyRequestedAndDenied_ShowsSettingsRedirectAlert() async {
        // Given - Permission already requested and denied
        mockNotificationManager.hasRequestedNotificationPermission = true
        mockNotificationManager.setAuthorizationStatus(.denied)

        // When
        await sut.requestSystemPermission()

        // Then - Should show the settings redirect alert
        XCTAssertTrue(sut.showSettingsRedirectAlert, "Should show settings redirect alert when permission already denied")
        XCTAssertEqual(
            mockNotificationManager.requestAuthorizationCallCount,
            0,
            "Should not request authorization again"
        )
    }

    func testConfirmOpenSystemSettings_DismissesAlert() {
        // Given - Alert is showing
        sut.showSettingsRedirectAlert = true

        // When
        sut.confirmOpenSystemSettings()

        // Then - Alert should be dismissed
        XCTAssertFalse(sut.showSettingsRedirectAlert, "confirmOpenSystemSettings should dismiss the alert")
        // Note: We can't easily verify UIApplication.shared.open was called without more complex mocking
    }

    func testDismissSettingsRedirectAlert_DismissesAlert() {
        // Given - Alert is showing
        sut.showSettingsRedirectAlert = true

        // When
        sut.dismissSettingsRedirectAlert()

        // Then - Alert should be dismissed
        XCTAssertFalse(sut.showSettingsRedirectAlert, "dismissSettingsRedirectAlert should dismiss the alert")
    }
}
