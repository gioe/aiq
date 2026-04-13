import XCTest

/// UI tests for the question grid toggle button.
///
/// Verifies that:
/// - The grid toggle button opens and closes the grid across multiple cycles
/// - Header controls remain tappable while the grid overlay is visible
///
/// Launches in `loggedInWithHistory` mock scenario so the dashboard is ready
/// immediately — no login step required.
final class QuestionGridToggleUITests: BaseUITest {
    // MARK: - Properties

    private var testHelper: TestTakingHelper!

    // MARK: - Element Queries

    /// The grid toggle button in the progress header.
    private var gridToggleButton: XCUIElement {
        app.buttons["testTakingView.questionNavigationGridToggle"]
    }

    /// First question navigation button — used as a proxy to confirm the grid is visible.
    /// Individual grid buttons are always surfaced by XCUITest; the grid container
    /// VStack may not be (it lacks `.accessibilityElement(children: .contain)`).
    private var firstGridButton: XCUIElement {
        app.buttons["testTakingView.questionNavigationButton.0"]
    }

    /// Progress label in the header ("1/20" format).
    private var progressLabel: XCUIElement {
        app.staticTexts["testTakingView.progressLabel"]
    }

    // MARK: - Launch Configuration

    override func setupLaunchConfiguration() {
        if mockScenario == "default" {
            mockScenario = "loggedInWithHistory"
        }
        super.setupLaunchConfiguration()
    }

    // MARK: - Setup & Teardown

    override func setUpWithError() throws {
        try super.setUpWithError()
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        testHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Grid Toggle Cycle Tests

    func testGridToggle_ThreeCycles_GridAppearsAndDisappearsEachTime() throws {
        try navigateToTestTaking()

        // Verify toggle button exists
        XCTAssertTrue(
            wait(for: gridToggleButton, timeout: standardTimeout),
            "Grid toggle button should exist"
        )

        // Grid should start hidden
        XCTAssertFalse(
            firstGridButton.exists,
            "Grid should be hidden initially"
        )

        // Three open/close cycles
        for cycle in 1 ... 3 {
            // Open the grid
            gridToggleButton.tap()
            XCTAssertTrue(
                firstGridButton.waitForExistence(timeout: standardTimeout),
                "Grid should appear after toggle tap (cycle \(cycle))"
            )

            // Close the grid
            gridToggleButton.tap()
            XCTAssertTrue(
                waitForDisappearance(of: firstGridButton, timeout: standardTimeout),
                "Grid should disappear after second toggle tap (cycle \(cycle))"
            )
        }
    }

    func testGridToggle_ButtonRemainsResponsive_AfterFourCycles() throws {
        try navigateToTestTaking()

        XCTAssertTrue(
            wait(for: gridToggleButton, timeout: standardTimeout),
            "Grid toggle button should exist"
        )

        // Four full open/close cycles — one more than the minimum to verify
        // the button doesn't become unresponsive with repeated use.
        for _ in 1 ... 4 {
            gridToggleButton.tap()
            XCTAssertTrue(
                firstGridButton.waitForExistence(timeout: standardTimeout),
                "Grid should appear"
            )

            gridToggleButton.tap()
            XCTAssertTrue(
                waitForDisappearance(of: firstGridButton, timeout: standardTimeout),
                "Grid should disappear"
            )
        }

        // After all cycles the grid should be hidden and the button still hittable
        XCTAssertFalse(firstGridButton.exists, "Grid should be hidden after even number of toggles")
        XCTAssertTrue(gridToggleButton.isHittable, "Toggle button should remain hittable")
    }

    // MARK: - Header Controls Tappable While Grid Shown

    func testHeaderControls_RemainTappable_WhileGridIsVisible() throws {
        try navigateToTestTaking()

        // Open the grid
        XCTAssertTrue(wait(for: gridToggleButton, timeout: standardTimeout))
        gridToggleButton.tap()
        XCTAssertTrue(
            firstGridButton.waitForExistence(timeout: standardTimeout),
            "Grid should be visible"
        )

        // Verify the toggle button itself is still hittable (it lives in the header
        // above the grid overlay). This is the regression test for TASK-405 where
        // the ZStack allowed the grid overlay to intercept header touches.
        XCTAssertTrue(
            gridToggleButton.isHittable,
            "Grid toggle button should remain hittable while grid is shown"
        )

        // Verify the progress label is still visible
        XCTAssertTrue(
            progressLabel.exists,
            "Progress label should remain visible while grid is shown"
        )

        // Close the grid via the toggle to confirm it's truly tappable
        gridToggleButton.tap()
        XCTAssertTrue(
            waitForDisappearance(of: firstGridButton, timeout: standardTimeout),
            "Grid should close — confirming the toggle button received the tap while grid was visible"
        )
    }

    func testExitButton_RemainsTappable_WhileGridIsVisible() throws {
        try navigateToTestTaking()

        // Open the grid
        XCTAssertTrue(wait(for: gridToggleButton, timeout: standardTimeout))
        gridToggleButton.tap()
        XCTAssertTrue(
            firstGridButton.waitForExistence(timeout: standardTimeout),
            "Grid should be visible"
        )

        // The exit button is in the header — verify it's hittable with grid shown
        let exitButton = app.buttons["testTakingView.exitButton"]
        XCTAssertTrue(
            exitButton.exists,
            "Exit button should exist while grid is shown"
        )
        XCTAssertTrue(
            exitButton.isHittable,
            "Exit button should remain hittable while grid is shown"
        )
    }

    // MARK: - Private Helpers

    private func navigateToTestTaking() throws {
        let testStarted = testHelper.startNewTest(waitForFirstQuestion: true)
        guard testStarted else {
            throw XCTSkip("Could not start test from dashboard")
        }
    }
}
