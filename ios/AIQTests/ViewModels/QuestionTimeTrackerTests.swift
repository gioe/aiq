@testable import AIQ
import XCTest

@MainActor
final class QuestionTimeTrackerTests: XCTestCase {
    private var sut: QuestionTimeTracker!

    override func setUp() {
        super.setUp()
        sut = QuestionTimeTracker()
    }

    override func tearDown() {
        sut.reset()
        sut = nil
        super.tearDown()
    }

    // MARK: - Basic Accumulation

    func testStartAndRecord_AccumulatesTime() async throws {
        sut.startTracking(questionId: 1)
        try await Task.sleep(nanoseconds: 1_100_000_000)
        sut.recordCurrent()

        XCTAssertGreaterThanOrEqual(sut.elapsed(for: 1), 1, "Should accumulate at least 1 second")
    }

    func testElapsed_ReturnsZeroForUntrackedQuestion() {
        XCTAssertEqual(sut.elapsed(for: 99), 0)
    }

    func testRecordCurrent_WhenNoActiveTracking_IsNoOp() {
        sut.recordCurrent()
        XCTAssertEqual(sut.elapsed(for: 1), 0)
    }

    // MARK: - Multi-Visit Accumulation

    func testTwoVisits_AccumulateAcrossVisits() async throws {
        // First visit: instant record (< 1s, rounds to 0)
        sut.startTracking(questionId: 1)
        sut.recordCurrent()
        let afterFirstVisit = sut.elapsed(for: 1)

        // Second visit: 1.1 seconds
        sut.startTracking(questionId: 1)
        try await Task.sleep(nanoseconds: 1_100_000_000)
        sut.recordCurrent()
        let afterSecondVisit = sut.elapsed(for: 1)

        XCTAssertGreaterThanOrEqual(afterSecondVisit, afterFirstVisit + 1, "Second visit should add to accumulated time")
    }

    func testMultipleQuestions_TrackIndependently() async throws {
        sut.startTracking(questionId: 1)
        try await Task.sleep(nanoseconds: 1_100_000_000)
        sut.recordCurrent()

        sut.startTracking(questionId: 2)
        sut.recordCurrent()

        XCTAssertGreaterThanOrEqual(sut.elapsed(for: 1), 1, "Question 1 should have elapsed time")
        XCTAssertEqual(sut.elapsed(for: 2), 0, "Question 2 had negligible time")
    }

    // MARK: - Background Pause

    func testPauseTracking_RecordsElapsedAndAllowsResume() async throws {
        sut.startTracking(questionId: 1)
        try await Task.sleep(nanoseconds: 1_100_000_000)

        // Simulate backgrounding
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 100_000_000) // let observer task execute

        XCTAssertGreaterThanOrEqual(sut.elapsed(for: 1), 1, "Pause should record elapsed time")

        // Simulate foregrounding — resume should restart because questionId was kept by pause
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 1_100_000_000) // 1.1s while resumed

        // Pause again to record resumed time
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 100_000_000)

        XCTAssertGreaterThanOrEqual(sut.elapsed(for: 1), 2, "Time should accumulate across pause/resume cycle")
    }

    // MARK: - Foreground Resume

    func testResumeTracking_RestartsTimerAfterPause() async throws {
        sut.startTracking(questionId: 1)

        // Pause with negligible time
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 100_000_000)
        let elapsedAfterPause = sut.elapsed(for: 1) // 0 since < 1s

        // Resume
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 1_100_000_000) // let resumed tracking accumulate

        // Pause again to commit
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 100_000_000)

        XCTAssertGreaterThanOrEqual(
            sut.elapsed(for: 1),
            elapsedAfterPause + 1,
            "Resume should restart tracking while question is active"
        )
    }

    func testResumeTracking_IsNoOpWhenNoActiveQuestion() async throws {
        // Complete a question normally — clears currentQuestionId
        sut.startTracking(questionId: 2)
        sut.recordCurrent()
        let elapsedAfterRecord = sut.elapsed(for: 2)

        // Resume with no active question — should be a no-op
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 100_000_000)

        // Background — if resume incorrectly started the timer, pause would record spurious time
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        try await Task.sleep(nanoseconds: 100_000_000)

        XCTAssertEqual(sut.elapsed(for: 2), elapsedAfterRecord, "Resume without active question should not record time")
    }

    // MARK: - Reset

    func testReset_ClearsAccumulatedTime() async throws {
        sut.startTracking(questionId: 1)
        try await Task.sleep(nanoseconds: 1_100_000_000)
        sut.recordCurrent()
        XCTAssertGreaterThanOrEqual(sut.elapsed(for: 1), 1)

        sut.reset()
        XCTAssertEqual(sut.elapsed(for: 1), 0, "Reset should clear accumulated time")
    }

    func testReset_ClearsActiveTracking() {
        sut.startTracking(questionId: 1)

        sut.reset()

        // After reset, recordCurrent should be a no-op (no active tracking)
        sut.recordCurrent()
        XCTAssertEqual(sut.elapsed(for: 1), 0, "Reset should clear in-progress tracking")
    }

    func testReset_ClearsAllQuestions() {
        sut.startTracking(questionId: 1)
        sut.recordCurrent()
        sut.startTracking(questionId: 2)
        sut.recordCurrent()

        sut.reset()

        XCTAssertEqual(sut.elapsed(for: 1), 0)
        XCTAssertEqual(sut.elapsed(for: 2), 0)
    }
}
