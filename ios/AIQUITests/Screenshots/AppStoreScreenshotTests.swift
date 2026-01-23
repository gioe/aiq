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
/// ./scripts/generate-app-store-screenshots.sh
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

        // Conditionally skip/enable privacy consent
        app.launchArguments.append("-com.aiq.privacyConsentAccepted")
        app.launchArguments.append(enableOnboardingFlow ? "0" : "1")
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
    func testGenerateAllScreenshots() throws {
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
    func testCaptureDashboard() throws {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )
        XCTAssertTrue(dashboardTab.isHittable, "Dashboard tab should be interactable")

        takeScreenshot(named: "01_Dashboard")
    }

    /// Capture an active test question
    func testCaptureTestQuestion() throws {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )

        captureTestQuestionScreenshot()
    }

    /// Capture test results screen
    func testCaptureResults() throws {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )

        // Start and submit a test to get results
        startTestAndAnswerQuestions()
        submitTestAndWaitForResults()

        let resultsView = app.otherElements["testResultsView"]
        XCTAssertTrue(resultsView.exists, "Results view should be visible")
        takeScreenshot(named: "03_Results")
    }

    /// Capture history/trends screen
    func testCaptureHistory() throws {
        let dashboardTab = app.buttons["Dashboard"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard should appear"
        )

        captureHistoryScreenshot()
    }

    /// Capture settings screen
    func testCaptureSettings() throws {
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
        // Look for Start Test button
        let startTestButton = app.buttons["dashboardView.startTestButton"]
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
        let startTestButton = app.buttons["dashboardView.startTestButton"]
        guard startTestButton.waitForExistence(timeout: standardTimeout) else {
            XCTFail("Start Test button not found")
            return
        }
        startTestButton.tap()

        // Wait for test to start
        let questionCard = app.otherElements["testTakingView.questionCard"]
        guard questionCard.waitForExistence(timeout: networkTimeout) else {
            XCTFail("Question card did not appear")
            return
        }

        // Answer 5 questions (mock will accept any answers)
        let totalQuestions = 5
        for questionIndex in 1 ... totalQuestions {
            // Find and tap first answer option
            let answerOption = app.buttons.matching(
                NSPredicate(format: "identifier CONTAINS 'answerOption'")
            ).firstMatch

            guard answerOption.waitForExistence(timeout: standardTimeout) else {
                continue
            }
            answerOption.tap()

            // Move to next question if not the last one
            if questionIndex < totalQuestions {
                let nextButton = app.buttons["testTakingView.nextButton"]
                if nextButton.waitForExistence(timeout: quickTimeout) {
                    nextButton.tap()
                    // Wait for next question to appear
                    _ = questionCard.waitForExistence(timeout: quickTimeout)
                }
            }
        }
    }

    /// Submit the test and wait for results
    private func submitTestAndWaitForResults() {
        // Look for submit button
        let submitButton = app.buttons["testTakingView.submitButton"]
        guard submitButton.waitForExistence(timeout: standardTimeout) else {
            XCTFail("Submit button not found")
            return
        }
        submitButton.tap()

        // Wait for results screen
        let resultsView = app.otherElements["testResultsView"]
        XCTAssertTrue(
            resultsView.waitForExistence(timeout: networkTimeout),
            "Results view should appear"
        )

        // Wait for results animations to complete
        waitForUIToSettle(element: resultsView)
    }

    /// Capture results screenshot
    private func captureResultsScreenshot() {
        startTestAndAnswerQuestions()
        submitTestAndWaitForResults()

        let resultsView = app.otherElements["testResultsView"]
        XCTAssertTrue(resultsView.exists, "Results view should be visible")
        takeScreenshot(named: "03_Results")
    }

    /// Navigate to history and capture screenshot
    private func captureHistoryScreenshot() {
        // Navigate to History tab
        let historyTab = app.buttons["History"]
        guard historyTab.waitForExistence(timeout: standardTimeout) else {
            XCTFail("History tab not found")
            return
        }
        historyTab.tap()

        // Wait for history content to load
        let historyList = app.tables.firstMatch
        XCTAssertTrue(
            historyList.waitForExistence(timeout: networkTimeout),
            "History list should appear"
        )

        // Wait for chart animations to complete
        waitForUIToSettle(element: historyList)

        takeScreenshot(named: "04_History")
    }

    /// Capture domain scores breakdown
    private func captureDomainScoresScreenshot() {
        // Check if we're on results screen with domain scores visible
        let domainScoresSection = app.otherElements["testResultsView.domainScores"]
        if domainScoresSection.exists {
            // Scroll to domain scores if needed
            domainScoresSection.swipeUp()
            waitForUIToSettle(element: domainScoresSection)
            XCTAssertTrue(domainScoresSection.isHittable, "Domain scores should be visible")
            takeScreenshot(named: "05_DomainScores")
            return
        }

        // Alternative: Navigate to history and tap on a result to see domain scores
        let historyTab = app.buttons["History"]
        guard historyTab.waitForExistence(timeout: standardTimeout) else {
            XCTFail("History tab not found")
            return
        }
        historyTab.tap()

        // Tap first history item
        let firstItem = app.cells.firstMatch
        guard firstItem.waitForExistence(timeout: standardTimeout) else {
            XCTFail("No history items found")
            return
        }
        firstItem.tap()

        // Wait for detail view to appear
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
    /// This test requires a fresh install state (not logged in).
    /// Uses loggedOut mock scenario with onboarding not completed.
    /// Note: This test is not part of testGenerateAllScreenshots because it requires
    /// a different app configuration (onboarding enabled).
    func testCaptureOnboarding() throws {
        // Enable onboarding flow and relaunch with logged out scenario
        enableOnboardingFlow = true
        relaunchWithScenario("loggedOut")

        // Wait for onboarding to appear
        let onboardingContainer = app.otherElements["onboardingContainer"]
        if onboardingContainer.waitForExistence(timeout: standardTimeout) {
            // Capture first onboarding page
            XCTAssertTrue(onboardingContainer.exists, "Onboarding container should be visible")
            captureOnboardingScreenshot(named: "Onboarding_01_Welcome", waitElement: onboardingContainer)

            // Advance through pages
            let nextButton = app.buttons["onboarding.nextButton"]
            for pageNum in 2 ... 4 where nextButton.waitForExistence(timeout: quickTimeout) {
                nextButton.tap()
                // Wait for page transition
                _ = onboardingContainer.waitForExistence(timeout: quickTimeout)
                captureOnboardingScreenshot(named: "Onboarding_0\(pageNum)", waitElement: onboardingContainer)
            }
        } else {
            // Capture welcome/login screen
            let welcomeIcon = app.images["welcomeView.brainIcon"]
            XCTAssertTrue(
                welcomeIcon.waitForExistence(timeout: standardTimeout),
                "Welcome screen should appear"
            )
            captureOnboardingScreenshot(named: "Welcome_Login", waitElement: welcomeIcon)
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
