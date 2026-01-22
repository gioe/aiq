import BackgroundTasks
import FirebaseCore
import FirebaseCrashlytics
import os
import TrustKit
import UIKit
import UserNotifications

class AppDelegate: NSObject, UIApplicationDelegate {
    private let notificationManager = NotificationManager.shared
    private let deepLinkHandler = DeepLinkHandler()
    private let analyticsService = AnalyticsService.shared
    private let backgroundRefreshManager = BackgroundRefreshManager.shared
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

        #if DEBUG
            // Skip TrustKit initialization in DEBUG builds to allow development with proxies
            Self.logger.info("DEBUG build: Certificate pinning disabled for development")
            Self.logger.info("API URL: \(AppConfig.apiBaseURL)")
        #else
            initializeTrustKit()
        #endif

        // Set notification delegate
        UNUserNotificationCenter.current().delegate = self

        // Register background refresh task
        Task { @MainActor in
            backgroundRefreshManager.registerBackgroundTask()
        }

        // Note: We don't request notification permissions at launch anymore
        // Permissions are requested when user explicitly enables notifications in Settings
        // This provides better UX and follows Apple's guidelines

        return true
    }

    // MARK: - TrustKit Initialization

    /// Initialize TrustKit for SSL certificate pinning (RELEASE builds only)
    ///
    /// Configuration is loaded from TrustKit.plist in the app bundle.
    ///
    /// ## App Store Privacy Compliance
    ///
    /// Certificate pinning events fire before privacy consent as they are:
    /// - **Anonymous technical telemetry**: No PII, only security status (success/failure)
    /// - **Essential security diagnostics**: Required for app integrity verification
    /// - **Non-behavioral**: Does not track user actions or preferences
    ///
    /// This is compliant with App Store guidelines as anonymous technical/performance
    /// data may be collected without explicit consent. User-behavioral analytics
    /// (registration, login, test events) only fire post-consent via `AuthManager`.
    ///
    /// Analytics tracking:
    /// - Initialization success/failure is tracked at startup
    /// - Runtime pinning validation failures are NOT tracked here because:
    ///   * TrustKit uses auto-swizzling (TSKSwizzleNetworkDelegates = true)
    ///   * Auto-swizzling automatically validates all NSURLSession connections
    ///   * No programmatic callback mechanism is provided for validation failures
    ///   * TrustKit logs failures to console and can send reports via TSKReportUris
    /// - To monitor runtime pinning failures in production:
    ///   * Configure TSKReportUris in TrustKit.plist to send reports to a backend endpoint
    ///   * Use Data Theorem's dashboard (free) at https://datatheorem.com
    ///   * Monitor console logs for "TrustKit" messages in development/TestFlight builds
    private func initializeTrustKit() {
        guard let trustKitConfigPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let trustKitConfig = NSDictionary(contentsOfFile: trustKitConfigPath) as? [String: Any]
        else {
            Self.logger.error("TrustKit.plist missing or invalid format - cannot load config")
            analyticsService.trackCertificatePinningInitializationFailed(
                reason: "TrustKit.plist missing or invalid format"
            )
            // Certificate pinning is critical for security - fail hard in production
            fatalError("Certificate pinning config failed to load. App cannot continue.")
        }

        // Verify minimum required pins are configured before initializing
        guard let pinnedDomains = trustKitConfig["TSKPinnedDomains"] as? [String: Any] else {
            analyticsService.trackCertificatePinningInitializationFailed(
                reason: "TSKPinnedDomains missing from config"
            )
            fatalError("TrustKit config missing TSKPinnedDomains")
        }
        guard let railwayConfig = pinnedDomains[AppConfig.productionDomain] as? [String: Any] else {
            analyticsService.trackCertificatePinningInitializationFailed(
                reason: "Domain config missing",
                domain: AppConfig.productionDomain
            )
            fatalError("TrustKit config missing pinning for \(AppConfig.productionDomain)")
        }
        guard let hashes = railwayConfig["TSKPublicKeyHashes"] as? [String] else {
            analyticsService.trackCertificatePinningInitializationFailed(
                reason: "TSKPublicKeyHashes missing",
                domain: AppConfig.productionDomain
            )
            fatalError("TrustKit config missing TSKPublicKeyHashes")
        }
        guard hashes.count >= Constants.Security.minRequiredPins else {
            analyticsService.trackCertificatePinningInitializationFailed(
                reason: "Insufficient pins (found \(hashes.count), need \(Constants.Security.minRequiredPins))",
                domain: AppConfig.productionDomain
            )
            fatalError(
                "Certificate pinning requires at least \(Constants.Security.minRequiredPins) pins " +
                    "(primary + backup), found \(hashes.count)"
            )
        }

        TrustKit.initSharedInstance(withConfiguration: trustKitConfig)
        Self.logger.info("TrustKit initialized with certificate pinning for Railway backend")

        // Track successful initialization
        analyticsService.trackCertificatePinningInitialized(
            domain: AppConfig.productionDomain,
            pinCount: hashes.count
        )
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
            // Test reminder notification - user should take a new test (90-day cadence)
            print("Test reminder notification received")
            // Navigation will be handled when user taps the notification
            // (see userNotificationCenter(_:didReceive:withCompletionHandler:))

        case "day_30_reminder":
            // Day 30 reminder - early engagement notification sent 30 days after first test
            // Part of Phase 2.2 provisional notification testing
            print("Day 30 reminder notification received")
            // This notification is designed to be silent for provisional authorization users
            // Navigation will be handled when user taps the notification

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
        return handleDeepLink(url, source: .urlScheme)
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
        return handleDeepLink(url, source: .universalLink)
    }

    /// Process a deep link URL and navigate to the appropriate destination
    ///
    /// This method:
    /// 1. Parses the URL using DeepLinkHandler
    /// 2. Posts a notification with the deep link for the app to handle
    /// 3. The notification is handled asynchronously by the MainTabView or other components
    ///
    /// - Parameters:
    ///   - url: The deep link URL to handle
    ///   - source: The source of the deep link (URL scheme, universal link, etc.)
    /// - Returns: true if the URL was parsed successfully, false otherwise
    private func handleDeepLink(_ url: URL, source: DeepLinkSource) -> Bool {
        // Parse the deep link
        let deepLink = deepLinkHandler.parse(url)

        // Sanitize URL for analytics (remove query parameters that might contain sensitive data)
        let sanitizedURL = sanitizeURLForAnalytics(url)

        // Check if the deep link is valid
        guard deepLink != .invalid else {
            Self.logger.warning("Invalid deep link: \(url.absoluteString, privacy: .public)")
            // Track the parse failure in analytics
            deepLinkHandler.trackParseFailed(
                error: .unrecognizedRoute(route: url.path, url: sanitizedURL),
                source: source,
                originalURL: sanitizedURL
            )
            // Show user-friendly error toast
            // The detailed error has already been logged and sent to Crashlytics by DeepLinkHandler
            Task { @MainActor in
                ToastManager.shared.show("toast.deeplink.invalid".localized, type: .error)
            }
            return false
        }

        Self.logger.info("Successfully parsed deep link: \(String(describing: deepLink), privacy: .public)")

        // Post notification for the app to handle
        // This allows the deep link to be handled asynchronously when the app is ready
        // (e.g., after authentication check, view hierarchy is set up, etc.)
        NotificationCenter.default.post(
            name: .deepLinkReceived,
            object: nil,
            userInfo: [
                "deepLink": deepLink,
                "source": source,
                "originalURL": sanitizedURL
            ]
        )

        return true
    }

    /// Sanitize a URL for analytics by removing sensitive query parameters
    ///
    /// - Parameter url: The URL to sanitize
    /// - Returns: A sanitized URL string with scheme, host, and path only
    private func sanitizeURLForAnalytics(_ url: URL) -> String {
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        // Remove query parameters to avoid leaking sensitive data
        components?.queryItems = nil
        components?.fragment = nil
        return components?.string ?? url.absoluteString
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

        // Get notification type
        let notificationType = userInfo["type"] as? String ?? "unknown"

        // Track notification tap with current authorization status
        // Note: completionHandler is called inside the Task to ensure all processing completes
        // before the system considers notification handling finished
        Task { @MainActor in
            await notificationManager.checkAuthorizationStatus()
            let authStatusString = authorizationStatusDescription(notificationManager.authorizationStatus)
            analyticsService.trackNotificationTapped(
                notificationType: notificationType,
                authorizationStatus: authStatusString
            )

            // Post notification to navigate to appropriate screen
            // Include authorization status so MainTabView can decide whether to show upgrade prompt
            NotificationCenter.default.post(
                name: .notificationTapped,
                object: nil,
                userInfo: [
                    "type": notificationType,
                    "payload": userInfo,
                    "authorizationStatus": notificationManager.authorizationStatus.rawValue
                ]
            )

            // Call completion handler after all processing is done
            completionHandler()
        }
    }

    /// Convert UNAuthorizationStatus to a human-readable string for analytics
    private func authorizationStatusDescription(_ status: UNAuthorizationStatus) -> String {
        switch status {
        case .notDetermined: "not_determined"
        case .denied: "denied"
        case .authorized: "authorized"
        case .provisional: "provisional"
        case .ephemeral: "ephemeral"
        @unknown default: "unknown"
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    /// Posted when user taps on a push notification
    static let notificationTapped = Notification.Name("notificationTapped")

    /// Posted when a deep link is received (URL scheme or universal link)
    static let deepLinkReceived = Notification.Name("deepLinkReceived")
}
