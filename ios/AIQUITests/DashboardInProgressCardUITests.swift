//
//  DashboardInProgressCardUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/03/26.
//

import XCTest

/// UI tests that verify the consolidated in-progress dashboard state after removing the
/// separate `statusBadge` view from `DashboardView`.
///
/// All tests run entirely in mock mode using the `testInProgress` scenario, which causes
/// `getActiveTest()` to return an active session so `viewModel.activeTestSession` is
/// non-nil. No backend connection is required.
final class DashboardInProgressCardUITests: BaseUITest {
    // MARK: - Convenience References

    private var inProgressTestCard: XCUIElement {
        app.otherElements["dashboardView.inProgressTestCard"]
    }

    private var resumeButton: XCUIElement {
        app.buttons["dashboardView.resumeButton"]
    }

    private var abandonButton: XCUIElement {
        app.buttons["dashboardView.abandonTestButton"]
    }

    private var actionButton: XCUIElement {
        app.buttons["dashboardView.actionButton"]
    }

    // MARK: - Setup

    /// Validates simulator preconditions before each test.
    ///
    /// Skips with a clear diagnostic message when mock mode is not active
    /// (`-UITestMockMode` not present in launch arguments). Without this guard,
    /// a missing mock flag causes the dashboard to hit the real backend and fail
    /// in ways indistinguishable from a real regression.
    override func setUpWithError() throws {
        try super.setUpWithError()
        try XCTSkipUnless(
            app.launchArguments.contains("-UITestMockMode"),
            "Skipping DashboardInProgressCardUITests: mock mode is not active. "
                + "Run via the standard AIQUITests scheme which injects -UITestMockMode."
        )
    }

    // MARK: - Launch Configuration

    /// Sets the mock scenario to `testInProgress` so the dashboard launches with an active
    /// test session. The guard on `mockScenario == "default"` preserves compatibility with
    /// `relaunchWithScenario(_:)` per the contract documented in `BaseUITest`.
    override func setupLaunchConfiguration() {
        if mockScenario == "default" {
            mockScenario = "testInProgress"
        }
        super.setupLaunchConfiguration()
    }

    // MARK: - In-Progress Card Tests

    func testInProgressTestCard_IsVisibleWithActiveSession() {
        XCTAssertTrue(
            wait(for: inProgressTestCard, timeout: networkTimeout),
            "In-progress test card should be visible when an active test session exists"
        )
        assertExists(inProgressTestCard, "In-progress test card should exist")
        takeScreenshot(named: "InProgressCard_Visible")
    }

    func testResumeButton_IsAccessibleAndHittable() {
        XCTAssertTrue(
            wait(for: inProgressTestCard, timeout: networkTimeout),
            "In-progress test card should appear before checking resume button"
        )
        takeScreenshot(named: "ResumeButton_CardLoaded")

        XCTAssertTrue(
            waitForHittable(resumeButton),
            "Resume button should be hittable inside the in-progress card"
        )
        assertHittable(resumeButton, "Resume button should be hittable")
        takeScreenshot(named: "ResumeButton_Hittable")
    }

    func testAbandonButton_IsAccessibleAndHittable() {
        XCTAssertTrue(
            wait(for: inProgressTestCard, timeout: networkTimeout),
            "In-progress test card should appear before checking abandon button"
        )
        takeScreenshot(named: "AbandonButton_CardLoaded")

        XCTAssertTrue(
            waitForHittable(abandonButton),
            "Abandon button should be hittable inside the in-progress card"
        )
        assertHittable(abandonButton, "Abandon button should be hittable")
        takeScreenshot(named: "AbandonButton_Hittable")
    }

    func testNoSeparateStatusBadge_AboveActionButton() {
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Action button should appear to confirm the dashboard has loaded"
        )
        takeScreenshot(named: "NoStatusBadge_DashboardLoaded")

        let badgePredicate = NSPredicate(format: "label BEGINSWITH 'Test in Progress. '")
        let badgeElements = app.otherElements.matching(badgePredicate)
        XCTAssertEqual(
            badgeElements.count,
            0,
            "No separate status badge should appear above the action button"
        )
        takeScreenshot(named: "NoStatusBadge_Verified")
    }

    func testActionButton_LabelIsResumeTestInProgress() {
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Action button should appear when an active test session exists"
        )

        // Scroll to bring the action button into view if it is off-screen
        app.scrollViews.firstMatch.swipeUp()

        XCTAssertTrue(
            waitForHittable(actionButton),
            "Action button should be hittable after scrolling"
        )
        takeScreenshot(named: "ActionButton_InView")

        XCTAssertEqual(
            actionButton.label,
            "Resume Test in Progress",
            "Action button accessibility label should read 'Resume Test in Progress' when a session is active"
        )
        takeScreenshot(named: "ActionButton_LabelVerified")
    }
}
