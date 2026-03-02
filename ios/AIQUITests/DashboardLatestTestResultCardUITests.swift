//
//  DashboardLatestTestResultCardUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 02/03/26.
//

import XCTest

/// UI tests that verify the `DashboardLatestTestResultCard` component rendered inside
/// `DashboardView.dashboardContent`.
///
/// All tests run entirely in mock mode. The primary scenario is `loggedInWithHistory`,
/// which causes `getTestHistory` to return 4 sample results so `viewModel.latestTestResult`
/// is non-nil and the card is rendered. The absence test uses `loggedInNoHistory`, where
/// `getTestHistory` returns an empty list so the dashboard shows the empty state instead
/// of `dashboardContent`. No backend connection is required.
final class DashboardLatestTestResultCardUITests: BaseUITest {
    // MARK: - Convenience References

    private var latestTestCard: XCUIElement {
        app.otherElements["dashboardView.latestTestCard"]
    }

    private var emptyStateActionButton: XCUIElement {
        app.buttons["emptyStateView.actionButton"]
    }

    // MARK: - Launch Configuration

    /// Sets the mock scenario to `loggedInWithHistory` so the dashboard launches with a
    /// non-nil `latestTestResult` and the card is visible. The guard on
    /// `mockScenario == "default"` preserves compatibility with `relaunchWithScenario(_:)`
    /// per the contract documented in `BaseUITest`.
    override func setupLaunchConfiguration() {
        if mockScenario == "default" {
            mockScenario = "loggedInWithHistory"
        }
        super.setupLaunchConfiguration()
    }

    // MARK: - Latest Test Result Card Tests

    func testLatestTestResultCard_IsVisibleWithNonNilResult() {
        XCTAssertTrue(
            wait(for: latestTestCard, timeout: networkTimeout),
            "Latest test result card should be visible when latestTestResult is non-nil"
        )
        assertExists(latestTestCard, "Latest test result card should exist")
        takeScreenshot(named: "LatestTestResultCard_Visible")
    }

    func testLatestTestResultCard_IsAbsentWithNilResult() {
        relaunchWithScenario("loggedInNoHistory")

        XCTAssertTrue(
            wait(for: emptyStateActionButton, timeout: networkTimeout),
            "Empty state action button should appear to confirm the dashboard has loaded"
        )
        takeScreenshot(named: "LatestTestResultCard_DashboardLoaded")

        XCTAssertFalse(
            latestTestCard.exists,
            "Latest test result card should not exist when latestTestResult is nil"
        )
        takeScreenshot(named: "LatestTestResultCard_Absent")
    }

    func testDateLabel_RendersWhenDateFormattedIsNonNil() {
        XCTAssertTrue(
            wait(for: latestTestCard, timeout: networkTimeout),
            "Latest test result card should appear before checking the date label"
        )
        takeScreenshot(named: "DateLabel_CardLoaded")

        let datePredicate = NSPredicate(format: "label BEGINSWITH 'Latest Result, '")
        let dateHeaderElement = app.otherElements.matching(datePredicate).firstMatch
        XCTAssertTrue(
            dateHeaderElement.exists,
            "Date header element should exist with a label beginning 'Latest Result, ' when dateFormatted is non-nil"
        )
        takeScreenshot(named: "DateLabel_Visible")
    }
}
