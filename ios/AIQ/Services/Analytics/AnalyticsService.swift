import Foundation
import OSLog
import UIKit

/// Analytics event types for tracking user actions and system events
enum AnalyticsEvent: String {
    // Authentication events
    case userRegistered = "user.registered"
    case userLogin = "user.login"
    case userLogout = "user.logout"
    case tokenRefreshed = "user.token_refreshed"

    // Test session events
    case testStarted = "test.started"
    case testCompleted = "test.completed"
    case testAbandoned = "test.abandoned"
    case testAbandonedFromDashboard = "test.abandoned_from_dashboard"
    case testResumedFromDashboard = "test.resumed_from_dashboard"
    case activeSessionConflict = "test.active_session_conflict"
    case activeSessionErrorRecovered = "test.active_session_error_recovered"
    case activeSessionDetected = "test.active_session_detected"

    // Question events
    case questionAnswered = "question.answered"
    case questionSkipped = "question.skipped"

    // Performance events
    case slowAPIRequest = "performance.slow_api_request"
    case apiError = "api.error"

    // Security events
    case authFailed = "security.auth_failed"

    // Account events
    case accountDeleted = "account.deleted"
}

/// A single analytics event with timestamp and properties
struct AnalyticsEventData: Codable {
    let eventName: String
    let timestamp: Date
    let properties: [String: AnyCodable]?

    private enum CodingKeys: String, CodingKey {
        case eventName = "event_name"
        case timestamp
        case properties
    }
}

/// Batch of analytics events to send to backend
struct AnalyticsEventsBatch: Codable {
    let events: [AnalyticsEventData]
    let clientPlatform: String
    let appVersion: String
    let deviceId: String?

    private enum CodingKeys: String, CodingKey {
        case events
        case clientPlatform = "client_platform"
        case appVersion = "app_version"
        case deviceId = "device_id"
    }
}

/// Response from analytics events submission
struct AnalyticsEventsResponse: Codable {
    let success: Bool
    let eventsReceived: Int
    let message: String

    private enum CodingKeys: String, CodingKey {
        case success
        case eventsReceived = "events_received"
        case message
    }
}

/// Type-erased wrapper for JSON encoding any value
struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()

        if let intValue = try? container.decode(Int.self) {
            value = intValue
        } else if let doubleValue = try? container.decode(Double.self) {
            value = doubleValue
        } else if let boolValue = try? container.decode(Bool.self) {
            value = boolValue
        } else if let stringValue = try? container.decode(String.self) {
            value = stringValue
        } else if let arrayValue = try? container.decode([AnyCodable].self) {
            value = arrayValue.map(\.value)
        } else if let dictValue = try? container.decode([String: AnyCodable].self) {
            value = dictValue.mapValues(\.value)
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()

        switch value {
        case let intValue as Int:
            try container.encode(intValue)
        case let doubleValue as Double:
            try container.encode(doubleValue)
        case let boolValue as Bool:
            try container.encode(boolValue)
        case let stringValue as String:
            try container.encode(stringValue)
        case let arrayValue as [Any]:
            try container.encode(arrayValue.map { AnyCodable($0) })
        case let dictValue as [String: Any]:
            try container.encode(dictValue.mapValues { AnyCodable($0) })
        default:
            try container.encodeNil()
        }
    }
}

/// Analytics service for logging and monitoring user actions in the iOS app
///
/// Sends events to the backend `/v1/analytics/events` endpoint with:
/// - Automatic retry with exponential backoff on network errors
/// - Offline queue for events when network is unavailable
/// - Batch submission for efficient network usage
class AnalyticsService {
    /// Shared singleton instance
    static let shared = AnalyticsService()

    /// Logger instance for analytics events
    private let logger: Logger

    /// Logger instance for performance events
    private let performanceLogger: Logger

    /// Logger instance for error events
    private let errorLogger: Logger

    /// Queue of events waiting to be sent
    private var eventQueue: [AnalyticsEventData] = []

    /// Serial queue for thread-safe access to event queue
    private let queueAccessQueue = DispatchQueue(label: "com.aiq.analyticsQueue")

    /// Timer for periodic batch submission
    private var batchTimer: Timer?

    /// Maximum number of events per batch
    let maxBatchSize = 50

    /// Maximum queue size to prevent unbounded memory growth
    let maxQueueSize = 500

    /// Interval for automatic batch submission (seconds)
    private let batchInterval: TimeInterval

    /// Maximum retries for failed submissions
    let maxRetries = 3

    /// Storage key for persisted events
    static let storageKey = "com.aiq.analyticsEventQueue"

    /// Network monitor for connectivity status
    private let networkMonitor: NetworkMonitorProtocol

    /// User defaults for event persistence
    private let userDefaults: UserDefaults

    /// URL session for network requests (injectable for testing)
    private let urlSession: URLSession

    /// Secure storage for auth token (injectable for testing)
    private let secureStorage: SecureStorageProtocol

    /// Flag to prevent concurrent batch submissions
    private var isSubmitting = false

    /// Private singleton initializer
    private convenience init() {
        self.init(
            userDefaults: .standard,
            networkMonitor: NetworkMonitor.shared,
            urlSession: .shared,
            secureStorage: KeychainStorage.shared,
            batchInterval: 30.0,
            startTimer: true
        )
    }

    /// Internal initializer for dependency injection (used in tests)
    init(
        userDefaults: UserDefaults,
        networkMonitor: NetworkMonitorProtocol,
        urlSession: URLSession,
        secureStorage: SecureStorageProtocol,
        batchInterval: TimeInterval = 30.0,
        startTimer: Bool = true
    ) {
        // Create separate loggers for different categories
        logger = Logger(subsystem: "com.aiq.app", category: "analytics")
        performanceLogger = Logger(subsystem: "com.aiq.app", category: "performance")
        errorLogger = Logger(subsystem: "com.aiq.app", category: "errors")
        self.userDefaults = userDefaults
        self.networkMonitor = networkMonitor
        self.urlSession = urlSession
        self.secureStorage = secureStorage
        self.batchInterval = batchInterval

        // Load any persisted events from previous sessions
        loadPersistedEvents()

        // Start batch submission timer if requested
        if startTimer {
            startBatchTimer()
        }
    }

    deinit {
        batchTimer?.invalidate()
    }

    // MARK: - Public Methods

    /// Track an analytics event
    ///
    /// - Parameters:
    ///   - event: The type of event to track
    ///   - properties: Optional dictionary of event properties
    func track(event: AnalyticsEvent, properties: [String: Any]? = nil) {
        #if DEBUG
            let propertiesString = properties?.description ?? "{}"
            logger.info("Analytics Event: \(event.rawValue) | Properties: \(propertiesString)")
        #endif

        // Create event data
        let eventData = AnalyticsEventData(
            eventName: event.rawValue,
            timestamp: Date(),
            properties: properties?.mapValues { AnyCodable($0) }
        )

        // Add to queue, enforce size limit, and persist atomically
        var shouldSubmit = false
        var droppedCount = 0
        queueAccessQueue.sync {
            // Enforce max queue size - drop oldest events if at limit
            if eventQueue.count >= maxQueueSize {
                droppedCount = eventQueue.count - maxQueueSize + 1
                eventQueue.removeFirst(droppedCount)
            }
            eventQueue.append(eventData)
            shouldSubmit = eventQueue.count >= maxBatchSize

            // Persist inside sync block to prevent data loss on crash
            persistEventsUnsafe()
        }

        if droppedCount > 0 {
            errorLogger.warning("Analytics: Dropped \(droppedCount) oldest events due to queue overflow")
        }

        // If queue is full, submit immediately
        if shouldSubmit {
            Task {
                await submitBatch()
            }
        }
    }

    /// Track user registration
    ///
    /// - Parameter email: User's email address (sanitized)
    func trackUserRegistered(email: String) {
        track(event: .userRegistered, properties: [
            "email_domain": emailDomain(from: email)
        ])
    }

    /// Track user login
    ///
    /// - Parameter email: User's email address (sanitized)
    func trackUserLogin(email: String) {
        track(event: .userLogin, properties: [
            "email_domain": emailDomain(from: email)
        ])
    }

    /// Track user logout
    func trackUserLogout() {
        track(event: .userLogout)
    }

    /// Track test session start
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID
    ///   - questionCount: Number of questions in the test
    func trackTestStarted(sessionId: Int, questionCount: Int) {
        track(event: .testStarted, properties: [
            "session_id": sessionId,
            "question_count": questionCount
        ])
    }

    /// Track test completion
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID
    ///   - iqScore: Final IQ score
    ///   - durationSeconds: Time taken to complete test
    ///   - accuracy: Accuracy percentage
    func trackTestCompleted(sessionId: Int, iqScore: Int, durationSeconds: Int, accuracy: Double) {
        track(event: .testCompleted, properties: [
            "session_id": sessionId,
            "iq_score": iqScore,
            "duration_seconds": durationSeconds,
            "accuracy_percentage": accuracy
        ])
    }

    /// Track test abandonment
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID
    ///   - answeredCount: Number of questions answered before abandonment
    func trackTestAbandoned(sessionId: Int, answeredCount: Int) {
        track(event: .testAbandoned, properties: [
            "session_id": sessionId,
            "answered_count": answeredCount
        ])
    }

    /// Track active session conflict detection
    ///
    /// - Parameter sessionId: The ID of the conflicting active session
    func trackActiveSessionConflict(sessionId: Int) {
        track(event: .activeSessionConflict, properties: [
            "session_id": sessionId
        ])
    }

    /// Track test resumed from dashboard
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID being resumed
    ///   - questionsAnswered: Number of questions already answered
    func trackTestResumedFromDashboard(sessionId: Int, questionsAnswered: Int) {
        track(event: .testResumedFromDashboard, properties: [
            "session_id": sessionId,
            "questions_answered": questionsAnswered
        ])
    }

    /// Track test abandoned from dashboard
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID being abandoned
    ///   - questionsAnswered: Number of questions answered before abandonment
    func trackTestAbandonedFromDashboard(sessionId: Int, questionsAnswered: Int) {
        track(event: .testAbandonedFromDashboard, properties: [
            "session_id": sessionId,
            "questions_answered": questionsAnswered
        ])
    }

    /// Track active session error recovered
    ///
    /// - Parameters:
    ///   - sessionId: Test session ID that was recovered
    ///   - recoveryAction: Action taken to recover (resume, abandon, cancel)
    func trackActiveSessionErrorRecovered(sessionId: Int, recoveryAction: String) {
        track(event: .activeSessionErrorRecovered, properties: [
            "session_id": sessionId,
            "recovery_action": recoveryAction
        ])
    }

    /// Track active session detected on dashboard
    ///
    /// - Parameters:
    ///   - sessionId: Active test session ID
    ///   - questionsAnswered: Number of questions already answered
    func trackActiveSessionDetected(sessionId: Int, questionsAnswered: Int) {
        track(event: .activeSessionDetected, properties: [
            "session_id": sessionId,
            "questions_answered": questionsAnswered
        ])
    }

    /// Track slow API request
    ///
    /// - Parameters:
    ///   - endpoint: API endpoint path
    ///   - durationSeconds: Request duration
    ///   - statusCode: HTTP status code
    func trackSlowRequest(endpoint: String, durationSeconds: Double, statusCode: Int) {
        let message = String(format: "Slow API Request: %@ took %.2fs", endpoint, durationSeconds)
        performanceLogger.warning("\(message) | Status: \(statusCode)")

        track(event: .slowAPIRequest, properties: [
            "endpoint": endpoint,
            "duration_seconds": durationSeconds,
            "status_code": statusCode
        ])
    }

    /// Track API error
    ///
    /// - Parameters:
    ///   - endpoint: API endpoint path
    ///   - error: Error that occurred
    ///   - statusCode: HTTP status code if available
    func trackAPIError(endpoint: String, error: Error, statusCode: Int? = nil) {
        var properties: [String: Any] = [
            "endpoint": endpoint,
            "error_type": String(describing: type(of: error)),
            "error_message": error.localizedDescription
        ]

        if let statusCode {
            properties["status_code"] = statusCode
        }

        errorLogger.error("API Error: \(endpoint) | Error: \(error.localizedDescription)")

        track(event: .apiError, properties: properties)
    }

    /// Track authentication failure
    ///
    /// - Parameter reason: Reason for authentication failure
    func trackAuthFailed(reason: String) {
        errorLogger.error("Auth Failed: \(reason)")

        track(event: .authFailed, properties: [
            "reason": reason
        ])
    }

    /// Force submission of all pending events
    /// Call this before app termination or logout
    func flush() async {
        await submitBatch()
    }

    // MARK: - Private Methods

    /// Start the batch submission timer
    private func startBatchTimer() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            batchTimer = Timer.scheduledTimer(
                withTimeInterval: batchInterval,
                repeats: true
            ) { [weak self] _ in
                Task { [weak self] in
                    await self?.submitBatch()
                }
            }
        }
    }

    /// Submit pending events to the backend
    private func submitBatch() async {
        // Prevent concurrent submissions to avoid race conditions
        var shouldProceed = false
        queueAccessQueue.sync {
            if !isSubmitting {
                isSubmitting = true
                shouldProceed = true
            }
        }
        guard shouldProceed else {
            logger.debug("Analytics: Batch submission already in progress, skipping")
            return
        }

        defer {
            queueAccessQueue.sync {
                isSubmitting = false
            }
        }

        // Check network connectivity
        guard networkMonitor.isConnected else {
            logger.info("Analytics: Offline, events queued for later")
            return
        }

        // Get events to submit atomically
        var eventsToSubmit: [AnalyticsEventData] = []
        var indicesToRemove = 0
        queueAccessQueue.sync {
            guard !eventQueue.isEmpty else { return }
            indicesToRemove = min(maxBatchSize, eventQueue.count)
            eventsToSubmit = Array(eventQueue.prefix(indicesToRemove))
        }

        guard !eventsToSubmit.isEmpty else { return }

        // Create batch request
        let batch = AnalyticsEventsBatch(
            events: eventsToSubmit,
            clientPlatform: "ios",
            appVersion: AppConfig.appVersion,
            deviceId: getDeviceId()
        )

        // Submit with retry
        let success = await submitWithRetry(batch: batch, maxRetries: maxRetries)

        if success {
            // Remove submitted events and persist atomically
            let submittedCount = eventsToSubmit.count
            queueAccessQueue.sync {
                eventQueue.removeFirst(min(submittedCount, eventQueue.count))
                persistEventsUnsafe()
            }

            logger.info("Analytics: Submitted \(submittedCount) events")
        } else {
            let stuckCount = eventsToSubmit.count
            let msg = "Analytics: Failed to submit \(stuckCount) events after \(maxRetries) retries"
            errorLogger.error("\(msg). Events will remain queued.")
        }
    }

    /// Submit batch with exponential backoff retry
    private func submitWithRetry(batch: AnalyticsEventsBatch, maxRetries: Int) async -> Bool {
        var attempt = 0
        var lastError: Error?

        while attempt < maxRetries {
            do {
                try await sendToBackend(batch: batch)
                return true
            } catch {
                lastError = error
                attempt += 1
                let errMsg = error.localizedDescription
                errorLogger.error("Analytics: Submission attempt \(attempt)/\(maxRetries) failed: \(errMsg)")

                if attempt < maxRetries {
                    // Exponential backoff: 1s, 2s, 4s
                    let delay = pow(2.0, Double(attempt - 1))
                    logger.info("Analytics: Retry \(attempt)/\(maxRetries) in \(delay)s")
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                }
            }
        }

        if let error = lastError {
            let errMsg = error.localizedDescription
            errorLogger.error("Analytics: All \(maxRetries) retries exhausted. Last error: \(errMsg)")
        }
        return false
    }

    /// Send batch to backend API
    private func sendToBackend(batch: AnalyticsEventsBatch) async throws {
        guard let url = URL(string: "\(AppConfig.apiBaseURL)/v1/analytics/events") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("iOS", forHTTPHeaderField: "X-Platform")
        request.setValue(AppConfig.appVersion, forHTTPHeaderField: "X-App-Version")
        request.timeoutInterval = 30

        // Add auth token if available
        if let token = getAuthToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        request.httpBody = try encoder.encode(batch)

        let (data, response) = try await urlSession.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard (200 ... 299).contains(httpResponse.statusCode) else {
            throw APIError.serverError(statusCode: httpResponse.statusCode, message: nil)
        }

        // Decode response (optional, for verification)
        _ = try? JSONDecoder().decode(AnalyticsEventsResponse.self, from: data)
    }

    /// Get current auth token if available
    private func getAuthToken() -> String? {
        // Access secure storage for auth token
        try? secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
    }

    /// Get a unique device identifier
    private func getDeviceId() -> String? {
        UIDevice.current.identifierForVendor?.uuidString
    }

    /// Persist event queue to disk (thread-safe wrapper)
    private func persistEvents() {
        queueAccessQueue.sync {
            persistEventsUnsafe()
        }
    }

    /// Persist event queue to disk (must be called from within queueAccessQueue.sync)
    private func persistEventsUnsafe() {
        guard !eventQueue.isEmpty else {
            userDefaults.removeObject(forKey: Self.storageKey)
            return
        }

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601

        do {
            let data = try encoder.encode(eventQueue)
            userDefaults.set(data, forKey: Self.storageKey)
        } catch {
            let count = eventQueue.count
            errorLogger.error("Analytics: Failed to persist \(count) events: \(error.localizedDescription)")
        }
    }

    /// Load persisted events from disk
    private func loadPersistedEvents() {
        guard let data = userDefaults.data(forKey: Self.storageKey) else {
            return
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        do {
            let events = try decoder.decode([AnalyticsEventData].self, from: data)
            queueAccessQueue.sync {
                eventQueue = events
            }
            logger.info("Analytics: Loaded \(events.count) persisted events")
        } catch {
            let errMsg = error.localizedDescription
            errorLogger.error("Analytics: Failed to load persisted events: \(errMsg). Clearing data.")
            userDefaults.removeObject(forKey: Self.storageKey)
        }
    }

    /// Extract domain from email for privacy-preserving analytics
    ///
    /// - Parameter email: Full email address
    /// - Returns: Domain portion only (e.g., "gmail.com")
    private func emailDomain(from email: String) -> String {
        guard let atIndex = email.firstIndex(of: "@") else {
            return "unknown"
        }
        return String(email[email.index(after: atIndex)...])
    }

    // MARK: - Test Helpers (Internal)

    #if DEBUG
        /// Returns the current event queue count (for testing)
        var eventQueueCount: Int {
            queueAccessQueue.sync { eventQueue.count }
        }

        /// Manually trigger batch submission (for testing)
        func testSubmitBatch() async {
            await submitBatch()
        }

        /// Manually persist events (for testing)
        func testPersistEvents() {
            queueAccessQueue.sync {
                persistEventsUnsafe()
            }
        }

        /// Clear the event queue (for testing)
        func testClearQueue() {
            queueAccessQueue.sync {
                eventQueue.removeAll()
            }
        }
    #endif
}
