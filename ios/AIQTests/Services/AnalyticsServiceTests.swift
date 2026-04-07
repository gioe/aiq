@testable import AIQ
import AIQSharedKit
import XCTest

final class FirebaseAnalyticsProviderTests: XCTestCase {
    var sut: FirebaseAnalyticsProvider!
    var mockNetworkMonitor: MockNetworkMonitor!
    var mockUserDefaults: UserDefaults!
    var mockURLSession: URLSession!
    var mockSecureStorage: MockSecureStorage!

    override func setUp() {
        super.setUp()

        mockNetworkMonitor = MockNetworkMonitor(isConnected: true)
        mockUserDefaults = UserDefaults(suiteName: "com.aiq.tests")!
        mockUserDefaults.removePersistentDomain(forName: "com.aiq.tests")
        mockSecureStorage = MockSecureStorage()

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        mockURLSession = URLSession(configuration: config)

        sut = FirebaseAnalyticsProvider(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false
        )
    }

    override func tearDown() {
        MockURLProtocol.requestHandler = nil
        mockUserDefaults.removePersistentDomain(forName: "com.aiq.tests")
        super.tearDown()
    }

    // MARK: - Helpers

    private func event(_ type: AIQAnalyticsEvent, parameters: [String: Any]? = nil) -> AnalyticsEvent {
        AnalyticsEvent(name: type.rawValue, parameters: parameters)
    }

    // MARK: - Event Tracking Tests

    func testTrackEvent_AddsEventToQueue() {
        sut.track(event(.userLogin, parameters: ["email_domain": "example.com"]))
        XCTAssertEqual(sut.eventQueueCount, 1, "Event should be added to queue")
    }

    func testTrackEvent_WithoutProperties() {
        sut.track(event(.userLogout))
        XCTAssertEqual(sut.eventQueueCount, 1)
    }

    func testTrackEvent_MultipleEvents() {
        sut.track(event(.userLogin))
        sut.track(event(.testStarted, parameters: ["session_id": 123]))
        sut.track(event(.testCompleted, parameters: ["session_id": 123, "iq_score": 120]))
        XCTAssertEqual(sut.eventQueueCount, 3)
    }

    func testTrackEvent_EnforcesMaxQueueSize() {
        let maxQueueSize = sut.maxQueueSize
        mockNetworkMonitor.isConnected = false

        for i in 0 ..< (maxQueueSize + 10) {
            sut.track(event(.userLogin, parameters: ["index": i]))
        }

        XCTAssertEqual(sut.eventQueueCount, maxQueueSize, "Queue should be capped at max size")
    }

    func testTrackEvent_DropsOldestEventsWhenQueueFull() {
        let maxQueueSize = sut.maxQueueSize
        mockNetworkMonitor.isConnected = false

        for i in 0 ..< maxQueueSize {
            sut.track(event(.userLogin, parameters: ["index": i]))
        }

        sut.track(event(.userLogout, parameters: ["index": maxQueueSize]))
        XCTAssertEqual(sut.eventQueueCount, maxQueueSize)
    }

    // MARK: - Event Persistence Tests

    func testPersistEvents_SavesEventsToUserDefaults() {
        sut.track(event(.userLogin, parameters: ["email_domain": "test.com"]))
        sut.track(event(.testStarted, parameters: ["session_id": 123]))

        sut.testPersistEvents()

        let data = mockUserDefaults.data(forKey: FirebaseAnalyticsProvider.storageKey)
        XCTAssertNotNil(data, "Events should be persisted to UserDefaults")

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
        sut.track(event(.userLogin))
        sut.testPersistEvents()
        XCTAssertNotNil(mockUserDefaults.data(forKey: FirebaseAnalyticsProvider.storageKey))

        sut.testClearQueue()
        sut.testPersistEvents()

        XCTAssertNil(mockUserDefaults.data(forKey: FirebaseAnalyticsProvider.storageKey))
    }

    func testLoadPersistedEvents_RestoresEventsFromUserDefaults() throws {
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
        let data = try encoder.encode(events)
        mockUserDefaults.set(data, forKey: FirebaseAnalyticsProvider.storageKey)

        let newProvider = FirebaseAnalyticsProvider(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false
        )

        XCTAssertEqual(newProvider.eventQueueCount, 2, "Should load 2 persisted events")
    }

    func testLoadPersistedEvents_HandlesMalformedData() throws {
        let malformedData = try XCTUnwrap("not valid json".data(using: .utf8))
        mockUserDefaults.set(malformedData, forKey: FirebaseAnalyticsProvider.storageKey)

        let newProvider = FirebaseAnalyticsProvider(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false
        )

        XCTAssertEqual(newProvider.eventQueueCount, 0, "Should have empty queue after malformed data")
        XCTAssertNil(mockUserDefaults.data(forKey: FirebaseAnalyticsProvider.storageKey))
    }

    // MARK: - Network Connectivity Tests

    func testSubmitBatch_SkipsWhenOffline() async {
        sut.track(event(.userLogin))
        mockNetworkMonitor.isConnected = false

        await sut.testSubmitBatch()

        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain when offline")
    }

    func testSubmitBatch_SkipsRequestWhenQueueEmpty() async {
        var requestMade = false
        MockURLProtocol.requestHandler = { _ in
            requestMade = true
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 0, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertFalse(requestMade, "Should not make network request for empty queue")
        XCTAssertEqual(sut.eventQueueCount, 0, "Queue should remain empty")
    }

    func testSubmitBatch_SubmitsWhenOnline() async {
        sut.track(event(.userLogin))
        mockNetworkMonitor.isConnected = true

        MockURLProtocol.requestHandler = { _ in
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertEqual(sut.eventQueueCount, 0, "Events should be removed after submission")
    }

    // MARK: - Batch Submission Tests

    func testSubmitBatch_BatchesEventsCorrectly() async {
        let testSut = FirebaseAnalyticsProvider(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false,
            autoSubmitWhenFull: false
        )

        let maxBatchSize = testSut.maxBatchSize
        for i in 0 ..< (maxBatchSize + 10) {
            testSut.track(event(.userLogin, parameters: ["index": i]))
        }

        var requestCount = 0
        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 50, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await testSut.testSubmitBatch()

        XCTAssertEqual(requestCount, 1, "Should make exactly one request")
        XCTAssertEqual(testSut.eventQueueCount, 10, "Should have 10 events remaining")
    }

    func testAutoSubmitWhenFull_SubmitsWhenBufferReachesCapacity() async {
        let testSut = FirebaseAnalyticsProvider(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false,
            autoSubmitWhenFull: true
        )

        let submissionExpectation = expectation(description: "Auto-submission occurs")
        var requestCount = 0
        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            submissionExpectation.fulfill()
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 50, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        let maxBatchSize = testSut.maxBatchSize
        for i in 0 ..< maxBatchSize {
            testSut.track(event(.userLogin, parameters: ["index": i]))
        }

        await fulfillment(of: [submissionExpectation], timeout: 2.0)
        XCTAssertGreaterThanOrEqual(requestCount, 1, "Should auto-submit when buffer reaches capacity")
    }

    func testSubmitBatch_IncludesCorrectMetadata() async {
        sut.track(event(.userLogin))

        var capturedRequest: URLRequest?
        MockURLProtocol.requestHandler = { request in
            capturedRequest = request
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertNotNil(capturedRequest)
        XCTAssertEqual(capturedRequest?.value(forHTTPHeaderField: "X-Platform"), "iOS")
        XCTAssertNotNil(capturedRequest?.value(forHTTPHeaderField: "X-App-Version"))
        XCTAssertEqual(capturedRequest?.value(forHTTPHeaderField: "Content-Type"), "application/json")
    }

    func testSubmitBatch_PreventsRaceConditions() async {
        for i in 0 ..< 10 {
            sut.track(event(.userLogin, parameters: ["index": i]))
        }

        var requestCount = 0
        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            Thread.sleep(forTimeInterval: 0.1)
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 10, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        async let submission1: Void = sut.testSubmitBatch()
        async let submission2: Void = sut.testSubmitBatch()
        async let submission3: Void = sut.testSubmitBatch()
        _ = await (submission1, submission2, submission3)

        XCTAssertEqual(requestCount, 1, "Only one submission should proceed")
    }

    // MARK: - Retry Logic Tests

    func testSubmitWithRetry_RetriesOnFailure() async {
        sut.track(event(.userLogin))

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
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertEqual(attemptCount, 3, "Should retry until success")
        XCTAssertEqual(sut.eventQueueCount, 0, "Events should be removed after successful retry")
    }

    func testSubmitWithRetry_GivesUpAfterMaxRetries() async {
        sut.track(event(.userLogin))
        let maxRetries = sut.maxRetries

        var attemptCount = 0
        MockURLProtocol.requestHandler = { _ in
            attemptCount += 1
            throw NSError(domain: "TestError", code: -1, userInfo: nil)
        }

        await sut.testSubmitBatch()

        XCTAssertEqual(attemptCount, maxRetries, "Should attempt exactly maxRetries times")
        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain in queue after all retries fail")
    }

    func testSubmitWithRetry_ExponentialBackoff() async {
        sut.track(event(.userLogin))

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
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertEqual(attemptTimes.count, 3, "Should have 3 attempts")

        if attemptTimes.count >= 3 {
            let firstDelay = attemptTimes[1].timeIntervalSince(attemptTimes[0])
            let secondDelay = attemptTimes[2].timeIntervalSince(attemptTimes[1])

            XCTAssertGreaterThan(firstDelay, 0.5, "First delay should be ~1s")
            XCTAssertLessThan(firstDelay, 2.0, "First delay should be ~1s")
            XCTAssertGreaterThan(secondDelay, 1.5, "Second delay should be ~2s")
            XCTAssertLessThan(secondDelay, 3.0, "Second delay should be ~2s")
        }
    }

    // MARK: - HTTP Error Handling Tests

    func testSubmitBatch_Handles401Unauthorized() async {
        sut.track(event(.userLogin))

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

        await sut.testSubmitBatch()

        XCTAssertEqual(attemptCount, sut.maxRetries, "Should retry on 401")
        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain in queue")
    }

    func testSubmitBatch_Handles500ServerError() async {
        sut.track(event(.userLogin))

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

        await sut.testSubmitBatch()

        XCTAssertEqual(attemptCount, sut.maxRetries, "Should retry on 500")
        XCTAssertEqual(sut.eventQueueCount, 1, "Events should remain in queue")
    }

    // MARK: - Auth Token Tests

    func testSubmitBatch_IncludesAuthTokenWhenAvailable() async {
        sut.track(event(.userLogin))
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
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertEqual(authorizationHeader, "Bearer test_token_123")
    }

    func testSubmitBatch_WorksWithoutAuthToken() async {
        sut.track(event(.userLogin))

        var authorizationHeader: String?
        MockURLProtocol.requestHandler = { request in
            authorizationHeader = request.value(forHTTPHeaderField: "Authorization")
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertNil(authorizationHeader, "Should not include Authorization header when no token")
        XCTAssertEqual(sut.eventQueueCount, 0, "Events should be submitted successfully")
    }

    func testSubmitBatch_HandlesSecureStorageRetrievalError() async {
        sut.track(event(.userLogin))
        mockSecureStorage.shouldThrowOnRetrieve = true

        var authorizationHeader: String?
        var requestMade = false
        MockURLProtocol.requestHandler = { request in
            requestMade = true
            authorizationHeader = request.value(forHTTPHeaderField: "Authorization")
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 1, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.testSubmitBatch()

        XCTAssertTrue(requestMade, "Request should be made even when secure storage throws")
        XCTAssertNil(authorizationHeader, "Should not include Authorization header when retrieval throws")
        XCTAssertEqual(sut.eventQueueCount, 0, "Events should be submitted successfully without auth token")
    }

    // MARK: - Thread Safety Tests

    func testConcurrentEventTracking_ThreadSafety() async {
        let testSut = FirebaseAnalyticsProvider(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor,
            urlSession: mockURLSession,
            secureStorage: mockSecureStorage,
            batchInterval: 1000.0,
            startTimer: false,
            autoSubmitWhenFull: false
        )

        let iterations = 100
        let expectation = expectation(description: "All events tracked")
        expectation.expectedFulfillmentCount = iterations

        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                testSut.track(self.event(.userLogin, parameters: ["index": i]))
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 5.0)
        XCTAssertEqual(testSut.eventQueueCount, iterations, "All events should be tracked")
    }

    func testConcurrentPersistence_ThreadSafety() async {
        mockNetworkMonitor.isConnected = false

        for i in 0 ..< 50 {
            sut.track(event(.userLogin, parameters: ["index": i]))
        }

        let iterations = 10
        let expectation = expectation(description: "All persistence operations complete")
        expectation.expectedFulfillmentCount = iterations

        for _ in 0 ..< iterations {
            DispatchQueue.global().async {
                self.sut.testPersistEvents()
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 5.0)

        let data = mockUserDefaults.data(forKey: FirebaseAnalyticsProvider.storageKey)
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
        for i in 0 ..< 10 {
            sut.track(event(.userLogin, parameters: ["index": i]))
        }

        MockURLProtocol.requestHandler = { _ in
            let response = HTTPURLResponse(
                url: URL(string: "https://test.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            let responseData = try XCTUnwrap("""
            {"success": true, "events_received": 10, "message": "Success"}
            """.data(using: .utf8))
            return (response, responseData)
        }

        await sut.flush()

        XCTAssertEqual(sut.eventQueueCount, 0, "Flush should submit all events")
    }

    // MARK: - Certificate Pinning Analytics Tests

    func testTrackCertificatePinningInitialized_TracksSuccessWithDomainAndPinCount() {
        sut.track(event(.certificatePinningInitialized, parameters: [
            "domain": "aiq-backend-production.up.railway.app",
            "pin_count": 2
        ]))

        XCTAssertEqual(sut.eventQueueCount, 1, "Should track certificate pinning initialized event")
    }

    func testTrackCertificatePinningInitializationFailed_TracksFailureWithReason() {
        sut.track(event(.certificatePinningInitializationFailed, parameters: [
            "reason": "TrustKit.plist missing or invalid format"
        ]))

        XCTAssertEqual(sut.eventQueueCount, 1, "Should track certificate pinning initialization failure")
    }

    func testCertificatePinningEvents_HaveCorrectEventNames() {
        XCTAssertEqual(
            AIQAnalyticsEvent.certificatePinningInitialized.rawValue,
            "security.certificate_pinning.initialized",
            "Event name should match expected format"
        )
        XCTAssertEqual(
            AIQAnalyticsEvent.certificatePinningInitializationFailed.rawValue,
            "security.certificate_pinning.initialization_failed",
            "Event name should match expected format"
        )
    }

    // MARK: - Reset Tests

    func testReset_ClearsQueueAndPersistedData() {
        sut.track(event(.userLogin))
        sut.track(event(.testStarted))
        sut.testPersistEvents()

        XCTAssertEqual(sut.eventQueueCount, 2)
        XCTAssertNotNil(mockUserDefaults.data(forKey: FirebaseAnalyticsProvider.storageKey))

        sut.reset()

        XCTAssertEqual(sut.eventQueueCount, 0, "Queue should be cleared")
        XCTAssertNil(mockUserDefaults.data(forKey: FirebaseAnalyticsProvider.storageKey), "Persisted data should be cleared")
    }
}
