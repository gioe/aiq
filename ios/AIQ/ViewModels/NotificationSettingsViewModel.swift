import Combine
import Foundation
import UIKit
import UserNotifications

/// ViewModel for managing notification settings
@MainActor
class NotificationSettingsViewModel: BaseViewModel {
    // MARK: - Published Properties

    /// Whether notifications are enabled in the backend
    @Published var notificationEnabled: Bool = false

    /// Whether system permission is granted
    @Published var systemPermissionGranted: Bool = false

    /// Whether we're currently checking permissions
    @Published var isCheckingPermission: Bool = false

    // MARK: - Private Properties

    private let notificationService: NotificationServiceProtocol
    private let notificationManager: NotificationManagerProtocol
    private let authManager: AuthManager
    private var viewCancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    init(
        notificationService: NotificationServiceProtocol = NotificationService.shared,
        notificationManager: NotificationManagerProtocol = NotificationManager.shared
    ) {
        self.notificationService = notificationService
        self.notificationManager = notificationManager
        authManager = AuthManager.shared
        super.init()

        // Observe app lifecycle to check permission changes
        observeAppLifecycle()

        // Observe authorization status from NotificationManager
        observeAuthorizationStatus()
    }

    // MARK: - Public Methods

    /// Load current notification preferences
    func loadNotificationPreferences() async {
        setLoading(true)
        clearError()

        do {
            // Get backend preferences
            let response = try await notificationService.getNotificationPreferences()
            notificationEnabled = response.notificationEnabled

            // Check system permission
            await checkSystemPermission()

            setLoading(false)

        } catch {
            handleError(error, context: .notificationPreferences) { [weak self] in
                await self?.loadNotificationPreferences()
            }
        }
    }

    /// Toggle notification preferences
    func toggleNotifications() async {
        // Check system permission first
        await checkSystemPermission()

        // If user wants to enable but doesn't have permission, prompt them
        if !notificationEnabled && !systemPermissionGranted {
            await requestSystemPermission()
            return
        }

        // Update backend preference
        setLoading(true)
        clearError()

        do {
            let newValue = !notificationEnabled
            let response = try await notificationService.updateNotificationPreferences(enabled: newValue)
            notificationEnabled = response.notificationEnabled

            setLoading(false)

        } catch {
            handleError(error, context: .notificationPreferences) { [weak self] in
                await self?.toggleNotifications()
            }
        }
    }

    /// Check current system permission status
    func checkSystemPermission() async {
        isCheckingPermission = true

        await notificationManager.checkAuthorizationStatus()
        systemPermissionGranted = notificationManager.authorizationStatus == .authorized

        isCheckingPermission = false
    }

    /// Request system notification permission
    func requestSystemPermission() async {
        let granted = await notificationManager.requestAuthorization()
        systemPermissionGranted = granted

        if granted {
            // Now enable in backend
            await toggleNotifications()
        }
    }

    /// Open system settings for the app
    func openSystemSettings() {
        guard let settingsURL = URL(string: UIApplication.openSettingsURLString) else {
            return
        }

        if UIApplication.shared.canOpenURL(settingsURL) {
            UIApplication.shared.open(settingsURL)
        }
    }

    // MARK: - Computed Properties

    /// Whether the toggle should be enabled
    var canToggle: Bool {
        !isLoading && !isCheckingPermission
    }

    /// Status message to display
    var statusMessage: String? {
        if notificationEnabled && !systemPermissionGranted {
            return "viewmodel.notification.permission.warning".localized
        }
        return nil
    }

    /// Whether to show a warning about system permissions
    var showPermissionWarning: Bool {
        notificationEnabled && !systemPermissionGranted
    }

    // MARK: - Private Methods

    /// Observe app lifecycle events to check for permission changes
    private func observeAppLifecycle() {
        // Check permission status when app becomes active (user may have changed it in Settings)
        NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)
            .sink { [weak self] _ in
                Task { @MainActor [weak self] in
                    await self?.checkSystemPermission()
                }
            }
            .store(in: &viewCancellables)

        // Also check when app enters foreground
        NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)
            .sink { [weak self] _ in
                Task { @MainActor [weak self] in
                    await self?.checkSystemPermission()
                }
            }
            .store(in: &viewCancellables)
    }

    /// Observe authorization status changes from NotificationManager
    private func observeAuthorizationStatus() {
        notificationManager.authorizationStatusPublisher
            .sink { [weak self] status in
                Task { @MainActor [weak self] in
                    guard let self else { return }
                    systemPermissionGranted = (status == .authorized)

                    // Handle different authorization states
                    await handleAuthorizationStatus(status)
                }
            }
            .store(in: &viewCancellables)
    }

    /// Handle different authorization statuses
    /// - Parameter status: The current authorization status
    private func handleAuthorizationStatus(_ status: UNAuthorizationStatus) async {
        switch status {
        case .notDetermined:
            // User hasn't been asked yet - no action needed
            print("ℹ️ [NotificationSettings] Notification permission not determined")

        case .denied:
            // User explicitly denied - show warning if backend thinks it's enabled
            print("⚠️ [NotificationSettings] Notification permission denied")
            if notificationEnabled {
                // Sync backend to disabled state
                await disableBackendNotifications()
            }

        case .authorized:
            // User granted permission - ensure device token is registered
            print("✅ [NotificationSettings] Notification permission authorized")
            await notificationManager.retryDeviceTokenRegistration()

        case .provisional:
            // Provisional authorization (quiet notifications) - treat as authorized
            print("ℹ️ [NotificationSettings] Notification permission provisional")
            await notificationManager.retryDeviceTokenRegistration()

        case .ephemeral:
            // App Clip authorization - treat as authorized
            print("ℹ️ [NotificationSettings] Notification permission ephemeral")

        @unknown default:
            print("⚠️ [NotificationSettings] Unknown authorization status: \(status.rawValue)")
        }
    }

    /// Disable notifications in backend without updating UI toggle
    private func disableBackendNotifications() async {
        do {
            let response = try await notificationService.updateNotificationPreferences(enabled: false)
            notificationEnabled = response.notificationEnabled
        } catch {
            // Record non-fatal error to Crashlytics for production monitoring
            CrashlyticsErrorRecorder.recordError(error, context: .notificationPreferences)
        }
    }
}
