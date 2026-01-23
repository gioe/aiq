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

    // MARK: - Setup

    override func setUpWithError() throws {
        // Set mock scenario before calling super (which launches the app)
        mockScenario = "loggedInWithHistory"

        try super.setUpWithError()

        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
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
        captureScreenshot(named: "01_Dashboard", caption: "Track your cognitive performance")

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

        captureScreenshot(named: "01_Dashboard", caption: "Track your cognitive performance")
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

        captureScreenshot(named: "03_Results", caption: "Detailed performance insights")
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

    /// Capture a screenshot with a descriptive name
    private func captureScreenshot(named name: String, caption: String? = nil) {
        // Allow UI to settle
        Thread.sleep(forTimeInterval: 0.3)

        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)

        print("[\(name)] Screenshot captured" + (caption.map { " - \($0)" } ?? ""))
    }

    /// Start a test and navigate to the question screen
    private func captureTestQuestionScreenshot() {
        // Look for Start Test button
        let startTestButton = app.buttons["dashboardView.startTestButton"]
        if startTestButton.waitForExistence(timeout: standardTimeout) {
            startTestButton.tap()

            // Wait for first question to appear
            let questionCard = app.otherElements["testTakingView.questionCard"]
            if questionCard.waitForExistence(timeout: networkTimeout) {
                // Allow question to fully render
                Thread.sleep(forTimeInterval: 0.5)
                captureScreenshot(named: "02_TestQuestion", caption: "AI-generated cognitive assessments")
            } else {
                // Fallback - capture whatever test screen is showing
                captureScreenshot(named: "02_TestQuestion", caption: "AI-generated cognitive assessments")
            }
        } else {
            print("[Warning] Start Test button not found - may need to clear existing test")
            captureScreenshot(named: "02_TestQuestion_Fallback", caption: "Test screen")
        }
    }

    /// Start test and answer some questions for results screen
    private func startTestAndAnswerQuestions() {
        let startTestButton = app.buttons["dashboardView.startTestButton"]
        guard startTestButton.waitForExistence(timeout: standardTimeout) else {
            return
        }
        startTestButton.tap()

        // Wait for test to start
        let questionCard = app.otherElements["testTakingView.questionCard"]
        guard questionCard.waitForExistence(timeout: networkTimeout) else {
            return
        }

        // Answer questions (mock will accept any answers)
        for questionIndex in 1 ... 5 {
            // Find and tap first answer option
            let answerOption = app.buttons.matching(
                NSPredicate(format: "identifier CONTAINS 'answerOption'")
            ).firstMatch

            if answerOption.waitForExistence(timeout: standardTimeout) {
                answerOption.tap()
            }

            // Move to next question if not the last one
            if questionIndex < 5 {
                let nextButton = app.buttons["testTakingView.nextButton"]
                if nextButton.waitForExistence(timeout: quickTimeout) {
                    nextButton.tap()
                }
            }

            // Brief pause between questions
            Thread.sleep(forTimeInterval: 0.3)
        }
    }

    /// Submit the test and wait for results
    private func submitTestAndWaitForResults() {
        // Look for submit button
        let submitButton = app.buttons["testTakingView.submitButton"]
        if submitButton.waitForExistence(timeout: standardTimeout) {
            submitButton.tap()
        }

        // Wait for results screen
        let resultsView = app.otherElements["testResultsView"]
        _ = resultsView.waitForExistence(timeout: networkTimeout)

        // Allow results to fully animate
        Thread.sleep(forTimeInterval: 0.5)
    }

    /// Capture results screenshot
    private func captureResultsScreenshot() {
        startTestAndAnswerQuestions()
        submitTestAndWaitForResults()
        captureScreenshot(named: "03_Results", caption: "Detailed performance insights")
    }

    /// Navigate to history and capture screenshot
    private func captureHistoryScreenshot() {
        // Navigate to History tab
        let historyTab = app.buttons["History"]
        guard historyTab.waitForExistence(timeout: standardTimeout) else {
            print("[Warning] History tab not found")
            return
        }
        historyTab.tap()

        // Wait for history content to load
        let historyList = app.tables.firstMatch
        _ = historyList.waitForExistence(timeout: networkTimeout)

        // Allow chart to animate
        Thread.sleep(forTimeInterval: 0.8)

        captureScreenshot(named: "04_History", caption: "Monitor your trends over time")
    }

    /// Capture domain scores breakdown
    private func captureDomainScoresScreenshot() {
        // Check if we're on results screen with domain scores visible
        let domainScoresSection = app.otherElements["testResultsView.domainScores"]
        if domainScoresSection.exists {
            // Scroll to domain scores if needed
            domainScoresSection.swipeUp()
            Thread.sleep(forTimeInterval: 0.3)
            captureScreenshot(named: "05_DomainScores", caption: "Understand your strengths")
            return
        }

        // Alternative: Navigate to history and tap on a result to see domain scores
        let historyTab = app.buttons["History"]
        if historyTab.waitForExistence(timeout: standardTimeout) {
            historyTab.tap()

            // Tap first history item
            let firstItem = app.cells.firstMatch
            if firstItem.waitForExistence(timeout: standardTimeout) {
                firstItem.tap()

                // Wait for detail view
                Thread.sleep(forTimeInterval: 0.5)

                captureScreenshot(named: "05_DomainScores", caption: "Understand your strengths")
            }
        }
    }

    /// Navigate to settings and capture screenshot
    private func captureSettingsScreenshot() {
        let settingsTab = app.buttons["Settings"]
        guard settingsTab.waitForExistence(timeout: standardTimeout) else {
            print("[Warning] Settings tab not found")
            return
        }
        settingsTab.tap()

        // Wait for settings to load
        Thread.sleep(forTimeInterval: 0.3)

        captureScreenshot(named: "06_Settings", caption: "Privacy-first design")
    }
}

// MARK: - Onboarding Screenshots

extension AppStoreScreenshotTests {
    /// Capture onboarding/welcome screens
    ///
    /// This test requires a fresh install state (not logged in).
    func testCaptureOnboarding() throws {
        // Relaunch in logged out state to see welcome screen
        relaunchAsLoggedOut()

        // Need to also skip onboarding skip to see the actual onboarding
        app.terminate()
        Thread.sleep(forTimeInterval: appTerminationDelay)

        // Configure for onboarding capture
        let onboardingApp = XCUIApplication()
        onboardingApp.launchArguments.append("-UITestMockMode")
        onboardingApp.launchEnvironment["MOCK_SCENARIO"] = "loggedOut"
        // Don't skip onboarding for this test
        onboardingApp.launchArguments.append("-hasCompletedOnboarding")
        onboardingApp.launchArguments.append("0")
        onboardingApp.launch()

        // Wait for onboarding to appear
        let onboardingContainer = onboardingApp.otherElements["onboardingContainer"]
        if onboardingContainer.waitForExistence(timeout: standardTimeout) {
            // Capture first onboarding page
            captureOnboardingScreenshot(app: onboardingApp, named: "Onboarding_01_Welcome")

            // Advance through pages
            let nextButton = onboardingApp.buttons["onboarding.nextButton"]
            for pageNum in 2 ... 4 where nextButton.waitForExistence(timeout: quickTimeout) {
                nextButton.tap()
                Thread.sleep(forTimeInterval: 0.3)
                captureOnboardingScreenshot(app: onboardingApp, named: "Onboarding_0\(pageNum)")
            }
        } else {
            // Capture welcome/login screen
            let welcomeIcon = onboardingApp.images["welcomeView.brainIcon"]
            if welcomeIcon.waitForExistence(timeout: standardTimeout) {
                captureOnboardingScreenshot(app: onboardingApp, named: "Welcome_Login")
            }
        }
    }

    private func captureOnboardingScreenshot(app: XCUIApplication, named name: String) {
        Thread.sleep(forTimeInterval: 0.3)
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        print("[\(name)] Onboarding screenshot captured")
    }
}
