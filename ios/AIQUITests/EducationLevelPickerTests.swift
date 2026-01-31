//
//  EducationLevelPickerTests.swift
//  AIQUITests
//
//  Created by Claude Code on 1/13/26.
//

import XCTest

/// UI tests for the education level picker in the registration flow
///
/// Tests cover:
/// - Opening the education level picker
/// - Selecting different education levels
/// - Verifying the selected value is displayed
/// - Default selection state
/// - Changing selection from one level to another
/// - Menu dismissal without selection
///
/// Related: BTS-104, PR #536
final class EducationLevelPickerTests: BaseUITest {
    // MARK: - Helper Properties

    private var registrationHelper: RegistrationHelper!

    /// All available education level display names
    private let educationLevels = [
        "High School",
        "Some College",
        "Associate's Degree",
        "Bachelor's Degree",
        "Master's Degree",
        "Doctorate",
        "Prefer not to say"
    ]

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()
        registrationHelper = RegistrationHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        registrationHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Helper Methods

    /// Navigate to registration screen and scroll to make education picker visible
    private func navigateToEducationPicker() -> Bool {
        guard registrationHelper.navigateToRegistration() else {
            return false
        }

        // Scroll down to reveal optional fields including education level
        let scrollView = app.scrollViews.firstMatch
        if scrollView.exists {
            scrollView.swipeUp()
        }

        return registrationHelper.educationLevelButton.waitForExistence(timeout: standardTimeout)
    }

    /// Navigate to the education picker, select the given level, and assert it displays correctly
    private func assertEducationLevelSelection(_ level: String) {
        let navigated = navigateToEducationPicker()
        XCTAssertTrue(navigated, "Should navigate to education picker")

        let success = registrationHelper.fillEducationLevel(level)
        XCTAssertTrue(success, "Should successfully select \(level) education level")

        let educationButton = registrationHelper.educationLevelButton
        XCTAssertTrue(
            educationButton.label.contains(level),
            "Education level should display '\(level)', got: \(educationButton.label)"
        )

        let screenshotName = level.replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "'", with: "")
        takeScreenshot(named: "EducationLevelPicker-\(screenshotName)")
    }

    // MARK: - Education Level Picker Existence Tests

    func testEducationLevelPickerExists() throws {
        throw XCTSkip("UI test - requires simulator/device")

        // Navigate to registration and scroll to education picker
        let navigated = navigateToEducationPicker()
        XCTAssertTrue(navigated, "Should navigate to education picker")

        // Verify the education level button exists
        let educationButton = registrationHelper.educationLevelButton
        assertExists(educationButton, "Education level picker should exist on registration screen")

        takeScreenshot(named: "EducationLevelPicker-Exists")
    }

    func testEducationLevelPickerDefaultState() throws {
        throw XCTSkip("UI test - requires simulator/device")

        // Navigate to registration and scroll to education picker
        let navigated = navigateToEducationPicker()
        XCTAssertTrue(navigated, "Should navigate to education picker")

        // Verify the default state shows "not selected"
        let educationButton = registrationHelper.educationLevelButton
        XCTAssertTrue(
            educationButton.label.contains("not selected"),
            "Education level should initially show 'not selected', got: \(educationButton.label)"
        )

        takeScreenshot(named: "EducationLevelPicker-DefaultState")
    }

    // MARK: - Education Level Selection Tests

    func testSelectHighSchoolEducationLevel() throws {
        throw XCTSkip("UI test - requires simulator/device")
        assertEducationLevelSelection("High School")
    }

    func testSelectBachelorsEducationLevel() throws {
        throw XCTSkip("UI test - requires simulator/device")
        assertEducationLevelSelection("Bachelor's Degree")
    }

    func testSelectDoctorateEducationLevel() throws {
        throw XCTSkip("UI test - requires simulator/device")
        assertEducationLevelSelection("Doctorate")
    }

    func testSelectPreferNotToSayEducationLevel() throws {
        throw XCTSkip("UI test - requires simulator/device")
        assertEducationLevelSelection("Prefer not to say")
    }

    // MARK: - Menu Opening and Interaction Tests

    func testEducationLevelMenuOpens() throws {
        throw XCTSkip("UI test - requires simulator/device")

        let navigated = navigateToEducationPicker()
        XCTAssertTrue(navigated, "Should navigate to education picker")

        // Tap the education level button to open the menu
        let educationButton = registrationHelper.educationLevelButton
        educationButton.tap()

        // Verify menu options are visible
        // Check that at least one education level option appears
        let bachelorOption = app.buttons["Bachelor's Degree"]
        let menuOpened = bachelorOption.waitForExistence(timeout: standardTimeout)
        XCTAssertTrue(menuOpened, "Education level menu should open and show options")

        takeScreenshot(named: "EducationLevelPicker-MenuOpen")
    }

    func testAllEducationLevelOptionsVisible() throws {
        throw XCTSkip("UI test - requires simulator/device")

        let navigated = navigateToEducationPicker()
        XCTAssertTrue(navigated, "Should navigate to education picker")

        // Open the menu
        let educationButton = registrationHelper.educationLevelButton
        educationButton.tap()

        // Wait for menu to appear
        _ = app.buttons["Bachelor's Degree"].waitForExistence(timeout: standardTimeout)

        // Verify all education levels are visible as menu options
        for level in educationLevels {
            let option = app.buttons[level]
            XCTAssertTrue(
                option.exists,
                "Education level option '\(level)' should be visible in menu"
            )
        }

        takeScreenshot(named: "EducationLevelPicker-AllOptions")
    }

    // MARK: - Selection Change Tests

    func testChangeEducationLevelSelection() throws {
        throw XCTSkip("UI test - requires simulator/device")

        let navigated = navigateToEducationPicker()
        XCTAssertTrue(navigated, "Should navigate to education picker")

        // First selection: Bachelor's Degree
        var success = registrationHelper.fillEducationLevel("Bachelor's Degree")
        XCTAssertTrue(success, "Should select Bachelor's Degree")

        let educationButton = registrationHelper.educationLevelButton
        XCTAssertTrue(
            educationButton.label.contains("Bachelor's Degree"),
            "Should show Bachelor's Degree"
        )

        // Change selection: Master's Degree
        success = registrationHelper.fillEducationLevel("Master's Degree")
        XCTAssertTrue(success, "Should change to Master's Degree")

        XCTAssertTrue(
            educationButton.label.contains("Master's Degree"),
            "Education level should now display 'Master's Degree', got: \(educationButton.label)"
        )

        takeScreenshot(named: "EducationLevelPicker-ChangedSelection")
    }

    // MARK: - Menu Dismissal Tests

    func testDismissMenuWithoutSelection() throws {
        throw XCTSkip("UI test - requires simulator/device")

        let navigated = navigateToEducationPicker()
        XCTAssertTrue(navigated, "Should navigate to education picker")

        let educationButton = registrationHelper.educationLevelButton

        // Open the menu
        educationButton.tap()

        // Wait for menu to appear
        let bachelorOption = app.buttons["Bachelor's Degree"]
        _ = bachelorOption.waitForExistence(timeout: standardTimeout)

        takeScreenshot(named: "EducationLevelPicker-MenuBeforeDismiss")

        // Tap outside the menu to dismiss (tap on the scroll view background)
        let scrollView = app.scrollViews.firstMatch
        scrollView.tap()

        // Wait for menu to disappear
        let menuDismissed = waitForDisappearance(of: bachelorOption, timeout: standardTimeout)
        XCTAssertTrue(menuDismissed, "Menu should dismiss when tapping outside")

        // Verify education level is still "not selected"
        XCTAssertTrue(
            educationButton.label.contains("not selected"),
            "Education level should remain 'not selected' after dismissing menu"
        )

        takeScreenshot(named: "EducationLevelPicker-DismissedNoSelection")
    }

    // MARK: - Registration Integration Tests

    func testRegistrationWithEducationLevel() throws {
        throw XCTSkip("UI test - requires backend connection and unique email")

        // Navigate to registration
        guard registrationHelper.navigateToRegistration() else {
            XCTFail("Failed to navigate to registration")
            return
        }

        // Fill required fields
        let timestamp = Date().timeIntervalSince1970
        let email = "test.edu.\(timestamp)@example.com"

        let formFilled = registrationHelper.fillRegistrationForm(
            firstName: "Test",
            lastName: "User",
            email: email,
            password: "testPassword123",
            confirmPassword: "testPassword123"
        )
        XCTAssertTrue(formFilled, "Should fill required form fields")

        // Scroll to and select education level
        let scrollView = app.scrollViews.firstMatch
        scrollView.swipeUp()

        let educationFilled = registrationHelper.fillEducationLevel("Bachelor's Degree")
        XCTAssertTrue(educationFilled, "Should select education level")

        // Verify education level is set before submission
        let educationButton = registrationHelper.educationLevelButton
        XCTAssertTrue(
            educationButton.label.contains("Bachelor's Degree"),
            "Education level should be set to Bachelor's Degree"
        )

        takeScreenshot(named: "RegistrationWithEducationLevel")
    }

    func testEducationLevelOptionalForRegistration() throws {
        throw XCTSkip("UI test - requires simulator/device")

        // Navigate to registration
        guard registrationHelper.navigateToRegistration() else {
            XCTFail("Failed to navigate to registration")
            return
        }

        // Fill only required fields (no education level)
        let formFilled = registrationHelper.fillRegistrationForm(
            firstName: "Test",
            lastName: "User",
            email: "test@example.com",
            password: "testPassword123",
            confirmPassword: "testPassword123"
        )
        XCTAssertTrue(formFilled, "Should fill required form fields")

        // Verify submit button is enabled without education level
        XCTAssertTrue(
            registrationHelper.isSubmitEnabled,
            "Submit button should be enabled without selecting education level"
        )

        takeScreenshot(named: "RegistrationWithoutEducationLevel")
    }
}
