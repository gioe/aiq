@testable import AIQ
import XCTest

final class AnalyticsServiceTests: XCTestCase {
    var sut: AnalyticsService!
    var mockNetworkMonitor: MockNetworkMonitor!
    var mockUserDefaults: UserDefaults!
    var mockURLSession: URLSession!
    var mockSecureStorage: MockSecureStorage!

    override func setUp() {
        super.setUp()

        // Create mock dependencies
        mockNetworkMonitor = MockNetworkMonitor(isConnected: true)
        mockUserDefaults = UserDefaults(suiteName: "com.aiq.tests")!
        mockUserDefaults.removePersistentDomain(forName: "com.aiq.tests")
        mockSecureStorage = MockSecureStorage()

        // Configure MockURLProtocol for network requests
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        mockURLSession = URLSession(configuration: config)

        // Create SUT with injected dependencies
        sut = AnalyticsService(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0, // Long interval to prevent automatic submission during tests
            startTimer: false // Don't start timer during tests
        )
    }

    override func tearDown() {
        MockURLProtocol.requestHandler = nil
        sut = nil
        mockNetworkMonitor = nil
        mockUserDefaults.removePersistentDomain(forName: "com.aiq.tests")
        mockUserDefaults = nil
        mockURLSession = nil
        mockSecureStorage = nil
        super.tearDown()
    }

    // MARK: - Event Tracking Tests

    func testTrackEvent_AddsEventToQueue() {
        // Given
        let event = AnalyticsEvent.userLogin
        let properties: [String: Any] = ["email_domain": "example.com"]

        // When
        sut.track(event: event, properties: properties)

        // Then
        XCTAssertEqual(sut.eventQueueCount, 1, "Event should be added to queue")
    }

    func testTrackEvent_WithoutProperties() {
        // Given
        let event = AnalyticsEvent.userLogout

        // When
        sut.track(event: event)

        // Then
        XCTAssertEqual(sut.eventQueueCount, 1)
    }

    func testTrackEvent_MultipleEvents() {
        // When
        sut.track(event: .userLogin)
        sut.track(event: .testStarted, properties: ["session_id": 123])
        sut.track(event: .testCompleted, properties: ["session_id": 123, "iq_score": 120])

        // Then
        XCTAssertEqual(sut.eventQueueCount, 3)
    }

    func testTrackEvent_EnforcesMaxQueueSize() {
        // Given - Max queue size is 500
        let maxQueueSize = sut.maxQueueSize

        // Disable network to prevent auto-submission when queue reaches batch size
        mockNetworkMonitor.isConnected = false

        // When - Add more than max events
        for i in 0 ..< (maxQueueSize + 10) {
            sut.track(event: .userLogin, properties: ["index": i])
        }

        // Then - Queue should be capped at max size
        XCTAssertEqual(sut.eventQueueCount, maxQueueSize, "Queue should be capped at max size")
    }

    func testTrackEvent_DropsOldestEventsWhenQueueFull() {
        // Given
        let maxQueueSize = sut.maxQueueSize

        // Disable network to prevent auto-submission when queue reaches batch size
        mockNetworkMonitor.isConnected = false

        // Add max events
        for i in 0 ..< maxQueueSize {
            sut.track(event: .userLogin, properties: ["index": i])
        }

        // When - Add one more event
        sut.track(event: .userLogout, properties: ["index": maxQueueSize])

        // Then - Queue should still be at max size
        XCTAssertEqual(sut.eventQueueCount, maxQueueSize)
    }

    // MARK: - Event Persistence Tests

    func testPersistEvents_SavesEventsToUserDefaults() {
        // Given
        sut.track(event: .userLogin, properties: ["email_domain": "test.com"])
        sut.track(event: .testStarted, properties: ["session_id": 123])

        // When
        sut.testPersistEvents()

        // Then - Events should be persisted
        let data = mockUserDefaults.data(forKey: AnalyticsService.storageKey)
        XCTAssertNotNil(data, "Events should be persisted to UserDefaults")

        // Verify we can decode the events
        guard let persistedData = data else {
            XCTFail("Data should not be nil")
            return
        }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let events = try? decoder.decode([AnalyticsEventData].self, from: persistedData)
        XCTAssertEqual(events?.count, 2, "Should persist 2 events")
    }

    func testPersistEvents_RemovesKeyWhenQueueEmpty() {
        // Given - Add and then remove all events
        sut.track(event: .userLogin)
        sut.testPersistEvents()
        XCTAssertNotNil(mockUserDefaults.data(forKey: AnalyticsService.storageKey))

        // When - Clear queue and persist
        sut.testClearQueue()
        sut.testPersistEvents()

        // Then - Key should be removed
        XCTAssertNil(mockUserDefaults.data(forKey: AnalyticsService.storageKey))
    }

    func testLoadPersistedEvents_RestoresEventsFromUserDefaults() {
        // Given - Persist some events manually
        let events = [
            AnalyticsEventData(
                eventName: "user.login",
                timestamp: Date(),
                properties: ["email_domain": AnyCodable("test.com")]
            ),
            AnalyticsEventData(
                eventName: "test.started",
                timestamp: Date(),
                properties: ["session_id": AnyCodable(123)]
            )
        ]

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try! encoder.encode(events)
        mockUserDefaults.set(data, forKey: AnalyticsService.storageKey)

        // When - Create a new service that will load persisted events
        let newService = AnalyticsService(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false
        )

        // Then - Events should be loaded
        XCTAssertEqual(newService.eventQueueCount, 2, "Should load 2 persisted events")
    }

    func testLoadPersistedEvents_HandlesMalformedData() {
        // Given - Store malformed data
        let malformedData = "not valid json".data(using: .utf8)!
        mockUserDefaults.set(malformedData, forKey: AnalyticsService.storageKey)

        // When - Create a new service that will try to load persisted events
        let newService = AnalyticsService(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false
        )

        // Then - Should handle gracefully (empty queue)
        XCTAssertEqual(newService.eventQueueCount, 0, "Should have empty queue after malformed data")
        // Malformed data should be cleared
        XCTAssertNil(mockUserDefaults.data(forKey: AnalyticsService.storageKey))
    }

    // MARK: - Network Connectivity Tests

    func testSubmitBatch_SkipsWhenOffline() async {
        // Given
        sut.track(event: .userLogin)
        mockNetworkMonitor.isConnected = false

        // When
        await sut.testSubmitBatch()

        // Then - Events should remain in queue
        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain when offline")
    }

    func testSubmitBatch_SubmitsWhenOnline() async {
        // Given
        sut.track(event: .userLogin)
        mockNetworkMonitor.isConnected = true

        MockURLProtocol.requestHandler = { _ in
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When
        await sut.testSubmitBatch()

        // Then - Events should be submitted and removed
        XCTAssertEqual(sut.eventQueueCount, 0, "Events should be removed after submission")
    }

    // MARK: - Batch Submission Tests

    func testSubmitBatch_BatchesEventsCorrectly() async {
        // Create a separate SUT with autoSubmitWhenFull disabled to prevent race conditions
        let testSut = AnalyticsService(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false,
            autoSubmitWhenFull: false
        )

        // Given - Add more events than max batch size
        let maxBatchSize = testSut.maxBatchSize
        for i in 0 ..< (maxBatchSize + 10) {
            testSut.track(event: .userLogin, properties: ["index": i])
        }

        // Set up mock handler
        var requestCount = 0
        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 50, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When - Submit batch (should only submit maxBatchSize events)
        await testSut.testSubmitBatch()

        // Then
        XCTAssertEqual(requestCount, 1, "Should make exactly one request")
        XCTAssertEqual(testSut.eventQueueCount, 10, "Should have 10 events remaining")
    }

    func testSubmitBatch_IncludesCorrectMetadata() async {
        // Given
        sut.track(event: .userLogin)

        var capturedRequest: URLRequest?
        MockURLProtocol.requestHandler = { request in
            capturedRequest = request
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When
        await sut.testSubmitBatch()

        // Then
        XCTAssertNotNil(capturedRequest)
        XCTAssertEqual(capturedRequest?.value(forHTTPHeaderField: "X-Platform"), "iOS")
        XCTAssertNotNil(capturedRequest?.value(forHTTPHeaderField: "X-App-Version"))
        XCTAssertEqual(capturedRequest?.value(forHTTPHeaderField: "Content-Type"), "application/json")
    }

    func testSubmitBatch_PreventsRaceConditions() async {
        // Given
        for i in 0 ..< 10 {
            sut.track(event: .userLogin, properties: ["index": i])
        }

        var requestCount = 0
        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            // Add a small delay to simulate network latency
            Thread.sleep(forTimeInterval: 0.1)
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 10, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When - Try to submit multiple times concurrently
        async let submission1: Void = sut.testSubmitBatch()
        async let submission2: Void = sut.testSubmitBatch()
        async let submission3: Void = sut.testSubmitBatch()
        _ = await (submission1, submission2, submission3)

        // Then - Only one request should go through due to isSubmitting flag
        XCTAssertEqual(requestCount, 1, "Only one submission should proceed")
    }

    // MARK: - Retry Logic Tests

    func testSubmitWithRetry_RetriesOnFailure() async {
        // Given
        sut.track(event: .userLogin)

        var attemptCount = 0
        MockURLProtocol.requestHandler = { _ in
            attemptCount += 1
            if attemptCount < 3 {
                throw NSError(domain: "TestError", code: -1, userInfo: nil)
            }
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When
        await sut.testSubmitBatch()

        // Then - Should have retried and eventually succeeded
        XCTAssertEqual(attemptCount, 3, "Should retry until success")
        XCTAssertEqual(sut.eventQueueCount, 0, "Events should be removed after successful retry")
    }

    func testSubmitWithRetry_GivesUpAfterMaxRetries() async {
        // Given
        sut.track(event: .userLogin)
        let maxRetries = sut.maxRetries

        var attemptCount = 0
        MockURLProtocol.requestHandler = { _ in
            attemptCount += 1
            throw NSError(domain: "TestError", code: -1, userInfo: nil)
        }

        // When
        await sut.testSubmitBatch()

        // Then - Should give up after max retries
        XCTAssertEqual(attemptCount, maxRetries, "Should attempt exactly maxRetries times")
        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain in queue after all retries fail")
    }

    func testSubmitWithRetry_ExponentialBackoff() async {
        // Given
        sut.track(event: .userLogin)

        var attemptTimes: [Date] = []
        MockURLProtocol.requestHandler = { _ in
            attemptTimes.append(Date())
            if attemptTimes.count < 3 {
                throw NSError(domain: "TestError", code: -1, userInfo: nil)
            }
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When
        await sut.testSubmitBatch()

        // Then - Verify exponential backoff timing (1s, 2s)
        XCTAssertEqual(attemptTimes.count, 3, "Should have 3 attempts")

        if attemptTimes.count >= 3 {
            let firstDelay = attemptTimes[1].timeIntervalSince(attemptTimes[0])
            let secondDelay = attemptTimes[2].timeIntervalSince(attemptTimes[1])

            // Allow some tolerance for timing
            XCTAssertGreaterThan(firstDelay, 0.9, "First delay should be ~1s")
            XCTAssertLessThan(firstDelay, 1.5, "First delay should be ~1s")
            XCTAssertGreaterThan(secondDelay, 1.9, "Second delay should be ~2s")
            XCTAssertLessThan(secondDelay, 2.5, "Second delay should be ~2s")
        }
    }

    // MARK: - HTTP Error Handling Tests

    func testSubmitBatch_Handles401Unauthorized() async {
        // Given
        sut.track(event: .userLogin)

        var attemptCount = 0
        MockURLProtocol.requestHandler = { _ in
            attemptCount += 1
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 401,
                httpVersion: nil,
                headerFields: nil
            )!
            return (response, Data())
        }

        // When
        await sut.testSubmitBatch()

        // Then - Should retry on 401
        XCTAssertEqual(attemptCount, sut.maxRetries, "Should retry on 401")
        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain in queue")
    }

    func testSubmitBatch_Handles500ServerError() async {
        // Given
        sut.track(event: .userLogin)

        var attemptCount = 0
        MockURLProtocol.requestHandler = { _ in
            attemptCount += 1
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 500,
                httpVersion: nil,
                headerFields: nil
            )!
            return (response, Data())
        }

        // When
        await sut.testSubmitBatch()

        // Then - Should retry on 500
        XCTAssertEqual(attemptCount, sut.maxRetries, "Should retry on 500")
        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain in queue")
    }

    // MARK: - Auth Token Tests

    func testSubmitBatch_IncludesAuthTokenWhenAvailable() async {
        // Given
        sut.track(event: .userLogin)
        try? mockSecureStorage.save("test_token_123", forKey: SecureStorageKey.accessToken.rawValue)

        var authorizationHeader: String?
        MockURLProtocol.requestHandler = { request in
            authorizationHeader = request.value(forHTTPHeaderField: "Authorization")
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When
        await sut.testSubmitBatch()

        // Then
        XCTAssertEqual(authorizationHeader, "Bearer test_token_123")
    }

    func testSubmitBatch_WorksWithoutAuthToken() async {
        // Given
        sut.track(event: .userLogin)
        // No auth token set in secure storage

        var authorizationHeader: String?
        MockURLProtocol.requestHandler = { request in
            authorizationHeader = request.value(forHTTPHeaderField: "Authorization")
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When
        await sut.testSubmitBatch()

        // Then
        XCTAssertNil(authorizationHeader, "Should not include Authorization header when no token")
        XCTAssertEqual(sut.eventQueueCount, 0, "Events should be submitted successfully")
    }

    // MARK: - Thread Safety Tests

    func testConcurrentEventTracking_ThreadSafety() async {
        // Given
        let iterations = 100
        let expectation = expectation(description: "All events tracked")
        expectation.expectedFulfillmentCount = iterations

        // When - Track events concurrently
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                self.sut.track(event: .userLogin, properties: ["index": i])
                expectation.fulfill()
            }
        }

        // Then
        await fulfillment(of: [expectation], timeout: 5.0)
        XCTAssertEqual(sut.eventQueueCount, iterations, "All events should be tracked")
    }

    func testConcurrentPersistence_ThreadSafety() async {
        // Given - Disable network to prevent auto-batch submission from clearing the queue
        mockNetworkMonitor.isConnected = false

        for i in 0 ..< 50 {
            sut.track(event: .userLogin, properties: ["index": i])
        }

        let iterations = 10
        let expectation = expectation(description: "All persistence operations complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Call persist concurrently
        for _ in 0 ..< iterations {
            DispatchQueue.global().async {
                self.sut.testPersistEvents()
                expectation.fulfill()
            }
        }

        // Then
        await fulfillment(of: [expectation], timeout: 5.0)

        // Verify data is still consistent
        let data = mockUserDefaults.data(forKey: AnalyticsService.storageKey)
        XCTAssertNotNil(data)

        guard let persistedData = data else {
            XCTFail("Data should not be nil")
            return
        }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let events = try? decoder.decode([AnalyticsEventData].self, from: persistedData)
        XCTAssertEqual(events?.count, 50, "Persisted data should be consistent")
    }

    // MARK: - Flush Tests

    func testFlush_SubmitsAllPendingEvents() async {
        // Given
        for i in 0 ..< 10 {
            sut.track(event: .userLogin, properties: ["index": i])
        }

        MockURLProtocol.requestHandler = { _ in
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = """
            {"success": true, "events_received": 10, "message": "Success"}
            """.data(using: .utf8)!
            return (response, responseData)
        }

        // When
        await sut.flush()

        // Then
        XCTAssertEqual(sut.eventQueueCount, 0, "Flush should submit all events")
    }

    // MARK: - Certificate Pinning Analytics Tests

    func testTrackCertificatePinningInitialized_TracksSuccessWithDomainAndPinCount() {
        // Given
        let domain = "aiq-backend-production.up.railway.app"
        let pinCount = 2

        // When
        sut.trackCertificatePinningInitialized(domain: domain, pinCount: pinCount)

        // Then
        XCTAssertEqual(sut.eventQueueCount, 1, "Should track certificate pinning initialized event")
    }

    func testTrackCertificatePinningInitializationFailed_TracksFailureWithReason() {
        // Given
        let reason = "TrustKit.plist missing or invalid format"

        // When
        sut.trackCertificatePinningInitializationFailed(reason: reason)

        // Then
        XCTAssertEqual(sut.eventQueueCount, 1, "Should track certificate pinning initialization failure")
    }

    func testTrackCertificatePinningInitializationFailed_TracksFailureWithReasonAndDomain() {
        // Given
        let reason = "TSKPublicKeyHashes missing"
        let domain = "aiq-backend-production.up.railway.app"

        // When
        sut.trackCertificatePinningInitializationFailed(reason: reason, domain: domain)

        // Then
        XCTAssertEqual(sut.eventQueueCount, 1, "Should track certificate pinning initialization failure with domain")
    }

    func testTrackCertificatePinningInitializationFailed_TracksInsufficientPins() {
        // Given
        let reason = "Insufficient pins (found 1, need 2)"
        let domain = "aiq-backend-production.up.railway.app"

        // When
        sut.trackCertificatePinningInitializationFailed(reason: reason, domain: domain)

        // Then
        XCTAssertEqual(sut.eventQueueCount, 1, "Should track insufficient pins error")
    }

    func testCertificatePinningEvents_HaveCorrectEventNames() {
        // Given/When
        sut.trackCertificatePinningInitialized(domain: "test.com", pinCount: 2)
        sut.trackCertificatePinningInitializationFailed(reason: "test failure")

        // Then
        XCTAssertEqual(sut.eventQueueCount, 2, "Should track both events")

        // Verify event names by checking if they're defined in AnalyticsEvent enum
        XCTAssertEqual(
            AnalyticsEvent.certificatePinningInitialized.rawValue,
            "security.certificate_pinning.initialized",
            "Event name should match expected format"
        )
        XCTAssertEqual(
            AnalyticsEvent.certificatePinningInitializationFailed.rawValue,
            "security.certificate_pinning.initialization_failed",
            "Event name should match expected format"
        )
    }
}
