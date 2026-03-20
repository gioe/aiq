//
//  AppStoreScreenshotTests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/23/26.
//

import XCTest

/// UI tests for generating App Store screenshots
///
/// These tests capture screenshots for App Store submission across all required device sizes.
/// Run these tests on specific simulators to generate correctly-sized screenshots:
///
/// ## Required Device Sizes
/// - iPhone 16 Pro Max (6.9") - 1320 x 2868
/// - iPhone 15 Pro Max (6.7") - 1290 x 2796
/// - iPhone XS Max (6.5") - 1242 x 2688
/// - iPhone 8 Plus (5.5") - 1242 x 2208
/// - iPad Pro 12.9" (6th gen) - 2048 x 2732
///
/// ## Usage
///
/// Run on specific simulator:
/// ```bash
/// xcodebuild test \
///   -project AIQ.xcodeproj \
///   -scheme AIQ \
///   -destination 'platform=iOS Simulator,name=iPhone 16 Pro Max' \
///   -only-testing:AIQUITests/AppStoreScreenshotTests
/// ```
///
/// Or run the provided script:
/// ```bash
/// ./ios/scripts/generate-app-store-screenshots.sh
/// ```
///
/// ## Screenshot Order (matches APP_STORE_METADATA.md)
///
/// 1. Dashboard - Home screen with test status
/// 2. Test Question - Active test with sample question
/// 3. Results - IQ score and domain breakdown
/// 4. History - Test history with trend chart
/// 5. Domain Scores - Six cognitive domains breakdown
/// 6. Settings - Privacy-focused settings
final class AppStoreScreenshotTests: BaseUITest {
    // MARK: - Properties

    private var loginHelper: LoginHelper!
    private var navHelper: NavigationHelper!
    private var testHelper: TestTakingHelper!

    /// Directory for screenshot output
    private let screenshotDirectory = "app-store/screenshots"

    /// Timeout for UI animations to settle before taking screenshots
    private let animationSettleTimeout: TimeInterval = 1.0

    /// Flag to enable onboarding flow (don't skip it)
    /// Set to true before relaunching to capture onboarding screenshots
    private var enableOnboardingFlow = false

    // MARK: - Setup

    override func setUpWithError() throws {
        // Set mock scenario before calling super (which launches the app)
        mockScenario = "loggedInWithHistory"

        try super.setUpWithError()

        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    /// Override to conditionally skip onboarding based on enableOnboardingFlow flag
    override func setupLaunchConfiguration() {
        // Enable mock mode for UI tests
        app.launchArguments.append("-UITestMockMode")

        // Set the mock scenario via environment variable
        app.launchEnvironment["MOCK_SCENARIO"] = mockScenario

        // Conditionally skip/enable onboarding
        app.launchArguments.append("-hasCompletedOnboarding")
        app.launchArguments.append(enableOnboardingFlow ? "0" : "1")

        // Privacy consent is always accepted: onboarding appears after consent in the RootView flow,
        // so disabling consent would show PrivacyConsentView instead of OnboardingContainerView.
        app.launchArguments.append("-com.aiq.privacyConsentAccepted")
        app.launchArguments.append("1")
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        navHelper = nil
        testHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - Screenshot Tests

    /// Generate all App Store screenshots in sequence
    ///
    /// This test captures all 6 screenshots in the recommended order for App Store submission.
    /// Screenshots are attached to the test results and can be extracted from the xcresult bundle.
    func testGenerateAllScreenshots() {
        // Wait for app to be ready
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear after launch"
        )

        // 1. Dashboard Screenshot
        XCTAssertTrue(dashboardTab.isHittable, "Dashboard tab should be interactable")
        takeScreenshot(named: "01_Dashboard")

        // 2. Start a test and capture question screen
        captureTestQuestionScreenshot()

        // 3. Submit test and capture results
        captureResultsScreenshot()

        // 4. Navigate to History and capture trends
        captureHistoryScreenshot()

        // 5. Capture domain scores detail
        captureDomainScoresScreenshot()

        // 6. Navigate to Settings
        captureSettingsScreenshot()
    }

    // MARK: - Individual Screenshot Captures

    /// Capture the dashboard/home screen
    func testCaptureDashboard() {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )
        XCTAssertTrue(dashboardTab.isHittable, "Dashboard tab should be interactable")

        takeScreenshot(named: "01_Dashboard")
    }

    /// Capture an active test question
    func testCaptureTestQuestion() {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )

        captureTestQuestionScreenshot()
    }

    /// Capture test results screen
    func testCaptureResults() {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )

        // Start and submit a test to get results
        startTestAndAnswerQuestions()
        submitTestAndWaitForResults()

        let scoreLabel = app.otherElements["testResultsView.scoreLabel"]
        XCTAssertTrue(scoreLabel.exists, "Results view should be visible")
        takeScreenshot(named: "03_Results")
    }

    /// Capture history/trends screen
    func testCaptureHistory() {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )

        captureHistoryScreenshot()
    }

    /// Capture settings screen
    func testCaptureSettings() {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )

        captureSettingsScreenshot()
    }

    // MARK: - Screenshot Helpers

    /// Wait for UI to settle after animations by waiting for element to be hittable
    /// - Parameter element: Element to wait for to be hittable before taking screenshot
    private func waitForUIToSettle(element: XCUIElement) {
        _ = waitForHittable(element, timeout: animationSettleTimeout)
    }

    /// Start a test and navigate to the question screen
    private func captureTestQuestionScreenshot() {
        // Look for Start Test button (identifier matches DashboardView.actionButton)
        let startTestButton = app.buttons["dashboardView.actionButton"]
        guard startTestButton.waitForExistence(timeout: standardTimeout) else {
            XCTFail("Start Test button not found")
            return
        }
        startTestButton.tap()

        // Wait for first question to appear
        let questionCard = app.otherElements["testTakingView.questionCard"]
        XCTAssertTrue(
            questionCard.waitForExistence(timeout: networkTimeout),
            "Question card should appear"
        )

        // Wait for question UI to be fully rendered
        waitForUIToSettle(element: questionCard)

        takeScreenshot(named: "02_TestQuestion")
    }

    /// Start test and answer some questions for results screen
    private func startTestAndAnswerQuestions() {
        // Use descendants(matching: .any) per CLAUDE.md note: the questionCard element
        // (Color.clear overlay) may map to a non-.other type depending on iOS version.
        let questionCard = app.descendants(matching: .any)["testTakingView.questionCard"]
        let questionText = app.descendants(matching: .any)["testTakingView.questionText"]

        // Only start a new test if not already in the test-taking view
        let alreadyInTest = questionCard.exists || questionText.exists
        if !alreadyInTest {
            let startTestButton = app.buttons["dashboardView.actionButton"]
            guard startTestButton.waitForExistence(timeout: standardTimeout) else {
                XCTFail("Start Test button not found")
                return
            }
            startTestButton.tap()

            let appeared = questionText.waitForExistence(timeout: networkTimeout) ||
                questionCard.waitForExistence(timeout: networkTimeout)
            guard appeared else {
                XCTFail("Question card did not appear")
                return
            }
        }

        // Answer all questions until the submit button appears.
        // Uses a max-iteration cap to avoid infinite loops in unexpected states.
        for _ in 1 ... 20 {
            // Handle memory question stimulus phase: tap Continue before answer options appear
            let continueButton = app.buttons["memoryQuestionView.continueButton"]
            if continueButton.waitForExistence(timeout: quickTimeout) {
                continueButton.tap()
            }

            // Try multiple-choice answer buttons first (identifier: testTakingView.answerButton.N)
            let mcAnswer = app.buttons.matching(
                NSPredicate(format: "identifier BEGINSWITH %@", "testTakingView.answerButton.")
            ).firstMatch

            if mcAnswer.waitForExistence(timeout: standardTimeout) {
                mcAnswer.tap()
            } else {
                // Fall back to text input for open-ended questions (math, pattern, etc.)
                let textField = app.textFields["testTakingView.answerTextField"]
                if textField.waitForExistence(timeout: standardTimeout) {
                    textField.tap()
                    textField.typeText("42")
                }
            }

            // Stop answering once the submit button is visible (last question answered)
            let submitButton = app.buttons["testTakingView.submitButton"]
            if submitButton.waitForExistence(timeout: quickTimeout) {
                break
            }

            // Advance to the next question
            let nextButton = app.buttons["testTakingView.nextButton"]
            if nextButton.waitForExistence(timeout: quickTimeout), nextButton.isEnabled {
                nextButton.tap()
                _ = questionCard.waitForExistence(timeout: quickTimeout)
            } else {
                break
            }
        }
    }

    /// Submit the test and navigate to the results screen.
    ///
    /// After submission the app shows TestCompletionView first, then TestResultsView
    /// once the user taps "View Results". This method handles both transitions.
    private func submitTestAndWaitForResults() {
        let submitButton = app.buttons["testTakingView.submitButton"]
        guard submitButton.waitForExistence(timeout: standardTimeout) else {
            XCTFail("Submit button not found")
            return
        }
        submitButton.tap()

        // TestCompletionView appears immediately after submission
        let completionOverlay = app.otherElements["testCompletionView.successOverlay"]
        if completionOverlay.waitForExistence(timeout: networkTimeout) {
            // Tap "View Results" to navigate to TestResultsView
            let viewResultsButton = app.buttons["testCompletionView.viewResultsButton"]
            if viewResultsButton.waitForExistence(timeout: standardTimeout) {
                viewResultsButton.tap()
            }
        }

        // Wait for the results score label to confirm TestResultsView is loaded
        let scoreLabel = app.otherElements["testResultsView.scoreLabel"]
        XCTAssertTrue(
            scoreLabel.waitForExistence(timeout: networkTimeout),
            "Results view should appear"
        )

        waitForUIToSettle(element: scoreLabel)
    }

    /// Capture results screenshot
    private func captureResultsScreenshot() {
        startTestAndAnswerQuestions()
        submitTestAndWaitForResults()

        let scoreLabel = app.otherElements["testResultsView.scoreLabel"]
        XCTAssertTrue(scoreLabel.exists, "Results view should be visible")
        takeScreenshot(named: "03_Results")
    }

    /// Navigate to history and capture screenshot
    private func captureHistoryScreenshot() {
        // If we're on the TestResultsView, tap Done to return to the main tab bar
        let doneButton = app.buttons["testResultsView.doneButton"]
        if doneButton.waitForExistence(timeout: quickTimeout) {
            doneButton.tap()
        }

        // Navigate to History tab
        let historyTab = app.buttons["History"]
        guard historyTab.waitForExistence(timeout: standardTimeout) else {
            XCTFail("History tab not found")
            return
        }
        historyTab.tap()

        // Wait for history scroll view to load (HistoryView uses ScrollView, not UITableView)
        // Use descendants(matching: .any) because SwiftUI ScrollView can appear as .other in XCTest
        let historyList = app.descendants(matching: .any)["historyView.scrollView"]
        XCTAssertTrue(
            historyList.waitForExistence(timeout: networkTimeout),
            "History scroll view should appear"
        )

        // Wait for chart animations to complete
        waitForUIToSettle(element: historyList)

        takeScreenshot(named: "04_History")
    }

    /// Capture domain scores breakdown
    private func captureDomainScoresScreenshot() {
        // Check if we're on results screen with domain scores visible
        let domainScoresSection = app.otherElements["testResultsView.domainScoresSection"]
        if domainScoresSection.exists {
            domainScoresSection.swipeUp()
            waitForUIToSettle(element: domainScoresSection)
            takeScreenshot(named: "05_DomainScores")
            return
        }

        // Navigate to History tab and tap the first result to see its detail/domain scores.
        // HistoryView uses a ScrollView with identifiers "historyView.testRow.N" (not UITableView cells).
        let historyTab = app.buttons["History"]
        guard historyTab.waitForExistence(timeout: standardTimeout) else {
            XCTFail("History tab not found")
            return
        }
        historyTab.tap()

        let firstItem = app.descendants(matching: .any)["historyView.testRow.0"]
        guard firstItem.waitForExistence(timeout: standardTimeout) else {
            XCTFail("No history items found")
            return
        }
        firstItem.tap()

        // Wait for detail view to appear (result is discarded — screenshot is taken regardless)
        let detailView = app.otherElements["testDetailView"]
        _ = detailView.waitForExistence(timeout: standardTimeout)
        waitForUIToSettle(element: detailView)

        takeScreenshot(named: "05_DomainScores")
    }

    /// Navigate to settings and capture screenshot
    private func captureSettingsScreenshot() {
        let settingsTab = app.buttons["Settings"]
        guard settingsTab.waitForExistence(timeout: standardTimeout) else {
            XCTFail("Settings tab not found")
            return
        }
        settingsTab.tap()

        // Wait for settings to load
        let settingsView = app.navigationBars["Settings"]
        XCTAssertTrue(
            settingsView.waitForExistence(timeout: standardTimeout),
            "Settings should appear"
        )
        waitForUIToSettle(element: settingsView)

        takeScreenshot(named: "06_Settings")
    }
}

// MARK: - Onboarding Screenshots

extension AppStoreScreenshotTests {
    /// Capture onboarding/welcome screens
    ///
    /// This test requires an authenticated user who has not completed onboarding.
    /// Uses loggedInNoHistory mock scenario with onboarding not completed, so that
    /// RootView routes to OnboardingContainerView (auth ✓, onboarding ✗).
    /// Note: This test is not part of testGenerateAllScreenshots because it requires
    /// a different app configuration (onboarding enabled).
    func testCaptureOnboarding() {
        // Enable onboarding flow and relaunch as authenticated (no history).
        // OnboardingContainerView only appears for authenticated users with hasCompletedOnboarding=false.
        enableOnboardingFlow = true
        relaunchWithScenario("loggedInNoHistory")

        // Wait for onboarding to appear (identifier: "onboardingView.containerView")
        let onboardingContainer = app.otherElements["onboardingView.containerView"]
        if onboardingContainer.waitForExistence(timeout: standardTimeout) {
            // Capture first onboarding page
            XCTAssertTrue(onboardingContainer.exists, "Onboarding container should be visible")
            captureOnboardingScreenshot(named: "Onboarding_01_Welcome", waitElement: onboardingContainer)

            // Advance through pages using correct button identifiers
            for pageNum in 2 ... 4 {
                let buttonId = pageNum == 4
                    ? "onboardingView.getStartedButton"
                    : "onboardingView.continueButton"
                let advanceButton = app.buttons[buttonId]
                guard advanceButton.waitForExistence(timeout: quickTimeout) else { break }
                advanceButton.tap()
                // Wait for page transition
                _ = onboardingContainer.waitForExistence(timeout: quickTimeout)
                captureOnboardingScreenshot(named: "Onboarding_0\(pageNum)", waitElement: onboardingContainer)
            }
        } else {
            // Capture welcome/login screen (email field is the reliable sentinel)
            let emailTextField = app.textFields["welcomeView.emailTextField"]
            XCTAssertTrue(
                emailTextField.waitForExistence(timeout: standardTimeout),
                "Welcome/login screen should appear"
            )
            captureOnboardingScreenshot(named: "Welcome_Login", waitElement: emailTextField)
        }

        // Reset flag for subsequent tests
        enableOnboardingFlow = false
    }

    private func captureOnboardingScreenshot(named name: String, waitElement: XCUIElement) {
        // Wait for UI to settle
        waitForUIToSettle(element: waitElement)

        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        print("[\(name)] Onboarding screenshot captured")
    }
}
