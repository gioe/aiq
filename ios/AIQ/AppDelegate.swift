import UIKit
import UserNotifications

class AppDelegate: NSObject, UIApplicationDelegate {
    private let notificationManager = NotificationManager.shared

    func application(
        _: UIApplication,
        didFinishLaunchingWithOptions _: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
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
}
