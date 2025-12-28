import FirebaseCore
import FirebaseCrashlytics
import os
import TrustKit
import UIKit
import UserNotifications

class AppDelegate: NSObject, UIApplicationDelegate {
    private let notificationManager = NotificationManager.shared
    private let deepLinkHandler = DeepLinkHandler()
    private static let logger = Logger(subsystem: "com.aiq.app", category: "AppDelegate")

    /// Weak reference to the app router for deep link navigation
    /// Set by AIQApp during initialization
    weak var appRouter: AppRouter?

    func application(
        _: UIApplication,
        didFinishLaunchingWithOptions _: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // Initialize Firebase
        FirebaseApp.configure()

        // Initialize TrustKit for SSL certificate pinning
        // Configuration is loaded from TrustKit.plist in the app bundle
        if let trustKitConfigPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
           let trustKitConfig = NSDictionary(contentsOfFile: trustKitConfigPath) as? [String: Any] {
            TrustKit.initSharedInstance(withConfiguration: trustKitConfig)
            Self.logger.info("TrustKit initialized with certificate pinning for Railway backend")
        } else {
            Self.logger.error("Failed to load TrustKit configuration from TrustKit.plist")
        }

        // Set notification delegate
        UNUserNotificationCenter.current().delegate = self

        // Note: We don't request notification permissions at launch anymore
        // Permissions are requested when user explicitly enables notifications in Settings
        // This provides better UX and follows Apple's guidelines

        return true
    }

    // MARK: - Remote Notification Callbacks

    func application(
        _: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        // Delegate to NotificationManager for proper handling
        Task { @MainActor in
            notificationManager.didReceiveDeviceToken(deviceToken)
        }
    }

    func application(
        _: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        // Delegate to NotificationManager for proper handling
        Task { @MainActor in
            notificationManager.didFailToRegisterForRemoteNotifications(error: error)
        }
    }

    // MARK: - Handle Received Notifications

    func application(
        _: UIApplication,
        didReceiveRemoteNotification userInfo: [AnyHashable: Any],
        fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        // Handle received push notification when app is in background
        print("Received remote notification: \(userInfo)")

        // Handle notification data
        handleNotificationData(userInfo)

        completionHandler(.newData)
    }

    // MARK: - Notification Handling

    /// Handle notification data and perform appropriate actions
    /// - Parameter userInfo: Notification payload
    private func handleNotificationData(_ userInfo: [AnyHashable: Any]) {
        // Extract notification type and data
        guard let notificationType = userInfo["type"] as? String else {
            print("No notification type found in payload")
            return
        }

        print("Handling notification of type: \(notificationType)")

        // Handle different notification types
        switch notificationType {
        case "test_reminder":
            // Test reminder notification - user should take a new test
            print("Test reminder notification received")
            // Navigation will be handled when user taps the notification
            // (see userNotificationCenter(_:didReceive:withCompletionHandler:))

        default:
            print("Unknown notification type: \(notificationType)")
        }
    }

    // MARK: - Deep Link Handling

    /// Handle URL scheme deep links (aiq://...)
    ///
    /// This method is called when the app is opened via a custom URL scheme.
    /// Deep links are parsed and navigation is performed via the AppRouter.
    ///
    /// - Parameters:
    ///   - app: The singleton app object
    ///   - url: The URL to open
    ///   - options: A dictionary of URL handling options
    /// - Returns: true if the URL was handled successfully
    func application(
        _: UIApplication,
        open url: URL,
        options _: [UIApplication.OpenURLOptionsKey: Any] = [:]
    ) -> Bool {
        Self.logger.info("Received URL scheme deep link: \(url.absoluteString, privacy: .public)")
        return handleDeepLink(url)
    }

    /// Handle universal links (https://aiq.app/...)
    ///
    /// This method is called when the app is opened via a universal link.
    /// Universal links provide a seamless experience when opening web links in the app.
    ///
    /// - Parameters:
    ///   - application: The singleton app object
    ///   - userActivity: The user activity object containing the universal link
    ///   - restorationHandler: A block to execute if your app creates objects to perform the task
    /// - Returns: true if the user activity was handled successfully
    func application(
        _: UIApplication,
        continue userActivity: NSUserActivity,
        restorationHandler _: @escaping ([UIUserActivityRestoring]?) -> Void
    ) -> Bool {
        // Check if this is a universal link activity
        guard userActivity.activityType == NSUserActivityTypeBrowsingWeb,
              let url = userActivity.webpageURL
        else {
            Self.logger.warning("Received non-web user activity: \(userActivity.activityType, privacy: .public)")
            return false
        }

        Self.logger.info("Received universal link: \(url.absoluteString, privacy: .public)")
        return handleDeepLink(url)
    }

    /// Process a deep link URL and navigate to the appropriate destination
    ///
    /// This method:
    /// 1. Parses the URL using DeepLinkHandler
    /// 2. Posts a notification with the deep link for the app to handle
    /// 3. The notification is handled asynchronously by the MainTabView or other components
    ///
    /// - Parameter url: The deep link URL to handle
    /// - Returns: true if the URL was parsed successfully, false otherwise
    private func handleDeepLink(_ url: URL) -> Bool {
        // Parse the deep link
        let deepLink = deepLinkHandler.parse(url)

        // Check if the deep link is valid
        guard deepLink != .invalid else {
            Self.logger.warning("Invalid deep link: \(url.absoluteString, privacy: .public)")
            return false
        }

        Self.logger.info("Successfully parsed deep link: \(String(describing: deepLink), privacy: .public)")

        // Post notification for the app to handle
        // This allows the deep link to be handled asynchronously when the app is ready
        // (e.g., after authentication check, view hierarchy is set up, etc.)
        NotificationCenter.default.post(
            name: .deepLinkReceived,
            object: nil,
            userInfo: ["deepLink": deepLink]
        )

        return true
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension AppDelegate: UNUserNotificationCenterDelegate {
    /// Handle notifications when app is in foreground
    func userNotificationCenter(
        _: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        // Show notification banner, sound, and badge even when app is in foreground
        print("Received notification in foreground: \(notification.request.content.userInfo)")

        // Handle notification data
        handleNotificationData(notification.request.content.userInfo)

        // Present the notification to the user
        if #available(iOS 14.0, *) {
            completionHandler([.banner, .sound, .badge])
        } else {
            completionHandler([.alert, .sound, .badge])
        }
    }

    /// Handle notification taps (user tapped on notification)
    func userNotificationCenter(
        _: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        print("User tapped notification: \(response.notification.request.content.userInfo)")

        // Handle notification data
        let userInfo = response.notification.request.content.userInfo
        handleNotificationData(userInfo)

        // Post notification to navigate to appropriate screen
        // This will be handled by the view layer
        if let notificationType = userInfo["type"] as? String {
            NotificationCenter.default.post(
                name: .notificationTapped,
                object: nil,
                userInfo: ["type": notificationType, "payload": userInfo]
            )
        }

        completionHandler()
    }
}

// MARK: - Notification Names

extension Notification.Name {
    /// Posted when user taps on a push notification
    static let notificationTapped = Notification.Name("notificationTapped")

    /// Posted when a deep link is received (URL scheme or universal link)
    static let deepLinkReceived = Notification.Name("deepLinkReceived")
}
