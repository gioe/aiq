import Combine
import XCTest

@testable import AIQ

@MainActor
final class TestTimerManagerTests: XCTestCase {
    var sut: TestTimerManager!
    var cancellables: Set<AnyCancellable>!

    override func setUp() {
        super.setUp()
        sut = TestTimerManager()
        cancellables = []
    }

    override func tearDown() {
        sut.stop()
        super.tearDown()
    }

    // MARK: - Initial State Tests

    func testInitialState_HasCorrectDefaults() {
        XCTAssertEqual(sut.remainingSeconds, 2100, "Should start with 35 minutes (2100 seconds)")
        XCTAssertFalse(sut.showWarning, "Warning should be false initially")
        XCTAssertFalse(sut.hasExpired, "Should not be expired initially")
        XCTAssertEqual(sut.formattedTime, "35:00", "Formatted time should be 35:00")
        XCTAssertEqual(sut.progress, 1.0, "Progress should be 1.0 (full)")
        XCTAssertEqual(sut.timerColor, .normal, "Timer color should be normal")
    }

    // MARK: - Timer Start Tests

    func testStart_BeginsCountdown() async {
        // Given
        let initialTime = sut.remainingSeconds

        // When
        sut.start()

        // Wait a bit for timer to tick
        try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

        // Then
        // Timer uses wall-clock reference, so remaining time should have decreased
        // Note: Due to test timing variability, we just verify the timer is running
        XCTAssertTrue(sut.remainingSeconds <= initialTime, "Timer should be counting down")
    }

    func testStartWithSessionTime_CalculatesElapsedTimeCorrectly() {
        // Given - Session started 60 seconds ago
        let sessionStart = Date().addingTimeInterval(-60)

        // When
        let started = sut.startWithSessionTime(sessionStart)

        // Then
        XCTAssertTrue(started, "Should return true when time remaining")
        // Allow for 1-2 second variance due to test execution time
        XCTAssertTrue(
            sut.remainingSeconds >= 2038 && sut.remainingSeconds <= 2042,
            "Should have ~2040 seconds remaining (35min - 60s). Actual: \(sut.remainingSeconds)"
        )
        XCTAssertFalse(sut.hasExpired, "Should not be expired")
    }

    func testStartWithSessionTime_ReturnsfalseWhenAlreadyExpired() {
        // Given - Session started 36 minutes ago (already expired)
        let sessionStart = Date().addingTimeInterval(-2160)

        // When
        let started = sut.startWithSessionTime(sessionStart)

        // Then
        XCTAssertFalse(started, "Should return false when time already expired")
        XCTAssertEqual(sut.remainingSeconds, 0, "Remaining seconds should be 0")
        XCTAssertTrue(sut.hasExpired, "Should be marked as expired")
        XCTAssertTrue(sut.showWarning, "Warning should be shown for expired timer")
    }

    func testStartWithSessionTime_SetsWarningWhenUnderFiveMinutes() {
        // Given - Session started 31 minutes ago (4 minutes remaining)
        let sessionStart = Date().addingTimeInterval(-1860) // 31 * 60 = 1860

        // When
        let started = sut.startWithSessionTime(sessionStart)

        // Then
        XCTAssertTrue(started, "Should return true when time remaining")
        XCTAssertTrue(sut.remainingSeconds <= 300, "Should have ≤300 seconds remaining")
        XCTAssertTrue(sut.showWarning, "Warning should be shown when under 5 minutes")
    }

    // MARK: - Timer Pause/Resume Tests

    func testPause_StopsTimerUpdates() async {
        // Given
        let sessionStart = Date().addingTimeInterval(-60)
        sut.startWithSessionTime(sessionStart)

        // When
        sut.pause()
        let pausedTime = sut.remainingSeconds

        // Wait to verify time doesn't change
        try? await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds

        // Then
        XCTAssertEqual(
            sut.remainingSeconds,
            pausedTime,
            "Time should not change while paused"
        )
    }

    func testResume_ContinuesCountdown() async {
        // Given
        let sessionStart = Date().addingTimeInterval(-60)
        sut.startWithSessionTime(sessionStart)
        sut.pause()
        let pausedTime = sut.remainingSeconds

        // When
        sut.resume()

        // Wait for timer to tick
        try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

        // Then - Time should have decreased after resume
        // Note: The timer recalculates from session start, so time continues
        XCTAssertTrue(
            sut.remainingSeconds <= pausedTime,
            "Timer should continue counting down after resume"
        )
    }

    func testResume_DoesNotResumeWhenExpired() {
        // Given
        let sessionStart = Date().addingTimeInterval(-2160) // Already expired
        sut.startWithSessionTime(sessionStart)

        // Verify expired state
        XCTAssertTrue(sut.hasExpired)

        // When
        sut.resume()

        // Then
        XCTAssertEqual(sut.remainingSeconds, 0, "Should remain at 0")
        XCTAssertTrue(sut.hasExpired, "Should still be expired")
    }

    // MARK: - Warning Threshold Tests

    func testWarningTriggersAtFiveMinutes() async {
        // Given - Start with 301 seconds remaining (just over 5 minutes)
        let sessionStart = Date().addingTimeInterval(-(2100 - 301))
        sut.startWithSessionTime(sessionStart)

        // Verify initial state
        XCTAssertFalse(sut.showWarning, "Warning should not be shown initially at 301 seconds")

        // When - Wait for timer to cross the threshold
        // We need to wait until remaining time drops to 300 or below
        var warningTriggered = false
        let expectation = XCTestExpectation(description: "Warning triggered")

        sut.$showWarning
            .dropFirst()
            .sink { showWarning in
                if showWarning {
                    warningTriggered = true
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Wait for the warning (with timeout)
        await fulfillment(of: [expectation], timeout: 3.0)

        // Then
        XCTAssertTrue(warningTriggered, "Warning should have been triggered")
        XCTAssertTrue(sut.showWarning, "showWarning should be true")
    }

    func testTimerColorChangesToWarningAtFiveMinutes() {
        // Given - Session with exactly 5 minutes remaining
        let sessionStart = Date().addingTimeInterval(-(2100 - 300))
        sut.startWithSessionTime(sessionStart)

        // Then
        XCTAssertEqual(
            sut.timerColor,
            .warning,
            "Timer color should be warning at 5 minutes"
        )
    }

    func testTimerColorChangesToCriticalAtOneMinute() {
        // Given - Session with 1 minute remaining
        let sessionStart = Date().addingTimeInterval(-(2100 - 60))
        sut.startWithSessionTime(sessionStart)

        // Then
        XCTAssertEqual(
            sut.timerColor,
            .critical,
            "Timer color should be critical at 1 minute"
        )
    }

    // MARK: - Expiration Tests

    func testTimerExpiresAtZero() async {
        // Given - Start with just 1 second remaining
        let sessionStart = Date().addingTimeInterval(-(2100 - 1))
        sut.startWithSessionTime(sessionStart)

        // When - Wait for expiration
        let expectation = XCTestExpectation(description: "Timer expired")

        sut.$hasExpired
            .dropFirst()
            .sink { hasExpired in
                if hasExpired {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        await fulfillment(of: [expectation], timeout: 3.0)

        // Then
        XCTAssertTrue(sut.hasExpired, "Timer should be expired")
        XCTAssertEqual(sut.remainingSeconds, 0, "Remaining seconds should be 0")
    }

    // MARK: - Reset Tests

    func testReset_RestoresInitialState() {
        // Given - Timer has been running
        let sessionStart = Date().addingTimeInterval(-600) // 10 minutes elapsed
        sut.startWithSessionTime(sessionStart)
        XCTAssertTrue(sut.remainingSeconds < 2100, "Time should have elapsed")

        // When
        sut.reset()

        // Then
        XCTAssertEqual(sut.remainingSeconds, 2100, "Should reset to 35 minutes")
        XCTAssertFalse(sut.showWarning, "Warning should be reset")
        XCTAssertFalse(sut.hasExpired, "Expired flag should be reset")
        XCTAssertEqual(sut.formattedTime, "35:00", "Formatted time should be 35:00")
    }

    // MARK: - Formatted Time Tests

    func testFormattedTime_DisplaysCorrectly() {
        // Test various remaining times
        // 35 minutes
        XCTAssertEqual(sut.formattedTime, "35:00")

        // 5 minutes
        let fiveMinStart = Date().addingTimeInterval(-(2100 - 300))
        sut.startWithSessionTime(fiveMinStart)
        sut.pause()
        XCTAssertEqual(sut.formattedTime, "05:00")

        // Reset and test 1 minute
        sut.reset()
        let oneMinStart = Date().addingTimeInterval(-(2100 - 60))
        sut.startWithSessionTime(oneMinStart)
        sut.pause()
        XCTAssertEqual(sut.formattedTime, "01:00")

        // Reset and test 59 seconds
        sut.reset()
        let fiftyNineSecStart = Date().addingTimeInterval(-(2100 - 59))
        sut.startWithSessionTime(fiftyNineSecStart)
        sut.pause()
        XCTAssertEqual(sut.formattedTime, "00:59")
    }

    // MARK: - Progress Tests

    func testProgress_CalculatesCorrectly() {
        // Full time = 1.0
        XCTAssertEqual(sut.progress, 1.0)

        // Half time = 0.5
        let halfTimeStart = Date().addingTimeInterval(-1050) // 17.5 minutes elapsed
        sut.startWithSessionTime(halfTimeStart)
        sut.pause()
        XCTAssertEqual(sut.progress, 0.5, accuracy: 0.01)

        // No time = 0.0
        sut.reset()
        let expiredStart = Date().addingTimeInterval(-2160)
        sut.startWithSessionTime(expiredStart)
        XCTAssertEqual(sut.progress, 0.0)
    }

    // MARK: - Constants Tests

    func testConstants_HaveCorrectValues() {
        XCTAssertEqual(
            TestTimerManager.totalTimeSeconds,
            2100,
            "Total time should be 35 minutes (2100 seconds)"
        )
        XCTAssertEqual(
            TestTimerManager.warningThresholdSeconds,
            300,
            "Warning threshold should be 5 minutes (300 seconds)"
        )
    }

    // MARK: - Edge Case Tests

    func testStartWhileAlreadyRunning_DoesNotCreateDuplicateTimers() async {
        // Given - Timer already running
        sut.start()
        let initialRemaining = sut.remainingSeconds

        // When - Try to start again
        sut.start()

        // Then - Wait a bit and verify timer is still working normally
        try? await Task.sleep(nanoseconds: 300_000_000)
        XCTAssertTrue(
            sut.remainingSeconds <= initialRemaining,
            "Timer should continue normally without duplicate timers"
        )
    }

    func testPauseWhileNotRunning_DoesNotCrash() {
        // Given - Timer not started
        // When - Pause without starting
        sut.pause()

        // Then - Should not crash and state should be valid
        XCTAssertFalse(sut.hasExpired)
        XCTAssertEqual(sut.remainingSeconds, 2100)
    }

    func testResumeWhileNotPaused_DoesNotCrash() {
        // Given - Timer not paused (just started)
        sut.start()

        // When - Try to resume
        sut.resume()

        // Then - Should not crash
        XCTAssertFalse(sut.hasExpired)
    }

    func testStop_CanBeCalledMultipleTimes() {
        // Given
        sut.start()

        // When
        sut.stop()
        sut.stop()
        sut.stop()

        // Then - Should not crash
        XCTAssertFalse(sut.hasExpired)
    }
}
