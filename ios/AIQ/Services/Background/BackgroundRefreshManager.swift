import BackgroundTasks
import Foundation
import os
import UserNotifications

/// Manager for handling background refresh tasks to check for new test availability
///
/// Responsibilities:
/// - Registers and schedules BGAppRefreshTask for periodic background execution
/// - Fetches test availability status from API when app is in background
/// - Sends local notification if user can take a new test
/// - Optimizes for battery efficiency (completes within 20 seconds)
///
/// Background refresh is triggered by iOS based on:
/// - App usage patterns (iOS learns when user typically uses the app)
/// - System conditions (battery level, network availability)
/// - Scheduled refresh requests (we request 4-hour intervals, iOS optimizes)
@MainActor
class BackgroundRefreshManager: ObservableObject {
    // MARK: - Singleton

    static let shared = BackgroundRefreshManager()

    // MARK: - Private Properties

    private let logger = Logger(subsystem: "com.aiq.app", category: "BackgroundRefresh")
    private let apiClient: APIClientProtocol
    private let authManager: AuthManagerProtocol
    private let analyticsService: AnalyticsService
    private let networkMonitor: NetworkMonitorProtocol
    private let notificationCenter: UserNotificationCenterProtocol

    /// UserDefaults key for tracking last successful refresh timestamp
    private let lastRefreshKey = "com.aiq.lastBackgroundRefresh"

    /// UserDefaults key for tracking last notification date (prevents spam)
    private let lastNotificationKey = "com.aiq.lastTestNotification"

    // MARK: - Initialization

    init(
        apiClient: APIClientProtocol = APIClient.shared,
        authManager: AuthManagerProtocol = AuthManager.shared,
        analyticsService: AnalyticsService = AnalyticsService.shared,
        networkMonitor: NetworkMonitorProtocol = NetworkMonitor.shared,
        notificationCenter: UserNotificationCenterProtocol = UNUserNotificationCenter.current()
    ) {
        self.apiClient = apiClient
        self.authManager = authManager
        self.analyticsService = analyticsService
        self.networkMonitor = networkMonitor
        self.notificationCenter = notificationCenter
    }

    // MARK: - Public Methods

    /// Register background refresh task with BGTaskScheduler
    /// Call this in AppDelegate.didFinishLaunchingWithOptions
    func registerBackgroundTask() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Constants.BackgroundRefresh.taskIdentifier,
            using: nil
        ) { [weak self] task in
            guard let self, let refreshTask = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }

            Task { @MainActor in
                await self.handleBackgroundRefresh(task: refreshTask)
            }
        }

        logger.info("Registered background refresh task with identifier: \(Constants.BackgroundRefresh.taskIdentifier)")
    }

    /// Schedule next background refresh
    /// Call this when app enters background or after completing a refresh
    func scheduleRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: Constants.BackgroundRefresh.taskIdentifier)

        // Request refresh after minimum interval (iOS will optimize based on usage patterns)
        request.earliestBeginDate = Date(timeIntervalSinceNow: Constants.BackgroundRefresh.minimumInterval)

        do {
            try BGTaskScheduler.shared.submit(request)
            let hours = Constants.BackgroundRefresh.minimumInterval / 3600
            logger.info("Scheduled background refresh for \(hours, privacy: .public) hours from now")
        } catch {
            logger.error("Failed to schedule background refresh: \(error.localizedDescription, privacy: .public)")
            analyticsService.track(event: .backgroundRefreshScheduleFailed, properties: [
                "error": error.localizedDescription
            ])
        }
    }

    // MARK: - Private Methods

    /// Handle background refresh task execution
    /// - Parameter task: The BGAppRefreshTask to handle
    private func handleBackgroundRefresh(task: BGAppRefreshTask) async {
        logger.info("Background refresh task started")

        let startTime = Date()

        // Set up task expiration handler
        task.expirationHandler = { [weak self] in
            self?.logger.warning("Background refresh task expired before completion")
            self?.analyticsService.track(event: .backgroundRefreshExpired)
            task.setTaskCompleted(success: false)
        }

        // Perform the refresh
        let success = await performRefresh()

        let duration = Date().timeIntervalSince(startTime)
        logger.info("Background refresh completed in \(duration, privacy: .public)s with success: \(success)")

        // Track completion analytics
        analyticsService.track(event: .backgroundRefreshCompleted, properties: [
            "success": success,
            "duration_seconds": duration
        ])

        // Schedule next refresh
        scheduleRefresh()

        // Mark task as completed
        task.setTaskCompleted(success: success)
    }

    /// Perform the actual background refresh logic
    /// - Returns: Whether the refresh completed successfully
    private func performRefresh() async -> Bool {
        // Fast-fail checks to minimize battery usage

        // Check if user is authenticated
        guard authManager.isAuthenticated else {
            logger.info("Skipping refresh: User not authenticated")
            return true // Not an error, just nothing to do
        }

        // Check network connectivity
        guard networkMonitor.isConnected else {
            logger.info("Skipping refresh: No network connection")
            return true // Not an error, just nothing to do
        }

        // Check if we refreshed recently (prevent excessive API calls)
        if let lastRefresh = getLastRefreshDate(),
           Date().timeIntervalSince(lastRefresh) < Constants.BackgroundRefresh.minimumInterval {
            logger.info("Skipping refresh: Last refresh was too recent")
            return true // Not an error, respecting rate limit
        }

        // Fetch test availability
        do {
            let isTestAvailable = try await checkTestAvailability()

            // Update last refresh timestamp
            saveLastRefreshDate()

            // Send notification if test is available and we haven't notified recently
            if isTestAvailable {
                await sendTestAvailableNotification()
            }

            return true

        } catch {
            logger.error("Background refresh failed: \(error.localizedDescription, privacy: .public)")
            analyticsService.track(event: .backgroundRefreshFailed, properties: [
                "error": error.localizedDescription
            ])
            return false
        }
    }

    /// Check if a new test is available for the user
    /// - Returns: True if user can take a new test
    private func checkTestAvailability() async throws -> Bool {
        // Fetch the most recent test from history
        let response: PaginatedTestHistoryResponse = try await apiClient.request(
            endpoint: .testHistory(limit: 1, offset: nil),
            method: .get,
            requiresAuth: true
        )

        // If no tests exist, user can take a test
        guard let lastTest = response.results.first else {
            logger.info("No previous tests found - test is available")
            return true
        }

        // Check if 90 days have passed since last test
        let daysSinceLastTest = Calendar.current.dateComponents(
            [.day],
            from: lastTest.completedAt,
            to: Date()
        ).day ?? 0

        let isAvailable = daysSinceLastTest >= Constants.BackgroundRefresh.testCadenceDays

        logger.info("Last test was \(daysSinceLastTest) days ago. Available: \(isAvailable)")

        return isAvailable
    }

    /// Send local notification that a new test is available
    private func sendTestAvailableNotification() async {
        // Check if we've already notified for this test window
        if let lastNotification = getLastNotificationDate() {
            let daysSinceNotification = Calendar.current.dateComponents(
                [.day],
                from: lastNotification,
                to: Date()
            ).day ?? 0

            // Don't notify more than once per test cadence period
            if daysSinceNotification < Constants.BackgroundRefresh.testCadenceDays {
                logger.info("Skipping notification: Already notified \(daysSinceNotification) days ago")
                return
            }
        }

        // Check notification authorization status
        let status = await notificationCenter.getAuthorizationStatus()
        guard status == .authorized else {
            logger.info("Skipping notification: Not authorized (status: \(status.rawValue))")
            return
        }

        // Create notification content
        let content = UNMutableNotificationContent()
        content.title = NSLocalizedString("notification.test.available.title", comment: "")
        content.body = NSLocalizedString("notification.test.available.body", comment: "")
        content.sound = .default
        content.badge = 1
        content.userInfo = ["type": "test_reminder"]

        // Create trigger to deliver immediately
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)

        // Create notification request
        let request = UNNotificationRequest(
            identifier: "test_available_\(Date().timeIntervalSince1970)",
            content: content,
            trigger: trigger
        )

        // Schedule notification
        do {
            try await notificationCenter.add(request)

            // Save notification timestamp
            saveLastNotificationDate()

            logger.info("Sent test available notification")
            analyticsService.track(event: .backgroundRefreshNotificationSent)

        } catch {
            logger.error("Failed to send notification: \(error.localizedDescription, privacy: .public)")
            analyticsService.track(event: .backgroundRefreshNotificationFailed, properties: [
                "error": error.localizedDescription
            ])
        }
    }

    // MARK: - UserDefaults Helpers

    /// Get the date of the last successful refresh
    private func getLastRefreshDate() -> Date? {
        UserDefaults.standard.object(forKey: lastRefreshKey) as? Date
    }

    /// Save the current date as the last refresh timestamp
    private func saveLastRefreshDate() {
        UserDefaults.standard.set(Date(), forKey: lastRefreshKey)
    }

    /// Get the date of the last notification sent
    private func getLastNotificationDate() -> Date? {
        UserDefaults.standard.object(forKey: lastNotificationKey) as? Date
    }

    /// Save the current date as the last notification timestamp
    private func saveLastNotificationDate() {
        UserDefaults.standard.set(Date(), forKey: lastNotificationKey)
    }
}
