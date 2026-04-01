//
//  DashboardPullToRefreshUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/04/26.
//
//  Regression tests for TASK-269: pull-to-refresh CancellationError race condition.
//  Verifies that a pull-to-refresh gesture on the Dashboard scroll view completes
//  successfully, the refresh spinner disappears, and the dashboard reflects
//  refreshed state with no error view.
//

import XCTest

/// UI tests that verify pull-to-refresh behaviour on the Dashboard scroll view.
///
/// All tests run in mock mode (`loggedInWithHistory` scenario) so responses are
/// deterministic. The primary regression scenario covered here is TASK-269, where
/// a concurrent token-refresh race caused the pull-to-refresh task to receive a
/// `CancellationError`, leaving the dashboard in a silent error state.
final class DashboardPullToRefreshUITests: BaseUITest {
    // MARK: - Element References

    private var scrollView: XCUIElement {
        app.scrollViews["dashboardView.scrollView"]
    }

    private var actionButton: XCUIElement {
        app.buttons["dashboardView.actionButton"]
    }

    private var emptyStateView: XCUIElement {
        app.otherElements["dashboardView.emptyStateView"]
    }

    // MARK: - Setup

    /// Sets the default scenario to `loggedInWithHistory` so the dashboard
    /// launches with completed test history and the "Take Another Test" action button.
    ///
    /// The `mockScenario == "default"` guard preserves compatibility with
    /// `relaunchWithScenario(_:)` per the contract in `BaseUITest`.
    override func setupLaunchConfiguration() {
        if mockScenario == "default" {
            mockScenario = "loggedInWithHistory"
        }
        super.setupLaunchConfiguration()
    }

    /// Skips with a diagnostic message when mock mode is not active.
    ///
    /// Without this guard a missing `-UITestMockMode` flag causes the dashboard
    /// to hit the real backend, producing failures indistinguishable from regressions.
    override func setUpWithError() throws {
        try super.setUpWithError()
        try XCTSkipUnless(
            app.launchArguments.contains("-UITestMockMode"),
            "Skipping DashboardPullToRefreshUITests: mock mode is not active. "
                + "Run via the standard AIQUITests scheme which injects -UITestMockMode."
        )
    }

    // MARK: - Tests

    /// Verifies that a pull-to-refresh gesture completes without the dashboard
    /// entering an error state.
    ///
    /// Regression test for TASK-269 where a concurrent token-refresh race caused
    /// the refresh task to receive a `CancellationError` and the dashboard silently
    /// showed an error view instead of refreshed content.
    func testPullToRefresh_CompletesWithoutError() {
        // Dashboard should load with completed-test content
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Dashboard action button should appear on initial load"
        )
        takeScreenshot(named: "PullToRefresh_Before")

        // Trigger pull-to-refresh gesture on the identified scroll view
        scrollView.swipeDown()

        // Assert: dashboard content still visible after refresh completes
        // Failure here indicates the TASK-269 regression has re-introduced itself:
        // the refresh task was cancelled and the dashboard shows an error view.
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Dashboard action button should remain visible after pull-to-refresh — "
                + "regression check for TASK-269 CancellationError"
        )
        takeScreenshot(named: "PullToRefresh_After_ContentVisible")
    }

    /// Verifies that the pull-to-refresh spinner appears and eventually disappears,
    /// confirming the refresh cycle completed rather than hanging indefinitely.
    ///
    /// The spinner is the system activity indicator injected by SwiftUI's `.refreshable`
    /// modifier. It must disappear once the async refresh closure returns. If it persists,
    /// the refresh task is still running (or deadlocked), which is the expected symptom of
    /// the TASK-269 `CancellationError` race.
    func testPullToRefresh_SpinnerAppearsAndDisappears() {
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Dashboard should load before triggering pull-to-refresh"
        )

        // Trigger pull-to-refresh gesture
        scrollView.swipeDown()

        // Assert the system refresh spinner appears, confirming the pull-to-refresh gesture
        // was recognised and the refresh closure was invoked by the framework.
        let spinner = app.activityIndicators.firstMatch
        XCTAssertTrue(
            wait(for: spinner, timeout: standardTimeout),
            "Pull-to-refresh spinner should appear after swipe gesture — "
                + "if absent the gesture was not recognised or the mock responded before the indicator rendered"
        )

        // Wait for the spinner to disappear, proving the refresh closure returned
        // and the framework dismissed the indicator.
        XCTAssertTrue(
            waitForDisappearance(of: spinner, timeout: networkTimeout),
            "Pull-to-refresh spinner should disappear after refresh completes — "
                + "if it persists the refresh task is still running or was cancelled (TASK-269 regression)"
        )
        takeScreenshot(named: "PullToRefresh_SpinnerGone")

        // Dashboard should still be in a valid state after the spinner clears
        XCTAssertTrue(
            wait(for: actionButton, timeout: standardTimeout),
            "Dashboard action button should be visible once the refresh spinner is gone"
        )
        takeScreenshot(named: "PullToRefresh_After_SpinnerTest")
    }

    /// Verifies that pull-to-refresh works from the empty state (no test history),
    /// ensuring the refresh path is exercised when `hasTests = false`.
    ///
    /// Uses the "Start Your First Test" action button as the presence indicator — its
    /// identifier (`dashboardView.actionButton`) is well-established and confirmed by
    /// `DashboardActionButtonUITests.testActionButton_EmptyState_IsRenderedWithStartYourFirstTestLabel`.
    func testPullToRefresh_FromEmptyState_CompletesWithoutError() {
        relaunchAsLoggedInNoHistory()

        // In the no-history empty state the action button shows "Start Your First Test"
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Dashboard action button should appear in the empty state (no test history)"
        )
        takeScreenshot(named: "PullToRefresh_EmptyState_Before")

        // Trigger pull-to-refresh gesture
        scrollView.swipeDown()

        // Action button should still be visible after refresh (no error state)
        XCTAssertTrue(
            wait(for: actionButton, timeout: networkTimeout),
            "Dashboard action button should remain visible after pull-to-refresh in empty state — "
                + "refresh should not produce an error when test count is zero"
        )

        // Regression guard for TASK-272: emptyStateView container must be detectable via
        // app.otherElements after .accessibilityElement(children: .contain) was applied.
        XCTAssertTrue(
            emptyStateView.waitForExistence(timeout: networkTimeout),
            "dashboardView.emptyStateView should be findable via app.otherElements after pull-to-refresh — "
                + "regression check for TASK-272 accessibility container fix"
        )
        takeScreenshot(named: "PullToRefresh_EmptyState_After")
    }
}
