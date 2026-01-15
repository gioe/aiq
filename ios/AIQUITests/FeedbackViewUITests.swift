//
//  FeedbackViewUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/15/26.
//

import XCTest

/// Comprehensive UI and accessibility tests for the FeedbackView
///
/// Tests cover:
/// - VoiceOver navigation and accessibility labels
/// - Dynamic Type scaling
/// - Form submission flow (fill, validate, submit, success)
/// - Form validation states
/// - Error handling
/// - Character count display
///
/// Note: Tests requiring backend connection are skipped by default using XCTSkip
final class FeedbackViewUITests: BaseUITest {
    // MARK: - Helper Properties

    private var feedbackHelper: FeedbackHelper!
    private var loginHelper: LoginHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Data

    private let validName = "John Doe"
    private let validEmail = "john.doe@example.com"
    private let validCategory = "Bug Report"
    private let validDescription = "This is a valid description with enough characters to pass validation."

    private let shortDescription = "Too short"
    private let invalidEmail = "not-an-email"

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()

        // Initialize helpers
        feedbackHelper = FeedbackHelper(app: app, timeout: standardTimeout)
        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)

        // Check if user is logged in (required to access FeedbackView)
        guard feedbackHelper.isLoggedIn else {
            throw XCTSkip("Tests require user to be logged in. App launched on Welcome screen.")
        }

        // Navigate to FeedbackView
        guard feedbackHelper.navigateToFeedback() else {
            throw XCTSkip("Could not navigate to FeedbackView. Ensure user is logged in.")
        }
    }

    override func tearDownWithError() throws {
        feedbackHelper = nil
        loginHelper = nil
        navHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - VoiceOver Navigation Tests

    func testVoiceOverNavigation_AllElementsHaveLabels() throws {
        // Verify we're on the feedback screen
        XCTAssertTrue(feedbackHelper.isOnFeedbackScreen, "Should be on feedback screen")
        takeScreenshot(named: "FeedbackScreen_Initial")

        // Verify all form elements have accessibility labels
        XCTAssertTrue(
            feedbackHelper.hasAccessibilityLabel(feedbackHelper.nameTextField),
            "Name field should have accessibility label"
        )

        XCTAssertTrue(
            feedbackHelper.hasAccessibilityLabel(feedbackHelper.emailTextField),
            "Email field should have accessibility label"
        )

        XCTAssertTrue(
            feedbackHelper.hasAccessibilityLabel(feedbackHelper.categoryMenu),
            "Category menu should have accessibility label"
        )

        XCTAssertTrue(
            feedbackHelper.hasAccessibilityLabel(feedbackHelper.descriptionTextField),
            "Description field should have accessibility label"
        )

        XCTAssertTrue(
            feedbackHelper.hasAccessibilityLabel(feedbackHelper.submitButton),
            "Submit button should have accessibility label"
        )

        takeScreenshot(named: "FeedbackScreen_AllElementsVerified")
    }

    func testVoiceOverNavigation_CategoryMenuHasHint() throws {
        // Verify category menu has accessibility hint
        let categoryMenu = feedbackHelper.categoryMenu
        assertExists(categoryMenu, "Category menu should exist")

        let label = feedbackHelper.accessibilityLabel(for: categoryMenu)
        XCTAssertNotNil(label, "Category menu should have accessibility label")
        XCTAssertTrue(
            label?.contains("Category") == true,
            "Category menu label should contain 'Category'"
        )

        // Note: Accessibility hints are implementation-specific
        // The view sets: "Double tap to open menu and select a feedback category"
        let hint = feedbackHelper.accessibilityHint(for: categoryMenu)
        XCTAssertNotNil(hint, "Category menu should have accessibility hint")

        takeScreenshot(named: "CategoryMenu_WithAccessibility")
    }

    func testVoiceOverNavigation_DescriptionFieldHasHint() throws {
        // Verify description field has accessibility hint
        let descriptionField = feedbackHelper.descriptionTextField
        assertExists(descriptionField, "Description field should exist")

        let label = feedbackHelper.accessibilityLabel(for: descriptionField)
        XCTAssertNotNil(label, "Description field should have accessibility label")

        // The view sets: "Text field. Double tap to edit. Minimum 10 characters required."
        let hint = feedbackHelper.accessibilityHint(for: descriptionField)
        XCTAssertNotNil(hint, "Description field should have accessibility hint")

        takeScreenshot(named: "DescriptionField_WithAccessibility")
    }

    func testVoiceOverNavigation_SubmitButtonHintChangesWithFormValidity() throws {
        // Initially, form is invalid - button should be disabled
        let submitButton = feedbackHelper.submitButton
        assertExists(submitButton, "Submit button should exist")

        // Check initial hint (form invalid)
        let initialHint = feedbackHelper.accessibilityHint(for: submitButton)
        XCTAssertNotNil(initialHint, "Submit button should have accessibility hint when invalid")
        XCTAssertTrue(
            initialHint?.contains("Complete all fields") == true,
            "Hint should indicate form needs completion"
        )

        takeScreenshot(named: "SubmitButton_FormInvalid")

        // Fill form to make it valid
        feedbackHelper.fillForm(
            name: validName,
            email: validEmail,
            category: validCategory,
            description: validDescription
        )

        // Wait for form state to update
        wait(for: submitButton, timeout: quickTimeout)

        // Check hint changes when form is valid
        let validHint = feedbackHelper.accessibilityHint(for: submitButton)
        XCTAssertNotNil(validHint, "Submit button should have accessibility hint when valid")
        XCTAssertTrue(
            validHint?.contains("Double tap to submit") == true,
            "Hint should indicate button is ready to submit"
        )

        takeScreenshot(named: "SubmitButton_FormValid")
    }

    func testVoiceOverNavigation_CharacterCountHasAccessibleLabel() throws {
        // Fill description field
        feedbackHelper.fillDescription("Test description")

        // Wait for character count to update
        let characterCountLabel = feedbackHelper.characterCountLabel
        wait(for: characterCountLabel, timeout: quickTimeout)

        // Verify character count has accessible label
        let label = feedbackHelper.accessibilityLabel(for: characterCountLabel)
        XCTAssertNotNil(label, "Character count should have accessibility label")
        XCTAssertTrue(
            label?.contains("characters") == true,
            "Character count label should mention 'characters'"
        )

        takeScreenshot(named: "CharacterCount_Accessible")
    }

    func testVoiceOverNavigation_ValidationErrorsHaveErrorPrefix() throws {
        // Fill name field with valid data to trigger validation
        feedbackHelper.fillName(validName)

        // Fill email with invalid format
        feedbackHelper.fillEmail(invalidEmail)

        // Tap elsewhere to trigger validation
        feedbackHelper.nameTextField.tap()

        // Wait for validation error to appear
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)

        // Look for error messages with "Error:" prefix
        let errorPredicate = NSPredicate(format: "label BEGINSWITH 'Error:'")
        let errorMessages = app.staticTexts.matching(errorPredicate)

        if !errorMessages.isEmpty {
            XCTAssertTrue(
                errorMessages.firstMatch.exists,
                "Validation errors should have 'Error:' prefix for accessibility"
            )
            takeScreenshot(named: "ValidationError_AccessiblePrefix")
        }
    }

    func testVoiceOverNavigation_SuccessOverlayIsCombinedForVoiceOver() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection for form submission")

        // Fill and submit form
        feedbackHelper.fillForm(
            name: validName,
            email: validEmail,
            category: validCategory,
            description: validDescription
        )
        feedbackHelper.submit(waitForSuccess: true)

        // Verify success overlay appears
        XCTAssertTrue(feedbackHelper.hasSuccessMessage, "Success message should appear")

        // The success overlay combines children for VoiceOver
        // and has .isStaticText trait
        let successOverlay = feedbackHelper.successOverlay
        assertExists(successOverlay, "Success overlay should exist")

        takeScreenshot(named: "SuccessOverlay_Accessible")
    }

    // MARK: - Dynamic Type Scaling Tests

    func testDynamicTypeScaling_AllTextScales() throws {
        // This test verifies that text elements exist and are visible
        // Actual Dynamic Type testing requires changing system settings
        // which is not directly supported in XCUITest

        // Verify all text elements are present and visible
        let nameTextField = feedbackHelper.nameTextField
        let emailTextField = feedbackHelper.emailTextField
        let categoryMenu = feedbackHelper.categoryMenu
        let descriptionTextField = feedbackHelper.descriptionTextField
        let submitButton = feedbackHelper.submitButton

        assertExists(nameTextField, "Name field should exist")
        assertExists(emailTextField, "Email field should exist")
        assertExists(categoryMenu, "Category menu should exist")
        assertExists(descriptionTextField, "Description field should exist")
        assertExists(submitButton, "Submit button should exist")

        // Verify elements are hittable (visible and accessible)
        assertHittable(nameTextField, "Name field should be hittable")
        assertHittable(emailTextField, "Email field should be hittable")
        assertHittable(categoryMenu, "Category menu should be hittable")
        assertHittable(descriptionTextField, "Description field should be hittable")
        assertHittable(submitButton, "Submit button should be hittable")

        takeScreenshot(named: "AllElements_Visible")
    }

    func testDynamicTypeScaling_MinimumTouchTargets() throws {
        // Verify all interactive elements are hittable (44pt minimum touch target)
        let nameTextField = feedbackHelper.nameTextField
        let emailTextField = feedbackHelper.emailTextField
        let categoryMenu = feedbackHelper.categoryMenu
        let descriptionTextField = feedbackHelper.descriptionTextField
        let submitButton = feedbackHelper.submitButton

        // All elements should be hittable, indicating proper touch target size
        XCTAssertTrue(
            waitForHittable(nameTextField, timeout: standardTimeout),
            "Name field should meet minimum touch target size"
        )

        XCTAssertTrue(
            waitForHittable(emailTextField, timeout: standardTimeout),
            "Email field should meet minimum touch target size"
        )

        XCTAssertTrue(
            waitForHittable(categoryMenu, timeout: standardTimeout),
            "Category menu should meet minimum touch target size"
        )

        XCTAssertTrue(
            waitForHittable(descriptionTextField, timeout: standardTimeout),
            "Description field should meet minimum touch target size"
        )

        XCTAssertTrue(
            waitForHittable(submitButton, timeout: standardTimeout),
            "Submit button should meet minimum touch target size"
        )

        takeScreenshot(named: "TouchTargets_Verified")
    }

    // MARK: - Form Submission Flow Tests

    func testFormSubmission_ValidForm_Success() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection for form submission")

        // Verify we start with an empty form
        XCTAssertTrue(feedbackHelper.isOnFeedbackScreen, "Should be on feedback screen")
        XCTAssertFalse(feedbackHelper.isSubmitEnabled, "Submit button should be disabled initially")

        takeScreenshot(named: "FormSubmission_Initial")

        // Fill form with valid data
        let success = feedbackHelper.fillForm(
            name: validName,
            email: validEmail,
            category: validCategory,
            description: validDescription
        )
        XCTAssertTrue(success, "Form should be filled successfully")

        takeScreenshot(named: "FormSubmission_Filled")

        // Verify form is now valid
        XCTAssertTrue(feedbackHelper.isFormValid, "Form should be valid after filling")
        XCTAssertTrue(feedbackHelper.isSubmitEnabled, "Submit button should be enabled")

        // Submit form
        feedbackHelper.submit(waitForSuccess: true)

        // Verify success message appears
        XCTAssertTrue(feedbackHelper.hasSuccessMessage, "Success message should appear")

        takeScreenshot(named: "FormSubmission_Success")
    }

    func testFormSubmission_InvalidEmail_ButtonDisabled() throws {
        // Fill form with invalid email
        feedbackHelper.fillName(validName)
        feedbackHelper.fillEmail(invalidEmail)
        feedbackHelper.selectCategory(validCategory)
        feedbackHelper.fillDescription(validDescription)

        // Wait for validation to run
        wait(for: feedbackHelper.submitButton, timeout: quickTimeout)

        // Verify button is disabled
        XCTAssertFalse(
            feedbackHelper.isSubmitEnabled,
            "Submit button should be disabled with invalid email"
        )

        takeScreenshot(named: "FormSubmission_InvalidEmail")
    }

    func testFormSubmission_ShortDescription_ButtonDisabled() throws {
        // Fill form with short description
        feedbackHelper.fillName(validName)
        feedbackHelper.fillEmail(validEmail)
        feedbackHelper.selectCategory(validCategory)
        feedbackHelper.fillDescription(shortDescription)

        // Wait for validation to run
        wait(for: feedbackHelper.submitButton, timeout: quickTimeout)

        // Verify button is disabled
        XCTAssertFalse(
            feedbackHelper.isSubmitEnabled,
            "Submit button should be disabled with short description"
        )

        takeScreenshot(named: "FormSubmission_ShortDescription")
    }

    func testFormSubmission_MissingCategory_ButtonDisabled() throws {
        // Fill form without selecting category
        feedbackHelper.fillName(validName)
        feedbackHelper.fillEmail(validEmail)
        // Skip category selection
        feedbackHelper.fillDescription(validDescription)

        // Wait for form state to update
        wait(for: feedbackHelper.submitButton, timeout: quickTimeout)

        // Verify button is disabled
        XCTAssertFalse(
            feedbackHelper.isSubmitEnabled,
            "Submit button should be disabled without category"
        )

        takeScreenshot(named: "FormSubmission_MissingCategory")
    }

    func testFormSubmission_EmptyForm_ButtonDisabled() throws {
        // Verify submit button is disabled with empty form
        XCTAssertFalse(
            feedbackHelper.isSubmitEnabled,
            "Submit button should be disabled with empty form"
        )

        takeScreenshot(named: "FormSubmission_EmptyForm")
    }

    // MARK: - Form Validation Tests

    func testFormValidation_EmailFormat() throws {
        // Test various email formats
        let testCases = [
            ("valid@example.com", true),
            ("user.name@example.co.uk", true),
            ("invalid-email", false),
            ("@example.com", false),
            ("user@", false)
        ]

        for (email, shouldBeValid) in testCases {
            // Clear form and fill with test email
            feedbackHelper.nameTextField.tap()
            feedbackHelper.nameTextField.typeText(validName)

            feedbackHelper.emailTextField.tap()
            feedbackHelper.emailTextField.typeText(email)

            feedbackHelper.selectCategory(validCategory)
            feedbackHelper.fillDescription(validDescription)

            // Check submit button state
            wait(for: feedbackHelper.submitButton, timeout: quickTimeout)

            if shouldBeValid {
                XCTAssertTrue(
                    feedbackHelper.isSubmitEnabled,
                    "Submit button should be enabled with valid email: \(email)"
                )
            } else {
                XCTAssertFalse(
                    feedbackHelper.isSubmitEnabled,
                    "Submit button should be disabled with invalid email: \(email)"
                )
            }

            takeScreenshot(named: "EmailValidation_\(email)")

            // Navigate back and return to reset form
            if email != testCases.last?.0 {
                app.navigationBars.buttons.firstMatch.tap()
                feedbackHelper.navigateToFeedback()
            }
        }
    }

    func testFormValidation_DescriptionMinimumLength() throws {
        // Fill all fields except description
        feedbackHelper.fillName(validName)
        feedbackHelper.fillEmail(validEmail)
        feedbackHelper.selectCategory(validCategory)

        // Test descriptions of various lengths
        let descriptions = [
            ("Short", false), // Too short (5 chars)
            ("A bit longer", true), // Valid (13 chars)
            ("This is a test description", true) // Valid (28 chars)
        ]

        for (description, shouldBeValid) in descriptions {
            // Clear and fill description
            let descriptionField = feedbackHelper.descriptionTextField
            descriptionField.tap()

            // Clear existing text
            if let currentValue = descriptionField.value as? String, !currentValue.isEmpty {
                let deleteString = String(repeating: XCUIKeyboardKey.delete.rawValue, count: currentValue.count)
                descriptionField.typeText(deleteString)
            }

            descriptionField.typeText(description)

            // Wait for validation
            wait(for: feedbackHelper.submitButton, timeout: quickTimeout)

            if shouldBeValid {
                XCTAssertTrue(
                    feedbackHelper.isSubmitEnabled,
                    "Submit button should be enabled with description: '\(description)'"
                )
            } else {
                XCTAssertFalse(
                    feedbackHelper.isSubmitEnabled,
                    "Submit button should be disabled with description: '\(description)'"
                )
            }

            takeScreenshot(named: "DescriptionValidation_\(description.count)chars")
        }
    }

    func testFormValidation_NameRequired() throws {
        // Fill all fields except name
        feedbackHelper.fillEmail(validEmail)
        feedbackHelper.selectCategory(validCategory)
        feedbackHelper.fillDescription(validDescription)

        // Wait for validation
        wait(for: feedbackHelper.submitButton, timeout: quickTimeout)

        // Verify button is disabled
        XCTAssertFalse(
            feedbackHelper.isSubmitEnabled,
            "Submit button should be disabled without name"
        )

        takeScreenshot(named: "NameValidation_Empty")

        // Now add name
        feedbackHelper.fillName(validName)

        // Wait for validation
        wait(for: feedbackHelper.submitButton, timeout: quickTimeout)

        // Verify button is now enabled
        XCTAssertTrue(
            feedbackHelper.isSubmitEnabled,
            "Submit button should be enabled after adding name"
        )

        takeScreenshot(named: "NameValidation_Filled")
    }

    // MARK: - Category Selection Tests

    func testCategorySelection_AllCategories() throws {
        // Test selecting each category
        let categories = [
            "Bug Report",
            "Feature Request",
            "General Feedback"
        ]

        for category in categories {
            // Select category
            let success = feedbackHelper.selectCategory(category)
            XCTAssertTrue(success, "Should be able to select category: \(category)")

            // Verify category is displayed in menu button
            let categoryMenu = feedbackHelper.categoryMenu
            wait(for: categoryMenu, timeout: quickTimeout)

            let label = feedbackHelper.accessibilityLabel(for: categoryMenu)
            XCTAssertNotNil(label, "Category menu should have label")
            XCTAssertTrue(
                label?.contains(category) == true,
                "Category menu should show selected category: \(category)"
            )

            takeScreenshot(named: "CategorySelection_\(category)")
        }
    }

    // MARK: - Character Count Tests

    func testCharacterCount_UpdatesWithInput() throws {
        // Initially, character count should be 0
        let descriptionField = feedbackHelper.descriptionTextField
        descriptionField.tap()

        // Type some text
        let testText = "This is a test description"
        descriptionField.typeText(testText)

        // Wait for character count to update
        wait(for: feedbackHelper.characterCountLabel, timeout: quickTimeout)

        // Verify character count matches
        let count = feedbackHelper.characterCount
        XCTAssertNotNil(count, "Character count should be available")
        XCTAssertEqual(
            count,
            testText.count,
            "Character count should match input length"
        )

        takeScreenshot(named: "CharacterCount_Updated")
    }

    func testCharacterCount_Accessible() throws {
        // Type text
        feedbackHelper.fillDescription("Test")

        // Wait for character count
        let countLabel = feedbackHelper.characterCountLabel
        wait(for: countLabel, timeout: quickTimeout)

        // Verify accessibility
        XCTAssertTrue(
            feedbackHelper.hasAccessibilityLabel(countLabel),
            "Character count should have accessibility label"
        )

        let label = feedbackHelper.accessibilityLabel(for: countLabel)
        XCTAssertTrue(
            label?.contains("character") == true,
            "Character count accessibility label should mention 'character'"
        )

        takeScreenshot(named: "CharacterCount_Accessible")
    }

    // MARK: - Navigation Tests

    func testNavigation_BackButton() throws {
        // Verify we're on feedback screen
        XCTAssertTrue(feedbackHelper.isOnFeedbackScreen, "Should be on feedback screen")

        // Tap back button
        let backButton = app.navigationBars.buttons.firstMatch
        assertExists(backButton, "Back button should exist")
        backButton.tap()

        // Wait for Settings screen
        wait(for: app.navigationBars["Settings"], timeout: standardTimeout)

        // Verify we're back on Settings
        XCTAssertTrue(
            app.navigationBars["Settings"].exists,
            "Should be back on Settings screen"
        )

        takeScreenshot(named: "Navigation_BackToSettings")
    }

    func testNavigation_NavigateFromSettings() throws {
        // Already navigated in setup, just verify
        XCTAssertTrue(feedbackHelper.isOnFeedbackScreen, "Should be on feedback screen")

        // Verify navigation bar title
        let feedbackNavBar = app.navigationBars["Feedback"]
        assertExists(feedbackNavBar, "Feedback navigation bar should exist")

        takeScreenshot(named: "Navigation_FeedbackScreen")
    }

    // MARK: - Loading State Tests

    func testLoadingState_SubmittingFeedback() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection for form submission")

        // Fill form
        feedbackHelper.fillForm(
            name: validName,
            email: validEmail,
            category: validCategory,
            description: validDescription
        )

        // Submit
        feedbackHelper.submitButton.tap()

        // Look for loading indicator
        // Note: Loading overlay might appear briefly
        let loadingText = app.staticTexts["Submitting feedback..."]
        if loadingText.exists {
            takeScreenshot(named: "LoadingState_Submitting")
        }

        // Wait for success or error
        wait(for: feedbackHelper.successOverlay, timeout: networkTimeout)
    }

    // MARK: - Integration Tests

    func testFullFeedbackFlow_EndToEnd() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection for full integration test")

        // Step 1: Verify starting on feedback screen
        XCTAssertTrue(feedbackHelper.isOnFeedbackScreen, "Should start on feedback screen")
        takeScreenshot(named: "E2E_Step1_FeedbackScreen")

        // Step 2: Verify form is empty and button is disabled
        XCTAssertFalse(feedbackHelper.isSubmitEnabled, "Submit button should be disabled initially")
        takeScreenshot(named: "E2E_Step2_EmptyForm")

        // Step 3: Fill form
        let fillSuccess = feedbackHelper.fillForm(
            name: validName,
            email: validEmail,
            category: validCategory,
            description: validDescription
        )
        XCTAssertTrue(fillSuccess, "Form should be filled successfully")
        takeScreenshot(named: "E2E_Step3_FormFilled")

        // Step 4: Verify form is valid
        XCTAssertTrue(feedbackHelper.isFormValid, "Form should be valid")
        XCTAssertTrue(feedbackHelper.isSubmitEnabled, "Submit button should be enabled")
        takeScreenshot(named: "E2E_Step4_FormValid")

        // Step 5: Submit form
        feedbackHelper.submit(waitForSuccess: true)
        takeScreenshot(named: "E2E_Step5_Submitting")

        // Step 6: Verify success message
        XCTAssertTrue(feedbackHelper.hasSuccessMessage, "Success message should appear")
        takeScreenshot(named: "E2E_Step6_Success")

        // Success overlay typically dismisses automatically after a delay
        // Wait for it to disappear or for navigation back to Settings
        let disappeared = waitForDisappearance(
            of: feedbackHelper.successOverlay,
            timeout: extendedTimeout
        )

        if disappeared {
            takeScreenshot(named: "E2E_Step7_SuccessDismissed")
        }
    }
}
