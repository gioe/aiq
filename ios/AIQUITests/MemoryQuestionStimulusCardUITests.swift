//
//  MemoryQuestionStimulusCardUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 03/04/26.
//

import XCTest

/// UI tests that verify the `stimulusCard` accessibility identifier survives the
/// `UIViewRepresentable` bridge introduced by the `.screenshotPrevented()` modifier.
///
/// The `.screenshotPrevented()` modifier wraps the stimulus `VStack` inside a
/// `UIHostingController` embedded in a `UITextField`'s secure canvas.  This UIKit
/// bridge layer can reorder the accessibility tree, making elements set via SwiftUI's
/// `.accessibilityIdentifier(_:)` unreachable from XCUITest.
///
/// These tests launch the app with the `memoryInProgress` mock scenario so the
/// dashboard immediately shows an in-progress session whose first question is a
/// memory type.  After tapping Resume the TestTakingView renders `MemoryQuestionView`
/// in stimulus phase, and the tests assert that
/// `AccessibilityIdentifiers.MemoryQuestionView.stimulusCard`
/// (`"memoryQuestionView.stimulusCard"`) is both present and hittable.
final class MemoryQuestionStimulusCardUITests: BaseUITest {
    // MARK: - Constants

    /// UITextField's intrinsic secure-canvas height; the TASK-1370 fix must exceed this.
    private let uiTextFieldDefaultHeight: CGFloat = 34

    // MARK: - Convenience References

    private var resumeButton: XCUIElement {
        app.buttons["dashboardView.resumeButton"]
    }

    private var stimulusCard: XCUIElement {
        app.otherElements["memoryQuestionView.stimulusCard"]
    }

    // MARK: - Launch Configuration

    /// Boot the app with `memoryInProgress` so `getActiveTest()` returns a session
    /// whose first question is a memory type.  The guard on `mockScenario == "default"`
    /// preserves compatibility with `relaunchWithScenario(_:)` per the contract
    /// documented in `BaseUITest`.
    override func setupLaunchConfiguration() {
        if mockScenario == "default" {
            mockScenario = "memoryInProgress"
        }
        super.setupLaunchConfiguration()
    }

    // MARK: - Stimulus Card Accessibility Tests

    func testStimulusCard_ExistsWhenStimulusPhaseIsShowing() {
        XCTAssertTrue(
            wait(for: resumeButton, timeout: networkTimeout),
            "Resume button should be visible when an active memory test session exists"
        )
        resumeButton.tap()

        // The stimulusCard identifier must survive the UIViewRepresentable bridge
        // applied by screenshotPrevented().
        XCTAssertTrue(
            wait(for: stimulusCard, timeout: extendedTimeout),
            "memoryQuestionView.stimulusCard should be reachable via XCUITest " +
                "after the UIViewRepresentable bridge introduced by screenshotPrevented()"
        )
        takeScreenshot(named: "StimulusCard_Exists")
    }

    func testStimulusCard_IsHittableWhenStimulusPhaseIsShowing() {
        XCTAssertTrue(
            wait(for: resumeButton, timeout: networkTimeout),
            "Resume button should appear before navigating to the test"
        )
        resumeButton.tap()

        guard wait(for: stimulusCard, timeout: extendedTimeout) else {
            XCTFail("Stimulus card did not appear after resuming the test")
            return
        }

        XCTAssertTrue(
            waitForHittable(stimulusCard, timeout: extendedTimeout),
            "memoryQuestionView.stimulusCard should be hittable, confirming the " +
                "UIViewRepresentable bridge does not suppress the element's hit-testability"
        )
        takeScreenshot(named: "StimulusCard_Hittable")
    }

    /// Regression guard for TASK-1370: verifies the stimulus card renders taller than
    /// UITextField's default secure-canvas height (~34 pt).
    ///
    /// Without the `preferredSizeProvider` wiring added to `ScreenshotContainerView` in
    /// TASK-1370, the `UIHostingController` would be constrained to UITextField's intrinsic
    /// ~34 pt height.  This test fails if either the `preferredSizeProvider` closure or the
    /// `invalidateIntrinsicContentSize()` call is accidentally removed.
    func testStimulusCard_HeightExceedsUITextFieldDefault() {
        XCTAssertTrue(
            wait(for: resumeButton, timeout: networkTimeout),
            "Resume button should appear before navigating to the test"
        )
        resumeButton.tap()

        guard wait(for: stimulusCard, timeout: extendedTimeout) else {
            XCTFail("Stimulus card did not appear after resuming the test")
            return
        }

        let height = stimulusCard.frame.height
        XCTAssertGreaterThan(
            height,
            uiTextFieldDefaultHeight,
            "Stimulus card height (\(height)pt) should exceed UITextField's default " +
                "~\(uiTextFieldDefaultHeight)pt, confirming preferredSizeProvider is wired in ScreenshotContainerView"
        )
        takeScreenshot(named: "StimulusCard_Height")
    }
}
