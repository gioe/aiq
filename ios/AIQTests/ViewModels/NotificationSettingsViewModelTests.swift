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

    override func tearDown() {
        sut = nil
        mockNotificationService = nil
        mockNotificationManager = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInit_SetsDefaultValues() {
        // Then
        XCTAssertFalse(sut.notificationEnabled)
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
        XCTAssertTrue(sut.notificationEnabled)
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
        sut.notificationEnabled = false
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
        XCTAssertTrue(sut.notificationEnabled)
        XCTAssertFalse(sut.isLoading)
    }

    func testToggleNotifications_DisableWhenEnabled_Success() async {
        // Given
        sut.notificationEnabled = true
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
        XCTAssertFalse(sut.notificationEnabled)
    }

    func testToggleNotifications_Failure_SetsError() async {
        // Given
        sut.notificationEnabled = false
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
        sut.notificationEnabled = true
        sut.systemPermissionGranted = false

        // When
        let message = sut.statusMessage

        // Then
        XCTAssertNotNil(message)
        XCTAssertEqual(message, "viewmodel.notification.permission.warning".localized)
    }

    func testStatusMessage_WhenEnabledWithPermission_ReturnsNil() {
        // Given
        sut.notificationEnabled = true
        sut.systemPermissionGranted = true

        // When
        let message = sut.statusMessage

        // Then
        XCTAssertNil(message)
    }

    func testStatusMessage_WhenDisabled_ReturnsNil() {
        // Given
        sut.notificationEnabled = false
        sut.systemPermissionGranted = false

        // When
        let message = sut.statusMessage

        // Then
        XCTAssertNil(message)
    }

    func testShowPermissionWarning_WhenEnabledButNoPermission_ReturnsTrue() {
        // Given
        sut.notificationEnabled = true
        sut.systemPermissionGranted = false

        // When
        let showWarning = sut.showPermissionWarning

        // Then
        XCTAssertTrue(showWarning)
    }

    func testShowPermissionWarning_WhenEnabledWithPermission_ReturnsFalse() {
        // Given
        sut.notificationEnabled = true
        sut.systemPermissionGranted = true

        // When
        let showWarning = sut.showPermissionWarning

        // Then
        XCTAssertFalse(showWarning)
    }

    func testShowPermissionWarning_WhenDisabled_ReturnsFalse() {
        // Given
        sut.notificationEnabled = false
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
        sut.notificationEnabled = false
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
        XCTAssertFalse(sut.notificationEnabled)

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
        XCTAssertTrue(sut.notificationEnabled)
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
        XCTAssertTrue(sut.notificationEnabled)
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
}
