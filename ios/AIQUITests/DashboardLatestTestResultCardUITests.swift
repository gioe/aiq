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
            wait(for: dateHeaderElement, timeout: standardTimeout),
            "Date header element should appear with a label beginning 'Latest Result, ' when dateFormatted is non-nil"
        )
        takeScreenshot(named: "DateLabel_Visible")
    }

    func testDateLabel_IsAbsentWhenDateFormattedIsNil() {
        relaunchWithScenario("loggedInWithHistoryNilDate")

        XCTAssertTrue(
            wait(for: latestTestCard, timeout: networkTimeout),
            "Latest test result card should still render when dateFormatted is nil"
        )
        takeScreenshot(named: "DateLabel_Nil_CardVisible")

        // Accessibility label must be exactly "Latest Result" with no date suffix
        let exactLabelPredicate = NSPredicate(format: "label == 'Latest Result'")
        let noDateHeaderElement = app.otherElements.matching(exactLabelPredicate).firstMatch
        XCTAssertTrue(
            wait(for: noDateHeaderElement, timeout: standardTimeout),
            "Card header accessibility label should be exactly 'Latest Result' when dateFormatted is nil"
        )
        takeScreenshot(named: "DateLabel_Nil_NoDateSuffix")

        // No element should exist with the date-suffix variant
        let dateSuffixPredicate = NSPredicate(format: "label BEGINSWITH 'Latest Result, '")
        let dateSuffixElement = app.otherElements.matching(dateSuffixPredicate).firstMatch
        XCTAssertFalse(
            dateSuffixElement.exists,
            "Card header should not carry a date suffix when dateFormatted is nil"
        )
        takeScreenshot(named: "DateLabel_Nil_Confirmed")
    }
}
