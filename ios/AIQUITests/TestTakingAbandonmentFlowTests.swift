//
//  TestTakingAbandonmentFlowTests.swift
//  AIQUITests
//

import XCTest

/// UI tests for the test-taking abandonment flow end-to-end.
///
/// Scenarios covered:
///
/// 1. **0-answer timer expiry → silent abandonment → fresh test start**
///    `expiredSession` is already past the 35-minute limit, so
///    `startWithSessionTime(_:)` returns `false` immediately and
///    `handleTimerExpiration()` fires without any real wall-clock wait.
///
/// 2. **Partial-answer timer expiry → "Time's Up!" alert shown**
///    `nearExpiredSession` has ~20 seconds remaining, so the test waits
///    for the real countdown to fire. A 30-second assertion timeout is used
///    to accommodate navigation overhead and slow CI runners.
///
/// 3. Silent vs. non-silent paths are exercised as distinct test cases
final class TestTakingAbandonmentFlowTests: BaseUITest {
    private var testHelper: TestTakingHelper!

    override func setUpWithError() throws {
        try super.setUpWithError()
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        testHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Scenario 1: 0-Answer Silent Abandonment → Fresh Test Start

    /// Verifies that after a 0-answer timer expiry:
    /// - The session is silently abandoned (no Time's Up alert shown)
    /// - A fresh test starts automatically
    /// - No "Time Running Low" banner is visible
    /// - All answer buttons are tappable (isLocked = false)
    func testZeroAnswerTimerExpiry_silentAbandon_freshTestStartsClean() {
        relaunchWithTimerExpiredZeroAnswers()

        // Navigate to test-taking — from dashboard tap Start Test
        // The expired session has 0 answers and will be silently abandoned
        // then a fresh test will auto-start.
        let startButton = testHelper.startTestButton
        XCTAssertTrue(
            startButton.waitForExistence(timeout: standardTimeout),
            "Start Test button should be visible (no active session on dashboard for zero-answer scenario)"
        )
        XCTAssertTrue(startButton.isEnabled, "Start Test button should be enabled")

        startButton.tap()
        takeScreenshot(named: "AfterStartTestTap")

        // Wait for the expired session to be processed and fresh test to start
        // (silent abandonment + auto-start fresh test happens automatically)
        XCTAssertTrue(
            testHelper.waitForQuestion(timeout: extendedTimeout),
            "Fresh test questions should appear after silent abandonment auto-start"
        )
        takeScreenshot(named: "FreshTestLoaded")

        // Verify: No "Time Running Low" banner visible
        let warningBanner = app.otherElements["testTakingView.timeWarningBanner"]
        XCTAssertFalse(
            warningBanner.exists,
            "Time Running Low banner must NOT be visible on a fresh test start after silent abandonment"
        )

        // Verify: All answer buttons are tappable (not locked from previous expired session)
        let firstAnswerButton = testHelper.answerButton(at: 0)
        XCTAssertTrue(
            firstAnswerButton.waitForExistence(timeout: standardTimeout),
            "First answer button should exist"
        )
        XCTAssertTrue(
            firstAnswerButton.isEnabled,
            "Answer buttons must be enabled (not locked) after silent abandonment and fresh start"
        )

        // Tap the answer to confirm it's interactive
        firstAnswerButton.tap()
        takeScreenshot(named: "AnswerButtonTapped_FreshTest")

        // Verify second answer button is also enabled
        let secondAnswerButton = testHelper.answerButton(at: 1)
        if secondAnswerButton.exists {
            XCTAssertTrue(
                secondAnswerButton.isEnabled,
                "Second answer button should also be enabled"
            )
        }

        // Verify Time's Up alert was NOT shown (silent path confirmed)
        let timesUpAlert = app.alerts["Time's Up!"]
        XCTAssertFalse(
            timesUpAlert.exists,
            "Time's Up alert must NOT appear in the silent abandonment path (0 answers)"
        )
    }

    // MARK: - Scenario 2: Partial-Answer Timer Expiry → Time's Up Alert

    /// Verifies that after a partial-answer timer expiry:
    /// - The "Time's Up!" alert is shown (non-silent path)
    /// - The test is NOT silently abandoned
    ///
    /// The mock uses `nearExpiredSession` (~20 s remaining) with 1 pre-seeded answer.
    /// `mergeSavedProgress` populates `answeredCount > 0` when the session is resumed,
    /// so the non-silent alert path fires once the countdown reaches zero.
    func testPartialAnswerTimerExpiry_nonSilentPath_timesUpAlertShown() {
        relaunchWithTimerExpiredWithAnswers()

        // Dashboard should show "Resume Test" since there's an active near-expired session
        let resumeButton = testHelper.resumeTestButton
        XCTAssertTrue(
            resumeButton.waitForExistence(timeout: standardTimeout),
            "Resume Test button should be visible on dashboard (active near-expired session with answers)"
        )
        XCTAssertTrue(resumeButton.isEnabled, "Resume Test button should be enabled")

        takeScreenshot(named: "DashboardWithResumeButton")
        resumeButton.tap()

        // Timer fires when the ~20-second remaining window elapses after navigation.
        // Use a 30-second timeout to exceed the session's remaining time plus overhead.
        let timesUpAlert = app.alerts["Time's Up!"]
        XCTAssertTrue(
            timesUpAlert.waitForExistence(timeout: 30),
            "Time's Up! alert must appear when timer expires with partial answers (non-silent path)"
        )
        takeScreenshot(named: "TimesUpAlertShown")

        // Dismiss the alert
        let okButton = timesUpAlert.buttons["OK"]
        XCTAssertTrue(okButton.exists, "OK button should exist in Time's Up alert")
        okButton.tap()

        takeScreenshot(named: "AfterAlertDismissed")
    }

    // MARK: - Scenario 3: Silent vs. Non-Silent Paths Are Distinct

    /// Verifies that the 0-answer (silent) and partial-answer (non-silent) abandonment
    /// paths produce distinct, non-overlapping outcomes.
    ///
    /// Silent path (0 answers):
    /// - No Time's Up alert
    /// - Fresh test starts automatically
    /// - Answer buttons are tappable
    ///
    /// Non-silent path (partial answers):
    /// - Time's Up alert is shown
    /// - (The fresh test path in silent scenario is NOT triggered)
    func testSilentAndNonSilentPaths_areDistinct() {
        // --- Silent path ---
        relaunchWithTimerExpiredZeroAnswers()

        let startButton = testHelper.startTestButton
        XCTAssertTrue(startButton.waitForExistence(timeout: standardTimeout))
        startButton.tap()

        // Wait for fresh test (silent path auto-starts)
        XCTAssertTrue(
            testHelper.waitForQuestion(timeout: extendedTimeout),
            "Silent path: fresh test should auto-start after 0-answer silent abandonment"
        )

        // Silent path must NOT show Time's Up alert
        let timesUpAlertDuringSilent = app.alerts["Time's Up!"]
        XCTAssertFalse(
            timesUpAlertDuringSilent.exists,
            "Silent path must NOT show Time's Up alert"
        )

        // Verify answer buttons enabled (not locked)
        let answerButton = testHelper.answerButton(at: 0)
        XCTAssertTrue(answerButton.waitForExistence(timeout: standardTimeout))
        XCTAssertTrue(answerButton.isEnabled, "Silent path: answer buttons must be enabled")

        takeScreenshot(named: "SilentPath_FreshTestReady")

        // --- Non-silent path ---
        relaunchWithTimerExpiredWithAnswers()

        let resumeButton = testHelper.resumeTestButton
        XCTAssertTrue(resumeButton.waitForExistence(timeout: standardTimeout))
        resumeButton.tap()

        // Non-silent path MUST show Time's Up alert.
        // Use a 30-second timeout to exceed the session's ~20-second remaining window.
        let timesUpAlertDuringNonSilent = app.alerts["Time's Up!"]
        XCTAssertTrue(
            timesUpAlertDuringNonSilent.waitForExistence(timeout: 30),
            "Non-silent path: Time's Up alert must appear with partial answers"
        )

        takeScreenshot(named: "NonSilentPath_TimesUpAlert")

        // Dismiss and verify we're NOT in the fresh-start auto-path
        timesUpAlertDuringNonSilent.buttons["OK"].tap()

        // Assert: view must navigate to results/completion screen (not back to a fresh test start)
        XCTAssertTrue(
            testHelper.waitForResults(timeout: extendedTimeout),
            "Non-silent path: must navigate to results/completion screen after Time's Up alert dismissal"
        )

        // The test was submitted (not silently abandoned), so no auto-start of fresh test happens immediately
        // The view should navigate to results (or stay on submission) — not to the Start Test state
        let warningBanner = app.otherElements["testTakingView.timeWarningBanner"]
        XCTAssertFalse(
            warningBanner.exists,
            "Non-silent path: Time Running Low banner should not be visible after alert dismissal"
        )
    }
}
