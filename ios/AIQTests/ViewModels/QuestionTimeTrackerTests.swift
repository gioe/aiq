@testable import AIQ
import XCTest

@MainActor
final class QuestionTimeTrackerTests: XCTestCase {
    private var sut: QuestionTimeTracker!
    private var clock: MockTimeProvider!

    override func setUp() {
        super.setUp()
        clock = MockTimeProvider()
        sut = QuestionTimeTracker(clock: clock)
    }

    override func tearDown() {
        sut.reset()
        sut = nil
        clock = nil
        super.tearDown()
    }

    // MARK: - Basic Accumulation

    func testStartAndRecord_AccumulatesTime() {
        sut.startTracking(questionId: 1)
        clock.advance(by: 5)
        sut.recordCurrent()

        XCTAssertEqual(sut.elapsed(for: 1), 5)
    }

    func testElapsed_ReturnsZeroForUntrackedQuestion() {
        XCTAssertEqual(sut.elapsed(for: 99), 0)
    }

    func testRecordCurrent_WhenNoActiveTracking_IsNoOp() {
        sut.recordCurrent()
        XCTAssertEqual(sut.elapsed(for: 1), 0)
    }

    // MARK: - Multi-Visit Accumulation

    func testTwoVisits_AccumulateAcrossVisits() {
        // First visit: instant record (0s elapsed)
        sut.startTracking(questionId: 1)
        sut.recordCurrent()
        let afterFirstVisit = sut.elapsed(for: 1)

        // Second visit: 3 seconds
        sut.startTracking(questionId: 1)
        clock.advance(by: 3)
        sut.recordCurrent()
        let afterSecondVisit = sut.elapsed(for: 1)

        XCTAssertEqual(afterFirstVisit, 0)
        XCTAssertEqual(afterSecondVisit, 3)
    }

    func testMultipleQuestions_TrackIndependently() {
        sut.startTracking(questionId: 1)
        clock.advance(by: 4)
        sut.recordCurrent()

        sut.startTracking(questionId: 2)
        sut.recordCurrent()

        XCTAssertEqual(sut.elapsed(for: 1), 4, "Question 1 should have 4s elapsed")
        XCTAssertEqual(sut.elapsed(for: 2), 0, "Question 2 had negligible time")
    }

    // MARK: - Background Pause

    func testPauseTracking_RecordsElapsedAndAllowsResume() async {
        sut.startTracking(questionId: 1)
        clock.advance(by: 5)

        // Simulate backgrounding
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()

        XCTAssertEqual(sut.elapsed(for: 1), 5, "Pause should record elapsed time")

        // Simulate foregrounding — resume sets start time to clock.now
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()
        clock.advance(by: 3) // 3s while resumed

        // Pause again to record resumed time
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()

        XCTAssertEqual(sut.elapsed(for: 1), 8, "Time should accumulate across pause/resume cycle")
    }

    // MARK: - Foreground Resume

    func testResumeTracking_RestartsTimerAfterPause() async {
        sut.startTracking(questionId: 1)

        // Pause with negligible time (0s elapsed)
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()

        // Resume
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()
        clock.advance(by: 4) // let resumed tracking accumulate

        // Pause again to commit
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()

        XCTAssertEqual(sut.elapsed(for: 1), 4, "Resume should restart tracking while question is active")
    }

    func testResumeTracking_IsNoOpWhenNoActiveQuestion() async {
        sut.startTracking(questionId: 2)
        clock.advance(by: 5)
        sut.recordCurrent()
        let elapsedAfterRecord = sut.elapsed(for: 2)
        XCTAssertEqual(elapsedAfterRecord, 5)

        // Resume with no active question — should be a no-op
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()

        // Background — if resume incorrectly started the timer, pause would record spurious time
        clock.advance(by: 3)
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        await Task.yield(); await Task.yield(); await Task.yield()

        XCTAssertEqual(sut.elapsed(for: 2), elapsedAfterRecord, "Resume without active question should not record time")
    }

    // MARK: - Reset

    func testReset_ClearsAccumulatedTime() {
        sut.startTracking(questionId: 1)
        clock.advance(by: 5)
        sut.recordCurrent()
        XCTAssertEqual(sut.elapsed(for: 1), 5)

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
        clock.advance(by: 5)
        sut.recordCurrent()
        XCTAssertEqual(sut.elapsed(for: 1), 5)

        sut.startTracking(questionId: 2)
        sut.recordCurrent()

        sut.reset()

        XCTAssertEqual(sut.elapsed(for: 1), 0)
        XCTAssertEqual(sut.elapsed(for: 2), 0)
    }
}
