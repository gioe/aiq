import AIQSharedKit
import Combine
import Foundation
import os
import UIKit
import UserNotifications

/// Manager for coordinating push notification permissions, device tokens, and backend synchronization
@MainActor
class NotificationManager: ObservableObject, NotificationManagerProtocol, DeviceTokenManagerProtocol {
    // MARK: - Types

    /// Closure signature for recording errors to Crashlytics. Declared on the class so tests can
    /// inject a capturing mock and assert on context/additionalInfo without touching Crashlytics
    /// itself. Matches the pattern used by `SettingsViewModel.CrashlyticsErrorRecorderClosure`.
    typealias CrashlyticsErrorRecorderClosure = (
        Error,
        CrashlyticsErrorRecorder.ErrorContext,
        [String: Any]?
    ) -> Void

    // MARK: - Singleton

    /// Shared singleton instance
    ///
    /// - Warning: Deprecated. Use `ServiceContainer.shared.resolve(NotificationManagerProtocol.self)` instead.
    ///   ServiceContainer now owns the singleton instances directly, making this property redundant.
    @available(*, deprecated, message: "Use ServiceContainer.shared.resolve(NotificationManagerProtocol.self) instead")
    static let shared = NotificationManager()

    // MARK: - Published Properties

    /// Current notification authorization status
    @Published private(set) var authorizationStatus: UNAuthorizationStatus = .notDetermined

    /// Whether the device token has been successfully registered with the backend
    @Published private(set) var isDeviceTokenRegistered: Bool = false

    /// Publisher for authorization status changes (protocol conformance)
    var authorizationStatusPublisher: Published<UNAuthorizationStatus>.Publisher {
        $authorizationStatus
    }

    // MARK: - Private Properties

    private let notificationService: any NotificationServiceProtocol
    private let authManager: any AuthManagerProtocol
    private let notificationCenter: any UserNotificationCenterProtocol
    private let application: any ApplicationProtocol
    private let errorRecorder: CrashlyticsErrorRecorderClosure
    private var cancellables = Set<AnyCancellable>()
    private let logger = Logger(subsystem: "com.aiq.app", category: "NotificationManager")

    /// Cached device token (stored until user is authenticated)
    private var pendingDeviceToken: String?

    /// UserDefaults key for storing device token
    /// Internal static constant to allow tests to reference the same key without needing an instance
    static let deviceTokenKey = "com.aiq.deviceToken"

    /// UserDefaults key for tracking if permission has been requested
    private let permissionRequestedKey = "com.aiq.hasRequestedNotificationPermission"

    /// UserDefaults key for tracking if provisional permission has been requested
    private let provisionalPermissionRequestedKey = "com.aiq.hasRequestedProvisionalPermission"

    /// Whether we're currently processing a device token registration
    private var isRegisteringToken = false

    /// Whether notification permission has been requested from the user
    var hasRequestedNotificationPermission: Bool {
        get {
            UserDefaults.standard.bool(forKey: permissionRequestedKey)
        }
        set {
            UserDefaults.standard.set(newValue, forKey: permissionRequestedKey)
        }
    }

    /// Whether provisional notification permission has been requested
    var hasRequestedProvisionalPermission: Bool {
        get {
            UserDefaults.standard.bool(forKey: provisionalPermissionRequestedKey)
        }
        set {
            UserDefaults.standard.set(newValue, forKey: provisionalPermissionRequestedKey)
        }
    }

    /// UserDefaults key for tracking if upgrade prompt has been shown
    private let upgradePromptShownKey = "com.aiq.hasShownUpgradePrompt"

    /// Whether the upgrade prompt has been shown to a provisional user
    /// Persists across app launches via UserDefaults to prevent showing the prompt repeatedly.
    /// Once shown, the prompt will not appear again for this user until they log out or reinstall.
    var hasShownUpgradePrompt: Bool {
        get {
            UserDefaults.standard.bool(forKey: upgradePromptShownKey)
        }
        set {
            UserDefaults.standard.set(newValue, forKey: upgradePromptShownKey)
        }
    }

    // MARK: - Initialization

    init(
        notificationService: any NotificationServiceProtocol = ServiceContainer.shared.resolve(),
        authManager: any AuthManagerProtocol = ServiceContainer.shared.resolve(),
        notificationCenter: any UserNotificationCenterProtocol = UNUserNotificationCenter.current(),
        application: (any ApplicationProtocol)? = nil,
        errorRecorder: @escaping CrashlyticsErrorRecorderClosure = { error, context, info in
            CrashlyticsErrorRecorder.recordError(error, context: context, additionalInfo: info)
        }
    ) {
        self.notificationService = notificationService
        self.authManager = authManager
        self.notificationCenter = notificationCenter
        self.application = application ?? UIApplication.shared
        self.errorRecorder = errorRecorder

        // Load cached device token synchronously (UserDefaults is fast)
        loadCachedDeviceToken()

        // Set up Combine subscription synchronously (critical for token handling)
        observeAuthStateChanges()

        // Check authorization status asynchronously (non-critical, just updates UI state)
        Task {
            await checkAuthorizationStatus()
        }
    }

    // MARK: - Public Methods

    /// Request notification authorization from the system
    /// - Returns: Whether authorization was granted
    @discardableResult
    func requestAuthorization() async -> Bool {
        // Mark that we've requested permission BEFORE showing the dialog
        // This prevents duplicate requests throughout the app lifecycle
        hasRequestedNotificationPermission = true

        // Capture previous status for error reporting
        let previousStatus = authorizationStatus

        do {
            let granted = try await notificationCenter
                .requestAuthorization(options: [.alert, .sound, .badge])

            await checkAuthorizationStatus()

            if granted {
                // Register for remote notifications
                application.registerForRemoteNotifications()
            }

            return granted

        } catch {
            logger.error(
                "Failed to request notification authorization: \(error.localizedDescription, privacy: .public)"
            )
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .notificationPermission,
                additionalInfo: [
                    "operation": "requestAuthorization",
                    "previousStatus": "\(previousStatus.rawValue)"
                ]
            )
            #if DebugBuild
                print("[ERROR] [NotificationManager] Authorization request failed: \(error.localizedDescription)")
            #endif
            return false
        }
    }

    /// Request provisional notification authorization (silent notifications)
    /// Provisional notifications appear only in Notification Center without alerts, sounds, or badges
    /// - Returns: Whether provisional authorization was granted (typically always true initially)
    @discardableResult
    func requestProvisionalAuthorization() async -> Bool {
        // Mark that we've requested provisional permission
        hasRequestedProvisionalPermission = true

        // Capture previous status for error reporting
        let previousStatus = authorizationStatus

        do {
            // Request provisional authorization with full capability options.
            // Including .alert, .sound, .badge alongside .provisional means if the user
            // has previously granted full authorization, the system will return that status.
            // This allows seamless upgrade from provisional to full authorization.
            let granted = try await notificationCenter
                .requestAuthorization(options: [.alert, .sound, .badge, .provisional])

            await checkAuthorizationStatus()

            if granted {
                // Register for remote notifications
                application.registerForRemoteNotifications()
            }

            return granted

        } catch {
            logger.error(
                """
                Failed to request provisional notification authorization: \
                \(error.localizedDescription, privacy: .public)
                """
            )
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .notificationPermission,
                additionalInfo: [
                    "operation": "requestProvisionalAuthorization",
                    "previousStatus": "\(previousStatus.rawValue)"
                ]
            )
            return false
        }
    }

    /// Check and update current authorization status
    func checkAuthorizationStatus() async {
        let newStatus = await notificationCenter.getAuthorizationStatus()
        if newStatus != authorizationStatus {
            authorizationStatus = newStatus
        }
    }

    /// Re-register the app with APNs when the user has already granted notification permission.
    ///
    /// Apple recommends calling `registerForRemoteNotifications()` every launch so rotated tokens
    /// reach the backend. This also covers the case where a previous launch received a token but
    /// the initial POST to `/v1/notifications/register-device` failed silently (e.g. because the
    /// user was not yet authenticated). Safe to call repeatedly — no-ops when authorization status
    /// is `.notDetermined` or `.denied`.
    func ensureRemoteNotificationRegistrationIfAuthorized() async {
        let status = await notificationCenter.getAuthorizationStatus()
        if status != authorizationStatus {
            authorizationStatus = status
        }
        guard status == .authorized || status == .provisional else {
            logger.info(
                "Launch-time APNs registration skipped (status=\(String(describing: status), privacy: .public))"
            )
            return
        }
        logger.info(
            "Launch-time APNs registration firing (status=\(String(describing: status), privacy: .public))"
        )
        application.registerForRemoteNotifications()
    }

    /// Handle the app becoming active. If authorization is granted but the device token has not
    /// yet been registered with the backend, retry the POST using any cached token. No-ops when
    /// the token is already registered or the user has not granted permission.
    func handleAppDidBecomeActive() async {
        guard !isDeviceTokenRegistered else {
            logger.info("didBecomeActive: token already registered, no retry needed")
            return
        }
        let status = await notificationCenter.getAuthorizationStatus()
        guard status == .authorized || status == .provisional else {
            logger.info(
                "didBecomeActive: skipping retry (status=\(String(describing: status), privacy: .public))"
            )
            return
        }
        logger.info(
            "didBecomeActive: retrying token registration (status=\(String(describing: status), privacy: .public))"
        )
        await retryDeviceTokenRegistration()
    }

    /// Handle device token received from APNs
    /// - Parameter deviceToken: The device token data
    func didReceiveDeviceToken(_ deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        let tokenPrefix = String(tokenString.prefix(12))
        logger.info(
            """
            Received APNs device token (prefix=\(tokenPrefix, privacy: .public), \
            length=\(tokenString.count, privacy: .public))
            """
        )
        #if DebugBuild
            print("[NOTIFICATION] Received device token: \(tokenString)")
        #endif

        // Cache the token
        cacheDeviceToken(tokenString)

        // Try to register with backend if authenticated
        Task {
            await registerDeviceTokenIfPossible(tokenString)
        }
    }

    /// Handle device token registration failure
    /// - Parameter error: The error that occurred
    func didFailToRegisterForRemoteNotifications(error: Error) {
        logger.error(
            "APNs registration failed at the iOS layer: \(error.localizedDescription, privacy: .public)"
        )
        errorRecorder(
            error,
            .notificationPermission,
            ["operation": "didFailToRegisterForRemoteNotifications"]
        )

        // Clear cached token on failure
        clearCachedDeviceToken()
        isDeviceTokenRegistered = false
    }

    /// Unregister device token from backend (called on logout)
    func unregisterDeviceToken() async {
        guard isDeviceTokenRegistered else {
            print("[INFO] [NotificationManager] No device token to unregister")
            return
        }

        do {
            try await notificationService.unregisterDeviceToken()
            print("[SUCCESS] [NotificationManager] Device token unregistered")

            isDeviceTokenRegistered = false
            clearCachedDeviceToken()

        } catch {
            print("[ERROR] [NotificationManager] Failed to unregister device token: \(error.localizedDescription)")
            // Even if backend fails, clear local state
            isDeviceTokenRegistered = false
            clearCachedDeviceToken()
        }
    }

    /// Retry registration with cached device token (useful after failed attempts)
    func retryDeviceTokenRegistration() async {
        guard let token = pendingDeviceToken ?? getCachedDeviceToken() else {
            logger.info("Retry skipped: no cached device token available")
            return
        }
        let tokenPrefix = String(token.prefix(12))
        logger.info("Retrying token registration (prefix=\(tokenPrefix, privacy: .public))")
        await registerDeviceTokenIfPossible(token)
    }

    // MARK: - Private Methods

    /// Observe authentication state changes to handle device token registration
    private func observeAuthStateChanges() {
        authManager.isAuthenticatedPublisher
            .sink { [weak self] isAuthenticated in
                Task { @MainActor [weak self] in
                    guard let self else { return }

                    if isAuthenticated {
                        // User logged in - try to register any pending device token
                        await retryDeviceTokenRegistration()
                    } else {
                        // User logged out - clear registration state
                        isDeviceTokenRegistered = false
                    }
                }
            }
            .store(in: &cancellables)
    }

    /// Register device token with backend if user is authenticated
    /// - Parameter token: The device token string
    private func registerDeviceTokenIfPossible(_ token: String) async {
        // swiftlint:disable:previous function_body_length
        let tokenPrefix = String(token.prefix(12))

        // Guard against concurrent registration attempts
        guard !isRegisteringToken else {
            logger.info(
                """
                registerDeviceTokenIfPossible skipped: registration in progress \
                (prefix=\(tokenPrefix, privacy: .public))
                """
            )
            return
        }

        // Check if user is authenticated
        guard authManager.isAuthenticated else {
            logger.warning(
                """
                registerDeviceTokenIfPossible skipped: user not authenticated; \
                caching token for retry (prefix=\(tokenPrefix, privacy: .public))
                """
            )
            pendingDeviceToken = token
            return
        }

        // Check if already registered
        guard !isDeviceTokenRegistered else {
            logger.info(
                """
                registerDeviceTokenIfPossible skipped: token already registered \
                (prefix=\(tokenPrefix, privacy: .public))
                """
            )
            return
        }

        isRegisteringToken = true
        logger.info(
            "POST /v1/notifications/register-device starting (prefix=\(tokenPrefix, privacy: .public))"
        )

        do {
            try await notificationService.registerDeviceToken(token)
            logger.info(
                "POST /v1/notifications/register-device succeeded (prefix=\(tokenPrefix, privacy: .public))"
            )
            isDeviceTokenRegistered = true
            pendingDeviceToken = nil

        } catch {
            logger.error(
                "Failed to register device token: \(error.localizedDescription, privacy: .public)"
            )
            errorRecorder(
                error,
                .notificationPermission,
                [
                    "operation": "registerDeviceToken",
                    "isAuthenticated": "\(authManager.isAuthenticated)"
                ]
            )
            // Keep token cached for retry
            pendingDeviceToken = token
            isDeviceTokenRegistered = false
        }

        isRegisteringToken = false
    }

    /// Cache device token to UserDefaults
    /// - Parameter token: The device token string
    private func cacheDeviceToken(_ token: String) {
        UserDefaults.standard.set(token, forKey: Self.deviceTokenKey)
        pendingDeviceToken = token
    }

    /// Get cached device token from UserDefaults
    /// - Returns: Cached device token if available
    private func getCachedDeviceToken() -> String? {
        UserDefaults.standard.string(forKey: Self.deviceTokenKey)
    }

    /// Load cached device token from UserDefaults
    private func loadCachedDeviceToken() {
        pendingDeviceToken = getCachedDeviceToken()
    }

    /// Clear cached device token from UserDefaults
    private func clearCachedDeviceToken() {
        UserDefaults.standard.removeObject(forKey: Self.deviceTokenKey)
        UserDefaults.standard.removeObject(forKey: permissionRequestedKey)
        UserDefaults.standard.removeObject(forKey: provisionalPermissionRequestedKey)
        UserDefaults.standard.removeObject(forKey: upgradePromptShownKey)
        pendingDeviceToken = nil
    }
}
