//
//  MemoryQuestionStimulusCardUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 03/04/26.
//

import XCTest

/// UI tests that verify the `stimulusCard` accessibility identifier is reachable from XCUITest.
///
/// The stimulus card contains an inner `Text(stimulus)` wrapped in `.screenshotPrevented()`, which
/// backs the view with a `UIViewRepresentable` (`ScreenshotContainerView`).  Because the element type
/// is determined at runtime by that UIKit bridge, the tests use `.descendants(matching: .any)` rather
/// than a type-specific query — this surfaces the identifier regardless of how XCTest classifies the
/// element.
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
        // Search all element types — if stimulusCard exists but with an unexpected type,
        // this will surface the identifier while a separate assertion on element type can follow.
        app.descendants(matching: .any)["memoryQuestionView.stimulusCard"]
    }

    private var continueButton: XCUIElement {
        // Use descendants(matching: .any) to surface the button regardless of element type,
        // in case the PrimaryButton's accessibility traits cause type mismatch with app.buttons.
        app.descendants(matching: .any)["memoryQuestionView.continueButton"]
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

        // Confirm navigation to TestTakingView completed
        XCTAssertTrue(
            wait(for: app.buttons["testTakingView.exitButton"], timeout: extendedTimeout),
            "TestTakingView exitButton must appear — navigation to test screen failed"
        )

        assertStimulusPhaseReady()

        // Use descendants(matching: .any) because the UIViewRepresentable backing
        // screenshotPrevented may change the element type XCTest assigns to the card.
        XCTAssertTrue(
            wait(for: stimulusCard, timeout: extendedTimeout),
            "memoryQuestionView.stimulusCard should be reachable via XCUITest as a native SwiftUI element"
        )
        takeScreenshot(named: "StimulusCard_Exists")
    }

    func testStimulusCard_IsHittableWhenStimulusPhaseIsShowing() {
        XCTAssertTrue(
            wait(for: resumeButton, timeout: networkTimeout),
            "Resume button should appear before navigating to the test"
        )
        resumeButton.tap()

        // Wait for TestTakingView navigation to complete before asserting stimulus card
        _ = wait(for: app.buttons["testTakingView.exitButton"], timeout: extendedTimeout)

        guard wait(for: stimulusCard, timeout: extendedTimeout) else {
            XCTFail("Stimulus card did not appear after resuming the test")
            return
        }

        XCTAssertTrue(
            waitForHittable(stimulusCard, timeout: extendedTimeout),
            "memoryQuestionView.stimulusCard should be hittable as a native SwiftUI element"
        )
        takeScreenshot(named: "StimulusCard_Hittable")
    }

    /// Verifies the stimulus card renders taller than UITextField's default height (~34 pt).
    ///
    /// The card shell contains a `.screenshotPrevented()` element backed by a `UIViewRepresentable`,
    /// so its height is determined by SwiftUI layout plus the `preferredSizeProvider` wired into
    /// `ScreenshotContainerView`.  This test guards against any regression where that sizing is lost.
    func testStimulusCard_HeightExceedsUITextFieldDefault() {
        XCTAssertTrue(
            wait(for: resumeButton, timeout: networkTimeout),
            "Resume button should appear before navigating to the test"
        )
        resumeButton.tap()

        // Wait for TestTakingView navigation to complete before asserting stimulus card
        _ = wait(for: app.buttons["testTakingView.exitButton"], timeout: extendedTimeout)

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

    // MARK: - Helpers

    /// Collects diagnostic state, takes a screenshot, and asserts that the app is
    /// in the stimulus phase (memory container present, question phase absent,
    /// continue button reachable).
    private func assertStimulusPhaseReady() {
        let loadFailureOverlay = app.otherElements["testTakingView.loadFailureOverlay"]
        let debugState = app.staticTexts["testTakingView.debugState"]
        let memoryContainer = app.descendants(matching: .any)["memoryQuestionView.container"]
        let questionCardAny = app.descendants(matching: .any)["testTakingView.questionCard"]
        let answerInput = app.descendants(matching: .any)["answerInput.container"]

        let hasLoadFailure = loadFailureOverlay.exists
        let hasDebugState = debugState.waitForExistence(timeout: 5)
        let hasMemoryContainer = memoryContainer.waitForExistence(timeout: 5)
        let hasQuestionCard = questionCardAny.exists
        let hasAnswerInput = answerInput.exists
        let debugLabel = hasDebugState ? debugState.label : "(not found)"
        let hasQuestionPhase = app.descendants(matching: .any)["memoryQuestionView.questionPhase"].exists

        takeScreenshot(named: "AfterExitButton_BeforeContinue")

        XCTAssertFalse(hasLoadFailure, "DIAG: load failure overlay IS showing — questions failed to load")
        XCTAssertTrue(
            hasDebugState,
            "DIAG: debugState=\(debugLabel) loadFailure=\(hasLoadFailure) " +
                "memContainer=\(hasMemoryContainer) qCard=\(hasQuestionCard) answerInput=\(hasAnswerInput)"
        )
        XCTAssertTrue(
            hasMemoryContainer,
            "DIAG: memoryQuestionView.container not found. " +
                "debugState=\(debugLabel) qCard=\(hasQuestionCard) answerInput=\(hasAnswerInput)"
        )
        XCTAssertFalse(
            hasQuestionPhase,
            "DIAG: questionPhase IS showing (showingStimulus=false). " +
                "memContainer=\(hasMemoryContainer) debugState=\(debugLabel)"
        )

        let buttonIds = app.buttons.allElementsBoundByIndex.map(\.identifier).joined(separator: ", ")
        let stimulusCardExists = app.descendants(matching: .any)["memoryQuestionView.stimulusCard"].exists
        XCTAssertTrue(
            wait(for: continueButton, timeout: networkTimeout),
            "Continue button not found. Buttons present: [\(buttonIds)]. " +
                "stimulusCard=\(stimulusCardExists) debugState=\(debugLabel)"
        )
    }
}
