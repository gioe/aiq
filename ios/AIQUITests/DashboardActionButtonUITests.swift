//
//  DashboardActionButtonUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 02/03/26.
//

import XCTest

/// UI tests that verify the `DashboardActionButton` component.
///
/// All tests run entirely in mock mode. The primary scenario is `loggedInWithHistory`,
/// which renders the action button with `hasActiveTest = false` showing "Take Another Test".
/// A secondary scenario is `testInProgress`, where `hasActiveTest = true` and the button
/// shows "Resume Test in Progress". No backend connection is required.
final class DashboardActionButtonUITests: BaseUITest {
    // MARK: - Convenience References

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
            "Skipping DashboardActionButtonUITests: mock mode is not active. "
                + "Run via the standard AIQUITests scheme which injects -UITestMockMode."
        )
    }

    // MARK: - Launch Configuration

    /// Sets the mock scenario to `loggedInWithHistory` so the dashboard launches with
    /// `hasActiveTest = false` and the action button shows "Take Another Test".
    /// The guard on `mockScenario == "default"` preserves compatibility with
    /// `relaunchWithScenario(_:)` per the contract documented in `BaseUITest`.
    override func setupLaunchConfiguration() {
        if mockScenario == "default" {
            mockScenario = "loggedInWithHistory"
        }
        super.setupLaunchConfiguration()
    }

    // MARK: - Empty State Tests (loggedInNoHistory)

    /// Verifies that the action button is rendered in the empty state (no test history)
    /// and displays the "Start Your First Test" label override introduced in TASK-1313.
    func testActionButton_EmptyState_IsRenderedWithStartYourFirstTestLabel() {
        relaunchAsLoggedInNoHistory()

        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Action button should be rendered in the empty state when there is no test history"
        )
        takeScreenshot(named: "ActionButton_EmptyState_Loaded")

        XCTAssertEqual(
            actionButton.label,
            "Start Your First Test",
            "Action button label should read 'Start Your First Test' in empty state (custom label override)"
        )
        takeScreenshot(named: "ActionButton_EmptyState_LabelVerified")
    }

    // MARK: - hasActiveTest = false Tests

    func testActionButton_NoActiveSession_ShowsTakeAnotherTestAndIdentifier() {
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Element with identifier 'dashboardView.actionButton' should exist on the dashboard"
        )
        takeScreenshot(named: "ActionButton_NoActiveTest_Loaded")

        XCTAssertEqual(
            actionButton.label,
            "Take Another Test",
            "Action button label should read 'Take Another Test' when no active session exists"
        )
        takeScreenshot(named: "ActionButton_NoActiveTest_LabelVerified")
    }

    // MARK: - hasActiveTest = true Tests

    func testActionButton_ActiveSession_ShowsResumeTestInProgress() {
        relaunchWithTestInProgress()

        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Action button should appear when an active test session exists"
        )

        app.scrollViews.firstMatch.swipeUp()

        XCTAssertTrue(
            waitForHittable(actionButton),
            "Action button should be hittable after scrolling"
        )
        takeScreenshot(named: "ActionButton_ActiveTest_InView")

        XCTAssertEqual(
            actionButton.label,
            "Resume Test in Progress",
            "Action button label should read 'Resume Test in Progress' when a session is active"
        )
        takeScreenshot(named: "ActionButton_ActiveTest_LabelVerified")
    }

    // MARK: - Navigation Tests

    func testActionButton_Tap_TriggersNavigationToTestTakingView() {
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Action button should appear before tapping"
        )

        app.scrollViews.firstMatch.swipeUp()

        XCTAssertTrue(
            waitForHittable(actionButton),
            "Action button should be hittable before tapping"
        )
        takeScreenshot(named: "ActionButton_BeforeTap")

        actionButton.tap()

        let exitButton = app.buttons["testTakingView.exitButton"]
        XCTAssertTrue(
            wait(for: exitButton, timeout: networkTimeout),
            "TestTakingView exit button should appear after tapping the action button, confirming navigation occurred"
        )
        takeScreenshot(named: "ActionButton_AfterTap_TestTakingView")
    }
}
