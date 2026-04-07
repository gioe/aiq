import AIQSharedKit
import Foundation
import OSLog
import UIKit

// MARK: - Backend Data Types

/// A single analytics event with timestamp and properties for backend submission
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

// MARK: - FirebaseAnalyticsProvider

/// Analytics provider that submits events to the backend `/v1/analytics/events` endpoint.
///
/// Implements the `AnalyticsProvider` protocol from SharedKit and preserves all production
/// analytics infrastructure from the original `AnalyticsService`:
/// - Automatic retry with exponential backoff on network errors
/// - Offline queue for events when network is unavailable
/// - Batch submission for efficient network usage
/// - UserDefaults persistence for crash recovery
///
/// ## App Store Privacy Compliance
///
/// This provider is designed to comply with Apple's App Store privacy requirements:
/// - No analytics events fire until the user has accepted the privacy policy
/// - Email addresses are sanitized to domain-only via the convenience extensions
/// - Device IDs use Apple's vendor identifier (resets on app reinstall)
class FirebaseAnalyticsProvider: AnalyticsProvider {
    /// Logger instance for analytics events
    private let logger: Logger

    /// Logger instance for error events
    private let errorLogger: Logger

    /// Queue of events waiting to be sent
    private var eventQueue: [AnalyticsEventData] = []

    /// Serial queue for thread-safe access to event queue
    private let queueAccessQueue = DispatchQueue(label: "com.aiq.analyticsQueue")

    /// Timer for periodic batch submission
    private var batchTimer: Timer?

    /// Maximum number of events per batch
    let maxBatchSize: Int

    /// Maximum queue size to prevent unbounded memory growth
    let maxQueueSize: Int

    /// Interval for automatic batch submission (seconds)
    private let batchInterval: TimeInterval

    /// Maximum retries for failed submissions
    let maxRetries: Int

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

    /// Whether to auto-submit when queue reaches maxBatchSize
    private let autoSubmitWhenFull: Bool

    /// Creates a FirebaseAnalyticsProvider with default production configuration.
    convenience init(
        networkMonitor: NetworkMonitorProtocol,
        secureStorage: SecureStorageProtocol
    ) {
        self.init(
            userDefaults: .standard,
            networkMonitor: networkMonitor,
            urlSession: .shared,
            secureStorage: secureStorage,
            maxBatchSize: Constants.Analytics.maxBatchSize,
            maxQueueSize: Constants.Analytics.maxQueueSize,
            maxRetries: Constants.Analytics.maxRetries,
            batchInterval: Constants.Analytics.batchInterval,
            startTimer: true
        )
    }

    /// Internal initializer for dependency injection (used in tests)
    init(
        userDefaults: UserDefaults,
        networkMonitor: NetworkMonitorProtocol,
        urlSession: URLSession,
        secureStorage: SecureStorageProtocol,
        maxBatchSize: Int = Constants.Analytics.maxBatchSize,
        maxQueueSize: Int = Constants.Analytics.maxQueueSize,
        maxRetries: Int = Constants.Analytics.maxRetries,
        batchInterval: TimeInterval = Constants.Analytics.batchInterval,
        startTimer: Bool = true,
        autoSubmitWhenFull: Bool = true
    ) {
        logger = Logger(subsystem: "com.aiq.app", category: "analytics")
        errorLogger = Logger(subsystem: "com.aiq.app", category: "errors")
        self.userDefaults = userDefaults
        self.networkMonitor = networkMonitor
        self.urlSession = urlSession
        self.secureStorage = secureStorage
        self.maxBatchSize = maxBatchSize
        self.maxQueueSize = maxQueueSize
        self.maxRetries = maxRetries
        self.batchInterval = batchInterval
        self.autoSubmitWhenFull = autoSubmitWhenFull

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

    // MARK: - AnalyticsProvider Conformance

    func track(_ event: AIQSharedKit.AnalyticsEvent) {
        #if DebugBuild
            let propertiesString = event.parameters?.description ?? "{}"
            logger.info("Analytics Event: \(event.name) | Properties: \(propertiesString)")
        #endif

        let eventData = AnalyticsEventData(
            eventName: event.name,
            timestamp: Date(),
            properties: event.parameters?.mapValues { AnyCodable($0) }
        )

        var shouldSubmit = false
        var droppedCount = 0
        queueAccessQueue.sync {
            if eventQueue.count >= maxQueueSize {
                droppedCount = eventQueue.count - maxQueueSize + 1
                eventQueue.removeFirst(droppedCount)
            }
            eventQueue.append(eventData)
            shouldSubmit = eventQueue.count >= maxBatchSize
            persistEventsUnsafe()
        }

        if droppedCount > 0 {
            errorLogger.warning("Analytics: Dropped \(droppedCount) oldest events due to queue overflow")
        }

        if shouldSubmit && autoSubmitWhenFull {
            Task {
                await submitBatch()
            }
        }
    }

    func trackScreen(_ name: String, parameters: [String: Any]?) {
        track(AIQSharedKit.AnalyticsEvent(name: "screen.\(name)", parameters: parameters))
    }

    func setUserProperty(_: String?, forName _: String) {
        // Backend analytics does not track user properties separately
    }

    func setUserID(_: String?) {
        // Backend analytics does not track user ID separately
    }

    func reset() {
        queueAccessQueue.sync {
            eventQueue.removeAll()
            userDefaults.removeObject(forKey: Self.storageKey)
        }
    }

    // MARK: - Flush

    /// Force submission of all pending events.
    /// Call this before app termination or logout.
    func flush() async {
        await submitBatch()
    }

    // MARK: - Private Methods

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

    private func submitBatch() async {
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

        guard networkMonitor.isConnected else {
            logger.info("Analytics: Offline, events queued for later")
            return
        }

        var eventsToSubmit: [AnalyticsEventData] = []
        queueAccessQueue.sync {
            guard !eventQueue.isEmpty else { return }
            let count = min(maxBatchSize, eventQueue.count)
            eventsToSubmit = Array(eventQueue.prefix(count))
        }

        guard !eventsToSubmit.isEmpty else { return }

        let batch = AnalyticsEventsBatch(
            events: eventsToSubmit,
            clientPlatform: "ios",
            appVersion: AppConfig.appVersion,
            deviceId: getDeviceId()
        )

        let success = await submitWithRetry(batch: batch, maxRetries: maxRetries)

        if success {
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

    private func sendToBackend(batch: AnalyticsEventsBatch) async throws {
        guard let url = URL(string: "\(AppConfig.apiBaseURL)/v1/analytics/events") else {
            throw APIError.api(.invalidURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("iOS", forHTTPHeaderField: "X-Platform")
        request.setValue(AppConfig.appVersion, forHTTPHeaderField: "X-App-Version")
        request.timeoutInterval = Constants.Analytics.requestTimeout

        if let token = getAuthToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        request.httpBody = try encoder.encode(batch)

        let (data, response) = try await urlSession.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.api(.invalidResponse)
        }

        guard (200 ... 299).contains(httpResponse.statusCode) else {
            throw APIError.api(.serverError(statusCode: httpResponse.statusCode, message: nil))
        }

        _ = try? JSONDecoder().decode(AnalyticsEventsResponse.self, from: data)
    }

    private func getAuthToken() -> String? {
        try? secureStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
    }

    private func getDeviceId() -> String? {
        UIDevice.current.identifierForVendor?.uuidString
    }

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

    // MARK: - Test Helpers (Internal)

    #if DebugBuild
        var eventQueueCount: Int {
            queueAccessQueue.sync { eventQueue.count }
        }

        func testSubmitBatch() async {
            await submitBatch()
        }

        func testPersistEvents() {
            queueAccessQueue.sync {
                persistEventsUnsafe()
            }
        }

        func testClearQueue() {
            queueAccessQueue.sync {
                eventQueue.removeAll()
            }
        }
    #endif
}
