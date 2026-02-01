@testable import AIQ
import XCTest

final class LocalAnswerStorageTests: XCTestCase {
    var sut: LocalAnswerStorage!
    var testUserDefaults: UserDefaults!
    let testSuiteName = "com.aiq.tests.localStorage"

    override func setUp() {
        super.setUp()

        // Create test-specific UserDefaults suite to avoid interfering with production data
        testUserDefaults = UserDefaults(suiteName: testSuiteName)!
        sut = LocalAnswerStorage(userDefaults: testUserDefaults)

        // Clean up any existing test data
        sut.clearProgress()
    }

    override func tearDown() {
        sut.clearProgress()
        testUserDefaults.removePersistentDomain(forName: testSuiteName)
        super.tearDown()
    }

    // MARK: - Helper Methods

    private func createTestProgress(
        sessionId: Int = 123,
        userId: Int = 456,
        questionIds: [Int] = [1, 2, 3, 4, 5],
        userAnswers: [Int: String] = [1: "A", 2: "B"],
        currentQuestionIndex: Int = 2,
        savedAt: Date = Date(),
        sessionStartedAt: Date? = Date()
    ) -> SavedTestProgress {
        SavedTestProgress(
            sessionId: sessionId,
            userId: userId,
            questionIds: questionIds,
            userAnswers: userAnswers,
            currentQuestionIndex: currentQuestionIndex,
            savedAt: savedAt,
            sessionStartedAt: sessionStartedAt,
            stimulusSeen: []
        )
    }

    // MARK: - Save Operation Tests

    func testSaveProgress_Success() throws {
        // Given
        let progress = createTestProgress()

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Progress should be saved")
        XCTAssertEqual(loaded?.sessionId, progress.sessionId)
        XCTAssertEqual(loaded?.userId, progress.userId)
        XCTAssertEqual(loaded?.questionIds, progress.questionIds)
        XCTAssertEqual(loaded?.userAnswers, progress.userAnswers)
        XCTAssertEqual(loaded?.currentQuestionIndex, progress.currentQuestionIndex)
    }

    func testSaveProgress_OverwritesExisting() throws {
        // Given
        let initialProgress = createTestProgress(sessionId: 123, currentQuestionIndex: 2)
        let updatedProgress = createTestProgress(sessionId: 456, currentQuestionIndex: 4)

        // When
        try sut.saveProgress(initialProgress)
        try sut.saveProgress(updatedProgress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertEqual(loaded?.sessionId, 456, "Should overwrite with new session ID")
        XCTAssertEqual(loaded?.currentQuestionIndex, 4, "Should overwrite with new progress")
    }

    func testSaveProgress_WithEmptyAnswers() throws {
        // Given
        let progress = createTestProgress(userAnswers: [:])

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Progress with empty answers should be saved")
        XCTAssertEqual(loaded?.userAnswers.count, 0, "Should have zero answers")
    }

    func testSaveProgress_WithLargeNumberOfQuestions() throws {
        // Given
        let questionIds = Array(1 ... 100)
        var userAnswers: [Int: String] = [:]
        for i in 1 ... 100 {
            userAnswers[i] = "Answer_\(i)"
        }
        let progress = createTestProgress(
            questionIds: questionIds,
            userAnswers: userAnswers,
            currentQuestionIndex: 50
        )

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Large progress should be saved")
        XCTAssertEqual(loaded?.questionIds.count, 100)
        XCTAssertEqual(loaded?.userAnswers.count, 100)
    }

    func testSaveProgress_DataEncoding() throws {
        // Given
        let progress = createTestProgress()

        // When
        try sut.saveProgress(progress)

        // Then - Verify data is actually stored in UserDefaults
        let data = testUserDefaults.data(forKey: "com.aiq.savedTestProgress")
        XCTAssertNotNil(data, "Data should be stored in UserDefaults")

        // Verify it's valid JSON
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(SavedTestProgress.self, from: data!)
        XCTAssertEqual(decoded.sessionId, progress.sessionId)
    }

    // MARK: - Load Operation Tests

    func testLoadProgress_ReturnsNilWhenNoProgress() {
        // Given - no saved progress

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNil(loaded, "Should return nil when no progress exists")
    }

    func testLoadProgress_ReturnsSavedProgress() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNotNil(loaded, "Should return saved progress")
        XCTAssertEqual(loaded?.sessionId, progress.sessionId)
        XCTAssertEqual(loaded?.userId, progress.userId)
        XCTAssertEqual(loaded?.questionIds, progress.questionIds)
        XCTAssertEqual(loaded?.userAnswers, progress.userAnswers)
        XCTAssertEqual(loaded?.currentQuestionIndex, progress.currentQuestionIndex)
    }

    func testLoadProgress_ClearsInvalidData() throws {
        // Given - Invalid/corrupted JSON data
        let invalidData = try XCTUnwrap("invalid json".data(using: .utf8))
        testUserDefaults.set(invalidData, forKey: "com.aiq.savedTestProgress")

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNil(loaded, "Should return nil for invalid data")

        // Verify data was cleared
        let data = testUserDefaults.data(forKey: "com.aiq.savedTestProgress")
        XCTAssertNil(data, "Invalid data should be cleared")
    }

    func testLoadProgress_ClearsExpiredProgress() throws {
        // Given - Progress saved more than 24 hours ago
        let expiredDate = Date().addingTimeInterval(-25 * 60 * 60) // 25 hours ago
        let progress = createTestProgress(savedAt: expiredDate)
        try sut.saveProgress(progress)

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNil(loaded, "Should return nil for expired progress")

        // Verify data was cleared
        let data = testUserDefaults.data(forKey: "com.aiq.savedTestProgress")
        XCTAssertNil(data, "Expired data should be cleared")
    }

    func testLoadProgress_ReturnsValidProgressWithin24Hours() throws {
        // Given - Progress saved 23 hours ago
        let recentDate = Date().addingTimeInterval(-23 * 60 * 60) // 23 hours ago
        let progress = createTestProgress(savedAt: recentDate)
        try sut.saveProgress(progress)

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNotNil(loaded, "Should return valid progress within 24 hours")
        XCTAssertEqual(loaded?.sessionId, progress.sessionId)
    }

    func testLoadProgress_ReturnsNilAfterClear() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)
        sut.clearProgress()

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNil(loaded, "Should return nil after clearing")
    }

    func testLoadProgress_ExactlyAt24HourBoundary() throws {
        // Given - Progress saved exactly 24 hours ago
        let exactDate = Date().addingTimeInterval(-24 * 60 * 60)
        let progress = createTestProgress(savedAt: exactDate)
        try sut.saveProgress(progress)

        // When
        let loaded = sut.loadProgress()

        // Then - Should be cleared (savedAt must be > dayAgo, not >= dayAgo)
        XCTAssertNil(loaded, "Progress exactly at 24-hour boundary should be expired")
    }

    // MARK: - Clear Operation Tests

    func testClearProgress_RemovesExistingProgress() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)

        // When
        sut.clearProgress()

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNil(loaded, "Progress should be cleared")

        // Verify data is removed from UserDefaults
        let data = testUserDefaults.data(forKey: "com.aiq.savedTestProgress")
        XCTAssertNil(data, "Data should be removed from UserDefaults")
    }

    func testClearProgress_WhenNoProgressExists() {
        // Given - no saved progress

        // When/Then - Should not crash or throw
        sut.clearProgress()

        // Verify still no data
        let loaded = sut.loadProgress()
        XCTAssertNil(loaded, "Should remain empty after clearing empty storage")
    }

    func testClearProgress_AfterAlreadyCleared() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)
        sut.clearProgress()

        // When - Clear again
        sut.clearProgress()

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNil(loaded, "Should handle multiple clears gracefully")
    }

    // MARK: - HasProgress Tests

    func testHasProgress_ReturnsTrueWhenValidProgressExists() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)

        // When
        let hasProgress = sut.hasProgress()

        // Then
        XCTAssertTrue(hasProgress, "Should return true when valid progress exists")
    }

    func testHasProgress_ReturnsFalseWhenNoProgressExists() {
        // Given - no saved progress

        // When
        let hasProgress = sut.hasProgress()

        // Then
        XCTAssertFalse(hasProgress, "Should return false when no progress exists")
    }

    func testHasProgress_ReturnsFalseWhenProgressExpired() throws {
        // Given - Expired progress
        let expiredDate = Date().addingTimeInterval(-25 * 60 * 60) // 25 hours ago
        let progress = createTestProgress(savedAt: expiredDate)
        try sut.saveProgress(progress)

        // When
        let hasProgress = sut.hasProgress()

        // Then
        XCTAssertFalse(hasProgress, "Should return false when progress is expired")
    }

    func testHasProgress_ReturnsFalseAfterClear() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)
        sut.clearProgress()

        // When
        let hasProgress = sut.hasProgress()

        // Then
        XCTAssertFalse(hasProgress, "Should return false after clearing")
    }

    func testHasProgress_ReturnsFalseForInvalidData() throws {
        // Given - Invalid data
        let invalidData = try XCTUnwrap("invalid json".data(using: .utf8))
        testUserDefaults.set(invalidData, forKey: "com.aiq.savedTestProgress")

        // When
        let hasProgress = sut.hasProgress()

        // Then
        XCTAssertFalse(hasProgress, "Should return false for invalid data")
    }

    // MARK: - Data Persistence Tests

    func testPersistence_SurvivesInstanceRecreation() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)

        // When - Create a new instance with same UserDefaults suite
        let newInstance = LocalAnswerStorage(userDefaults: testUserDefaults)
        let loaded = newInstance.loadProgress()

        // Then
        XCTAssertNotNil(loaded, "Data should persist across instances")
        XCTAssertEqual(loaded?.sessionId, progress.sessionId)
        XCTAssertEqual(loaded?.userId, progress.userId)
    }

    func testPersistence_IsolatedByUserDefaultsSuite() throws {
        // Given
        let suite1 = UserDefaults(suiteName: "com.aiq.tests.suite1")!
        let suite2 = UserDefaults(suiteName: "com.aiq.tests.suite2")!

        let storage1 = LocalAnswerStorage(userDefaults: suite1)
        let storage2 = LocalAnswerStorage(userDefaults: suite2)

        let progress1 = createTestProgress(sessionId: 111)
        let progress2 = createTestProgress(sessionId: 222)

        // When
        try storage1.saveProgress(progress1)
        try storage2.saveProgress(progress2)

        // Then
        XCTAssertEqual(storage1.loadProgress()?.sessionId, 111, "Suite 1 should have its own data")
        XCTAssertEqual(storage2.loadProgress()?.sessionId, 222, "Suite 2 should have its own data")

        // Clean up
        storage1.clearProgress()
        storage2.clearProgress()
        suite1.removePersistentDomain(forName: "com.aiq.tests.suite1")
        suite2.removePersistentDomain(forName: "com.aiq.tests.suite2")
    }

    // MARK: - Error Handling Tests

    func testError_EncodingRobustness() {
        // Note: JSONEncoder.encode() should not fail for Codable types in normal circumstances.
        // SavedTestProgress conforms to Codable, so encoding should always succeed.
        // This test documents that the method throws, but in practice with valid Codable types,
        // encoding errors are not expected.

        // Given
        let progress = createTestProgress()

        // When/Then - Should not throw for valid Codable type
        XCTAssertNoThrow(try sut.saveProgress(progress), "Should not throw for valid Codable type")
    }

    func testError_DecodingInvalidData() throws {
        // Given - Data that looks like JSON but has wrong structure
        let invalidJSON = try XCTUnwrap("""
        {
            "wrongField": "wrongValue"
        }
        """.data(using: .utf8))
        testUserDefaults.set(invalidJSON, forKey: "com.aiq.savedTestProgress")

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNil(loaded, "Should return nil for invalid structure")

        // Verify invalid data was cleared
        let data = testUserDefaults.data(forKey: "com.aiq.savedTestProgress")
        XCTAssertNil(data, "Invalid data should be cleared")
    }

    // MARK: - Concurrent Access Tests

    func testConcurrentSave_ThreadSafety() {
        // Given
        let iterations = 100
        let expectation = expectation(description: "All saves complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Save concurrently from multiple threads
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                do {
                    let progress = self.createTestProgress(sessionId: i)
                    try self.sut.saveProgress(progress)
                    expectation.fulfill()
                } catch {
                    XCTFail("Concurrent save failed: \(error)")
                }
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // Verify a value is present (the last one saved wins)
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "A progress value should be saved")
    }

    func testConcurrentRead_ThreadSafety() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)

        let iterations = 100
        let expectation = expectation(description: "All reads complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Read concurrently from multiple threads
        for _ in 0 ..< iterations {
            DispatchQueue.global().async {
                let loaded = self.sut.loadProgress()
                XCTAssertNotNil(loaded, "Should load progress")
                XCTAssertEqual(loaded?.sessionId, progress.sessionId)
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)
    }

    func testConcurrentClear_ThreadSafety() throws {
        // Given
        let progress = createTestProgress()
        try sut.saveProgress(progress)

        let iterations = 100
        let expectation = expectation(description: "All clears complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Clear concurrently from multiple threads
        for _ in 0 ..< iterations {
            DispatchQueue.global().async {
                self.sut.clearProgress()
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // Verify progress is cleared
        let loaded = sut.loadProgress()
        XCTAssertNil(loaded, "Progress should be cleared")
    }

    func testConcurrentMixedOperations_ThreadSafety() {
        // Given
        let iterations = 50
        let expectation = expectation(description: "All operations complete")
        expectation.expectedFulfillmentCount = iterations * 4 // save, load, hasProgress, clear

        // When - Perform mixed operations concurrently
        for i in 0 ..< iterations {
            // Save
            DispatchQueue.global().async {
                do {
                    let progress = self.createTestProgress(sessionId: i)
                    try self.sut.saveProgress(progress)
                    expectation.fulfill()
                } catch {
                    XCTFail("Save failed: \(error)")
                }
            }

            // Load
            DispatchQueue.global().async {
                _ = self.sut.loadProgress()
                expectation.fulfill()
            }

            // HasProgress
            DispatchQueue.global().async {
                _ = self.sut.hasProgress()
                expectation.fulfill()
            }

            // Clear (occasionally)
            if i % 10 == 0 {
                DispatchQueue.global().async {
                    self.sut.clearProgress()
                    expectation.fulfill()
                }
            } else {
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)
    }

    func testConcurrentSaveAndLoad_ThreadSafety() {
        // Given
        let iterations = 100
        let expectation = expectation(description: "All operations complete")
        expectation.expectedFulfillmentCount = iterations * 2

        // When - Save and load concurrently
        for i in 0 ..< iterations {
            // Save
            DispatchQueue.global().async {
                do {
                    let progress = self.createTestProgress(sessionId: i)
                    try self.sut.saveProgress(progress)
                    expectation.fulfill()
                } catch {
                    XCTFail("Save failed: \(error)")
                }
            }

            // Load
            DispatchQueue.global().async {
                _ = self.sut.loadProgress()
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // Should not crash and should have some value
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Should have a progress value after concurrent operations")
    }

    // MARK: - Edge Cases

    func testEdgeCase_EmptyQuestionIds() throws {
        // Given
        let progress = createTestProgress(questionIds: [])

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Should save progress with empty question IDs")
        XCTAssertEqual(loaded?.questionIds.count, 0)
    }

    func testEdgeCase_NilSessionStartedAt() throws {
        // Given
        let progress = createTestProgress(sessionStartedAt: nil)

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Should save progress with nil sessionStartedAt")
        XCTAssertNil(loaded?.sessionStartedAt)
    }

    func testEdgeCase_CurrentQuestionIndexAtBoundary() throws {
        // Given
        let questionIds = [1, 2, 3, 4, 5]
        let progress = createTestProgress(
            questionIds: questionIds,
            currentQuestionIndex: questionIds.count - 1 // Last question
        )

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Should save progress at last question")
        XCTAssertEqual(loaded?.currentQuestionIndex, questionIds.count - 1)
    }

    func testEdgeCase_SpecialCharactersInAnswers() throws {
        // Given
        let answers = [
            1: "Test!@#$%^&*(){}[]|\\:;\"'<>,.?/~`",
            2: "Hello 世界 🌍 مرحبا",
            3: "Line1\nLine2\nLine3"
        ]
        let progress = createTestProgress(userAnswers: answers)

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Should save progress with special characters")
        XCTAssertEqual(loaded?.userAnswers, answers, "Should preserve special characters")
    }

    func testEdgeCase_VeryLongAnswer() throws {
        // Given
        let longAnswer = String(repeating: "A", count: 10000)
        let answers = [1: longAnswer]
        let progress = createTestProgress(userAnswers: answers)

        // When
        try sut.saveProgress(progress)

        // Then
        let loaded = sut.loadProgress()
        XCTAssertNotNil(loaded, "Should save progress with very long answer")
        XCTAssertEqual(loaded?.userAnswers[1], longAnswer, "Should preserve long answer")
    }

    func testEdgeCase_SavedAtJustUnderExpiration() throws {
        // Given - Progress saved 23 hours and 50 minutes ago (10-minute margin for test stability)
        let almostExpiredDate = Date().addingTimeInterval(-(23 * 60 * 60 + 50 * 60))
        let progress = createTestProgress(savedAt: almostExpiredDate)
        try sut.saveProgress(progress)

        // When
        let loaded = sut.loadProgress()

        // Then
        XCTAssertNotNil(loaded, "Progress well within 24 hours should still be valid")
    }

    // MARK: - Integration Tests

    func testRealWorldScenario_TestSessionProgress() throws {
        // Given - User starts a test session
        let sessionId = 12345
        let userId = 67890
        let questionIds = [101, 102, 103, 104, 105]

        // When - Save initial progress (no answers yet)
        let initialProgress = createTestProgress(
            sessionId: sessionId,
            userId: userId,
            questionIds: questionIds,
            userAnswers: [:],
            currentQuestionIndex: 0
        )
        try sut.saveProgress(initialProgress)

        // Then - Should be able to load initial progress
        var loaded = sut.loadProgress()
        XCTAssertNotNil(loaded)
        XCTAssertEqual(loaded?.currentQuestionIndex, 0)
        XCTAssertEqual(loaded?.userAnswers.count, 0)

        // When - User answers first question and saves
        let progressAfterFirst = createTestProgress(
            sessionId: sessionId,
            userId: userId,
            questionIds: questionIds,
            userAnswers: [101: "A"],
            currentQuestionIndex: 1
        )
        try sut.saveProgress(progressAfterFirst)

        // Then - Progress should be updated
        loaded = sut.loadProgress()
        XCTAssertEqual(loaded?.currentQuestionIndex, 1)
        XCTAssertEqual(loaded?.userAnswers.count, 1)

        // When - User answers multiple questions
        let progressMidTest = createTestProgress(
            sessionId: sessionId,
            userId: userId,
            questionIds: questionIds,
            userAnswers: [101: "A", 102: "B", 103: "C"],
            currentQuestionIndex: 3
        )
        try sut.saveProgress(progressMidTest)

        // Then - All progress should be saved
        loaded = sut.loadProgress()
        XCTAssertEqual(loaded?.currentQuestionIndex, 3)
        XCTAssertEqual(loaded?.userAnswers.count, 3)

        // When - User completes test (clear progress)
        sut.clearProgress()

        // Then - No progress should remain
        XCTAssertFalse(sut.hasProgress())
        XCTAssertNil(sut.loadProgress())
    }

    func testRealWorldScenario_AppRestart() throws {
        // Given - User is in middle of test
        let progress = createTestProgress(
            sessionId: 123,
            userId: 456,
            questionIds: [1, 2, 3, 4, 5],
            userAnswers: [1: "A", 2: "B"],
            currentQuestionIndex: 2
        )
        try sut.saveProgress(progress)

        // When - App restarts (simulate with new instance)
        let newSut = LocalAnswerStorage(userDefaults: testUserDefaults)
        let loaded = newSut.loadProgress()

        // Then - Progress should be restored
        XCTAssertNotNil(loaded, "Progress should survive app restart")
        XCTAssertEqual(loaded?.sessionId, 123)
        XCTAssertEqual(loaded?.currentQuestionIndex, 2)
        XCTAssertEqual(loaded?.userAnswers.count, 2)
    }

    func testRealWorldScenario_ProgressExpiration() throws {
        // Given - User saved progress yesterday
        let yesterday = Date().addingTimeInterval(-25 * 60 * 60) // 25 hours ago
        let oldProgress = createTestProgress(savedAt: yesterday)
        try sut.saveProgress(oldProgress)

        // When - User opens app next day
        let hasOldProgress = sut.hasProgress()
        let loadedOldProgress = sut.loadProgress()

        // Then - Old progress should be expired and cleared
        XCTAssertFalse(hasOldProgress, "Old progress should not be available")
        XCTAssertNil(loadedOldProgress, "Old progress should return nil")

        // When - User starts new test
        let newProgress = createTestProgress(sessionId: 999)
        try sut.saveProgress(newProgress)

        // Then - New progress should be saved
        XCTAssertTrue(sut.hasProgress())
        XCTAssertEqual(sut.loadProgress()?.sessionId, 999)
    }
}
