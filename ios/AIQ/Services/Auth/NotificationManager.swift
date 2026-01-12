import Combine
import Foundation
import os
import UIKit
import UserNotifications

/// Manager for coordinating push notification permissions, device tokens, and backend synchronization
@MainActor
class NotificationManager: ObservableObject, NotificationManagerProtocol, DeviceTokenManagerProtocol {
    // MARK: - Singleton

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

    private let notificationService: NotificationServiceProtocol
    private let authManager: AuthManagerProtocol
    private let notificationCenter: UserNotificationCenterProtocol
    private let application: ApplicationProtocol
    private var cancellables = Set<AnyCancellable>()
    private let logger = Logger(subsystem: "com.aiq.app", category: "NotificationManager")

    /// Cached device token (stored until user is authenticated)
    private var pendingDeviceToken: String?

    /// UserDefaults key for storing device token
    private let deviceTokenKey = "com.aiq.deviceToken"

    /// UserDefaults key for tracking if permission has been requested
    private let permissionRequestedKey = "com.aiq.hasRequestedNotificationPermission"

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

    // MARK: - Initialization

    init(
        notificationService: NotificationServiceProtocol = NotificationService.shared,
        authManager: AuthManagerProtocol = AuthManager.shared,
        notificationCenter: UserNotificationCenterProtocol = UNUserNotificationCenter.current(),
        application: ApplicationProtocol = UIApplication.shared
    ) {
        self.notificationService = notificationService
        self.authManager = authManager
        self.notificationCenter = notificationCenter
        self.application = application

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
            #if DEBUG
                print("❌ [NotificationManager] Authorization request failed: \(error.localizedDescription)")
            #endif
            return false
        }
    }

    /// Check and update current authorization status
    func checkAuthorizationStatus() async {
        authorizationStatus = await notificationCenter.getAuthorizationStatus()
    }

    /// Handle device token received from APNs
    /// - Parameter deviceToken: The device token data
    func didReceiveDeviceToken(_ deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        #if DEBUG
            print("📱 [NotificationManager] Received device token: \(tokenString)")
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
        print("❌ [NotificationManager] Failed to register for remote notifications: \(error.localizedDescription)")

        // Clear cached token on failure
        clearCachedDeviceToken()
        isDeviceTokenRegistered = false
    }

    /// Unregister device token from backend (called on logout)
    func unregisterDeviceToken() async {
        guard isDeviceTokenRegistered else {
            print("ℹ️ [NotificationManager] No device token to unregister")
            return
        }

        do {
            let response = try await notificationService.unregisterDeviceToken()
            print("✅ [NotificationManager] Device token unregistered: \(response.message)")

            isDeviceTokenRegistered = false
            clearCachedDeviceToken()

        } catch {
            print("❌ [NotificationManager] Failed to unregister device token: \(error.localizedDescription)")
            // Even if backend fails, clear local state
            isDeviceTokenRegistered = false
            clearCachedDeviceToken()
        }
    }

    /// Retry registration with cached device token (useful after failed attempts)
    func retryDeviceTokenRegistration() async {
        guard let token = pendingDeviceToken ?? getCachedDeviceToken() else {
            print("ℹ️ [NotificationManager] No device token available to retry")
            return
        }

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
        // Guard against concurrent registration attempts
        guard !isRegisteringToken else {
            print("ℹ️ [NotificationManager] Registration already in progress")
            return
        }

        // Check if user is authenticated
        guard authManager.isAuthenticated else {
            print("ℹ️ [NotificationManager] User not authenticated, caching token for later")
            pendingDeviceToken = token
            return
        }

        // Check if already registered
        guard !isDeviceTokenRegistered else {
            print("ℹ️ [NotificationManager] Device token already registered")
            return
        }

        isRegisteringToken = true

        do {
            let response = try await notificationService.registerDeviceToken(token)
            print("✅ [NotificationManager] Device token registered: \(response.message)")

            isDeviceTokenRegistered = true
            pendingDeviceToken = nil

        } catch {
            print("❌ [NotificationManager] Failed to register device token: \(error.localizedDescription)")
            // Keep token cached for retry
            pendingDeviceToken = token
            isDeviceTokenRegistered = false
        }

        isRegisteringToken = false
    }

    /// Cache device token to UserDefaults
    /// - Parameter token: The device token string
    private func cacheDeviceToken(_ token: String) {
        UserDefaults.standard.set(token, forKey: deviceTokenKey)
        pendingDeviceToken = token
    }

    /// Get cached device token from UserDefaults
    /// - Returns: Cached device token if available
    private func getCachedDeviceToken() -> String? {
        UserDefaults.standard.string(forKey: deviceTokenKey)
    }

    /// Load cached device token from UserDefaults
    private func loadCachedDeviceToken() {
        pendingDeviceToken = getCachedDeviceToken()
    }

    /// Clear cached device token from UserDefaults
    private func clearCachedDeviceToken() {
        UserDefaults.standard.removeObject(forKey: deviceTokenKey)
        UserDefaults.standard.removeObject(forKey: permissionRequestedKey)
        pendingDeviceToken = nil
    }
}
