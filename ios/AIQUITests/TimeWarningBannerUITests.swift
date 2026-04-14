import XCTest

/// XCUITests for the TimeWarningBanner dismiss functionality.
///
/// These tests exercise the full in-app dismiss flow using the `timerNearWarning`
/// scenario, which loads a session with ~4 minutes remaining so the banner
/// appears immediately on test-taking view load.
///
/// Scenarios covered:
///
/// - Criteria 1404: Tapping the dismiss button removes the banner within 1 second.
/// - Criteria 1405: After dismissal, the banner does not reappear during continued
///   test-taking even though the underlying timer still reports `showWarning = true`.
final class TimeWarningBannerUITests: BaseUITest {
    private var testHelper: TestTakingHelper!

    override func setUpWithError() throws {
        try super.setUpWithError()
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        testHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Criteria 1404: Dismiss button closes banner

    /// Verifies that tapping the dismiss button on the time-warning banner removes
    /// the banner from the screen within 1 second.
    func testDismissButton_tapClosesBannerWithinOneSecond() {
        relaunchWithTimerNearWarning()

        // Navigate to test-taking — Resume button should appear for active session
        let resumeButton = testHelper.resumeTestButton
        XCTAssertTrue(
            resumeButton.waitForExistence(timeout: standardTimeout),
            "Resume Test button should appear for timerNearWarning scenario"
        )
        resumeButton.tap()

        // Wait for question to load
        XCTAssertTrue(
            testHelper.waitForQuestion(timeout: extendedTimeout),
            "Question should appear after resuming"
        )

        // Verify banner appears — container uses .accessibilityElement(children: .contain)
        // so it is found via otherElements (see CODING_STANDARDS.md accessibility note)
        let warningBanner = app.otherElements["testTakingView.timeWarningBanner"]
        XCTAssertTrue(
            wait(for: warningBanner, timeout: standardTimeout),
            "Time warning banner should appear when timer is in warning zone"
        )

        // Tap dismiss button — IconButton queried by accessibility label
        let dismissButton = app.buttons.matching(
            NSPredicate(format: "label == 'Dismiss time warning'")
        ).firstMatch
        XCTAssertTrue(
            dismissButton.waitForExistence(timeout: quickTimeout),
            "Dismiss button should exist on the warning banner"
        )
        dismissButton.tap()

        // Verify banner disappears within 1 second
        XCTAssertTrue(
            waitForDisappearance(of: warningBanner, timeout: 1.0),
            "Warning banner should disappear within 1 second of tapping dismiss"
        )
    }

    // MARK: - Criteria 1405: Banner does not reappear after dismissal

    /// Verifies that after the user dismisses the time-warning banner, answering a
    /// question and navigating does not cause the banner to reappear.
    ///
    /// The `warningBannerDismissed` flag in `TestTimerModifier` should prevent the
    /// `.onChange(of: timerManager.showWarning)` handler from setting
    /// `showTimeWarningBanner` back to `true`.
    func testBannerDoesNotReappear_afterDismissal() {
        relaunchWithTimerNearWarning()

        let resumeButton = testHelper.resumeTestButton
        XCTAssertTrue(
            resumeButton.waitForExistence(timeout: standardTimeout),
            "Resume Test button should appear for timerNearWarning scenario"
        )
        resumeButton.tap()

        XCTAssertTrue(
            testHelper.waitForQuestion(timeout: extendedTimeout),
            "Question should appear after resuming"
        )

        // Wait for banner and dismiss it
        let warningBanner = app.otherElements["testTakingView.timeWarningBanner"]
        XCTAssertTrue(
            wait(for: warningBanner, timeout: standardTimeout),
            "Time warning banner should appear"
        )

        let dismissButton = app.buttons.matching(
            NSPredicate(format: "label == 'Dismiss time warning'")
        ).firstMatch
        XCTAssertTrue(dismissButton.waitForExistence(timeout: quickTimeout))
        dismissButton.tap()

        XCTAssertTrue(
            waitForDisappearance(of: warningBanner, timeout: 1.0),
            "Banner should disappear after dismiss"
        )

        // Continue test-taking — answer a question and navigate to the next
        XCTAssertTrue(
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true),
            "Should be able to answer question after banner dismissal"
        )

        // Wait a moment for any re-trigger that might occur on the next `.onChange` fire
        Thread.sleep(forTimeInterval: 1.0)

        // Verify banner has not reappeared
        XCTAssertFalse(
            warningBanner.exists,
            "Warning banner must NOT reappear after dismissal during continued test-taking"
        )
    }
}
