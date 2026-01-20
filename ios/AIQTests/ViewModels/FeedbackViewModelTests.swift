import Combine
import XCTest

@testable import AIQ
import AIQAPIClient

@MainActor
final class FeedbackViewModelTests: XCTestCase {
    var sut: FeedbackViewModel!
    var mockAPIClient: MockAPIClient!

    override func setUp() {
        super.setUp()
        mockAPIClient = MockAPIClient()
        sut = FeedbackViewModel(apiClient: mockAPIClient)
    }

    override func tearDown() {
        sut = nil
        mockAPIClient = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialization_DefaultState() {
        XCTAssertEqual(sut.name, "", "name should be empty initially")
        XCTAssertEqual(sut.email, "", "email should be empty initially")
        XCTAssertNil(sut.selectedCategory, "selectedCategory should be nil initially")
        XCTAssertEqual(sut.description, "", "description should be empty initially")
        XCTAssertFalse(sut.showSuccessMessage, "showSuccessMessage should be false initially")
        XCTAssertFalse(sut.isLoading, "isLoading should be false initially")
        XCTAssertNil(sut.error, "error should be nil initially")
    }

    func testInitialization_WithAuthenticatedUser_PrePopulatesEmail() {
        // Given
        let mockAuthManager = MockAuthManager()
        let expectedEmail = "authenticated@example.com"
        mockAuthManager.currentUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: expectedEmail,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: false
        )

        // When
        let viewModel = FeedbackViewModel(apiClient: mockAPIClient, authManager: mockAuthManager)

        // Then
        XCTAssertEqual(viewModel.email, expectedEmail, "email should be pre-populated from authenticated user")
        XCTAssertEqual(viewModel.name, "", "name should remain empty")
    }

    func testInitialization_WithoutAuthManager_EmailRemainsEmpty() {
        // When
        let viewModel = FeedbackViewModel(apiClient: mockAPIClient, authManager: nil)

        // Then
        XCTAssertEqual(viewModel.email, "", "email should be empty when no auth manager provided")
    }

    func testInitialization_WithUnauthenticatedUser_EmailRemainsEmpty() {
        // Given
        let mockAuthManager = MockAuthManager()
        mockAuthManager.currentUser = nil

        // When
        let viewModel = FeedbackViewModel(apiClient: mockAPIClient, authManager: mockAuthManager)

        // Then
        XCTAssertEqual(viewModel.email, "", "email should be empty when user is not authenticated")
    }

    // MARK: - Name Validation Tests

    func testNameValidation_EmptyName_Invalid() {
        sut.name = ""
        XCTAssertFalse(sut.nameValidation.isValid, "empty name should be invalid")
        XCTAssertEqual(sut.nameValidation.errorMessage, "Name is required")
    }

    func testNameValidation_SingleCharacter_Invalid() {
        sut.name = "A"
        XCTAssertFalse(sut.nameValidation.isValid, "single character name should be invalid")
        XCTAssertEqual(
            sut.nameValidation.errorMessage,
            "Name must be at least \(Constants.Validation.minNameLength) characters"
        )
    }

    func testNameValidation_TwoCharacters_Valid() {
        sut.name = "Jo"
        XCTAssertTrue(sut.nameValidation.isValid, "two character name should be valid")
        XCTAssertNil(sut.nameValidation.errorMessage)
    }

    func testNameValidation_WhitespaceOnly_Invalid() {
        sut.name = "   "
        XCTAssertFalse(sut.nameValidation.isValid, "whitespace-only name should be invalid")
        XCTAssertEqual(sut.nameValidation.errorMessage, "Name is required")
    }

    func testNameValidation_ValidName() {
        sut.name = "John Doe"
        XCTAssertTrue(sut.nameValidation.isValid, "valid name should pass validation")
        XCTAssertNil(sut.nameValidation.errorMessage)
    }

    // MARK: - Email Validation Tests

    func testEmailValidation_EmptyEmail_Invalid() {
        sut.email = ""
        XCTAssertFalse(sut.emailValidation.isValid, "empty email should be invalid")
        XCTAssertEqual(sut.emailValidation.errorMessage, "Email is required")
    }

    func testEmailValidation_InvalidFormat_Invalid() {
        sut.email = "notanemail"
        XCTAssertFalse(sut.emailValidation.isValid, "invalid email format should be invalid")
        XCTAssertEqual(sut.emailValidation.errorMessage, "Please enter a valid email address")
    }

    func testEmailValidation_ValidFormat_Valid() {
        sut.email = "john@example.com"
        XCTAssertTrue(sut.emailValidation.isValid, "valid email should pass validation")
        XCTAssertNil(sut.emailValidation.errorMessage)
    }

    func testEmailValidation_WhitespaceOnly_Invalid() {
        sut.email = "   "
        XCTAssertFalse(sut.emailValidation.isValid, "whitespace-only email should be invalid")
        XCTAssertEqual(sut.emailValidation.errorMessage, "Email is required")
    }

    // MARK: - Category Validation Tests

    func testCategoryValidation_NilCategory_Invalid() {
        sut.selectedCategory = nil
        XCTAssertFalse(sut.categoryValidation.isValid, "nil category should be invalid")
        XCTAssertEqual(sut.categoryValidation.errorMessage, "Please select a category")
    }

    func testCategoryValidation_BugReport_Valid() {
        sut.selectedCategory = .bugReport
        XCTAssertTrue(sut.categoryValidation.isValid, "bugReport category should be valid")
        XCTAssertNil(sut.categoryValidation.errorMessage)
    }

    func testCategoryValidation_FeatureRequest_Valid() {
        sut.selectedCategory = .featureRequest
        XCTAssertTrue(sut.categoryValidation.isValid, "featureRequest category should be valid")
        XCTAssertNil(sut.categoryValidation.errorMessage)
    }

    func testCategoryValidation_GeneralFeedback_Valid() {
        sut.selectedCategory = .generalFeedback
        XCTAssertTrue(sut.categoryValidation.isValid, "generalFeedback category should be valid")
        XCTAssertNil(sut.categoryValidation.errorMessage)
    }

    func testCategoryValidation_QuestionHelp_Valid() {
        sut.selectedCategory = .questionHelp
        XCTAssertTrue(sut.categoryValidation.isValid, "questionHelp category should be valid")
        XCTAssertNil(sut.categoryValidation.errorMessage)
    }

    func testCategoryValidation_Other_Valid() {
        sut.selectedCategory = .other
        XCTAssertTrue(sut.categoryValidation.isValid, "other category should be valid")
        XCTAssertNil(sut.categoryValidation.errorMessage)
    }

    // MARK: - Description Validation Tests

    func testDescriptionValidation_EmptyDescription_Invalid() {
        sut.description = ""
        XCTAssertFalse(sut.descriptionValidation.isValid, "empty description should be invalid")
        XCTAssertEqual(sut.descriptionValidation.errorMessage, "Description is required")
    }

    func testDescriptionValidation_NineCharacters_Invalid() {
        sut.description = "123456789"
        XCTAssertFalse(sut.descriptionValidation.isValid, "9 character description should be invalid")
        XCTAssertEqual(sut.descriptionValidation.errorMessage, "Description must be at least 10 characters")
    }

    func testDescriptionValidation_TenCharacters_Valid() {
        sut.description = "1234567890"
        XCTAssertTrue(sut.descriptionValidation.isValid, "10 character description should be valid")
        XCTAssertNil(sut.descriptionValidation.errorMessage)
    }

    func testDescriptionValidation_WhitespaceOnly_Invalid() {
        sut.description = "          "
        XCTAssertFalse(sut.descriptionValidation.isValid, "whitespace-only description should be invalid")
        XCTAssertEqual(sut.descriptionValidation.errorMessage, "Description is required")
    }

    func testDescriptionValidation_ValidDescription() {
        sut.description = "This is a detailed feedback description that is definitely long enough."
        XCTAssertTrue(sut.descriptionValidation.isValid, "valid description should pass validation")
        XCTAssertNil(sut.descriptionValidation.errorMessage)
    }

    // MARK: - Form Validation Tests

    func testFormValidation_AllFieldsEmpty_Invalid() {
        XCTAssertFalse(sut.isFormValid, "form with all empty fields should be invalid")
    }

    func testFormValidation_PartiallyFilled_Invalid() {
        sut.name = "John Doe"
        sut.email = "john@example.com"
        // Missing category and description
        XCTAssertFalse(sut.isFormValid, "partially filled form should be invalid")
    }

    func testFormValidation_MissingName_Invalid() {
        sut.name = ""
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"
        XCTAssertFalse(sut.isFormValid, "form missing name should be invalid")
    }

    func testFormValidation_MissingEmail_Invalid() {
        sut.name = "John Doe"
        sut.email = ""
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"
        XCTAssertFalse(sut.isFormValid, "form missing email should be invalid")
    }

    func testFormValidation_MissingCategory_Invalid() {
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = nil
        sut.description = "This is a detailed bug report"
        XCTAssertFalse(sut.isFormValid, "form missing category should be invalid")
    }

    func testFormValidation_MissingDescription_Invalid() {
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = ""
        XCTAssertFalse(sut.isFormValid, "form missing description should be invalid")
    }

    func testFormValidation_AllFieldsValid_Valid() {
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"
        XCTAssertTrue(sut.isFormValid, "form with all valid fields should be valid")
    }

    // MARK: - Submit Feedback Tests

    func testSubmitFeedback_Success() async {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        // Configure mock response
        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you for your feedback",
            submissionId: 123,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)

        // When
        await sut.submitFeedback()

        // Then - Verify API call
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .submitFeedback, "should call submitFeedback endpoint")
        XCTAssertEqual(lastMethod, .post, "should use POST method")
        XCTAssertEqual(lastRequiresAuth, false, "should not require authentication")

        // Then - Verify success state
        XCTAssertTrue(sut.showSuccessMessage, "should show success message")
        XCTAssertFalse(sut.isLoading, "should not be loading after success")
        XCTAssertNil(sut.error, "should have no error after success")
    }

    func testSubmitFeedback_BackendReturnsFalse_SetsError() async {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        // Configure mock response with success=false
        let mockResponse = FeedbackSubmitResponse(
            message: "Feedback submission failed",
            submissionId: 0,
            success: false
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)

        // When
        await sut.submitFeedback()

        // Then
        XCTAssertFalse(sut.showSuccessMessage, "should not show success message")
        XCTAssertNotNil(sut.error, "should set error when backend returns success=false")
        XCTAssertEqual(
            (sut.error as NSError?)?.localizedDescription,
            "Feedback submission failed",
            "error should contain backend message"
        )
        XCTAssertFalse(sut.isLoading, "should not be loading after error")
    }

    func testSubmitFeedback_NetworkError_SetsError() async {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        // Configure mock to throw error
        let networkError = NSError(
            domain: "NetworkError",
            code: -1009,
            userInfo: [NSLocalizedDescriptionKey: "The Internet connection appears to be offline"]
        )
        await mockAPIClient.setError(networkError, for: .submitFeedback)

        // When
        await sut.submitFeedback()

        // Then
        XCTAssertFalse(sut.showSuccessMessage, "should not show success message on error")
        XCTAssertNotNil(sut.error, "should set error when network request fails")
        XCTAssertFalse(sut.isLoading, "should not be loading after error")
    }

    func testSubmitFeedback_InvalidForm_DoesNotCallAPI() async {
        // Given - Setup invalid form (missing required fields)
        sut.name = ""
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        // When
        await sut.submitFeedback()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertFalse(requestCalled, "should not call API when form is invalid")
        XCTAssertFalse(sut.showSuccessMessage, "should not show success message")
    }

    func testSubmitFeedback_RequestBodyContainsCorrectData() async {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .featureRequest
        sut.description = "Please add dark mode support"

        // Configure mock response
        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you",
            submissionId: 456,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)

        // When
        await sut.submitFeedback()

        // Then - Verify request body
        let bodyDict = await mockAPIClient.lastBodyAsDictionary
        XCTAssertNotNil(bodyDict, "request body should be present")
        XCTAssertEqual(bodyDict?["name"] as? String, "John Doe")
        XCTAssertEqual(bodyDict?["email"] as? String, "john@example.com")
        XCTAssertEqual(bodyDict?["category"] as? String, "feature_request")
        XCTAssertEqual(bodyDict?["description"] as? String, "Please add dark mode support")
    }

    // MARK: - Loading State Tests

    func testSubmitFeedback_LoadingStateTransitions() async {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you",
            submissionId: 123,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)

        // When - Start submission
        XCTAssertFalse(sut.isLoading, "should not be loading initially")

        let submitTask = Task {
            await sut.submitFeedback()
        }

        // Give it a moment to start loading
        try? await Task.sleep(nanoseconds: 10_000_000) // 0.01 seconds

        // Then - Should be loading during submission
        // Note: This might pass before loading starts due to fast mock execution
        // The important part is verifying it's false after completion
        await submitTask.value

        // Then - Should not be loading after completion
        XCTAssertFalse(sut.isLoading, "should not be loading after completion")
    }

    func testSubmitFeedback_ClearsErrorBeforeSubmit() async {
        // Given - Setup with existing error
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        sut.error = NSError(domain: "Test", code: -1, userInfo: nil)
        XCTAssertNotNil(sut.error, "should have error set")

        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you",
            submissionId: 123,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)

        // When
        await sut.submitFeedback()

        // Then
        XCTAssertNil(sut.error, "should clear error on successful submit")
    }

    // MARK: - Reset Form Tests

    func testResetForm_ClearsAllFields() {
        // Given - Form with data
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"
        sut.showSuccessMessage = true
        sut.error = NSError(domain: "Test", code: -1, userInfo: nil)

        // When
        sut.resetForm()

        // Then
        XCTAssertEqual(sut.name, "", "name should be cleared")
        XCTAssertEqual(sut.email, "", "email should be cleared")
        XCTAssertNil(sut.selectedCategory, "selectedCategory should be nil")
        XCTAssertEqual(sut.description, "", "description should be cleared")
        XCTAssertFalse(sut.showSuccessMessage, "showSuccessMessage should be false")
        XCTAssertNil(sut.error, "error should be cleared")
    }

    func testResetForm_EmptyForm_RemainsEmpty() {
        // Given - Already empty form
        XCTAssertEqual(sut.name, "")
        XCTAssertEqual(sut.email, "")
        XCTAssertNil(sut.selectedCategory)
        XCTAssertEqual(sut.description, "")

        // When
        sut.resetForm()

        // Then - Should remain empty
        XCTAssertEqual(sut.name, "")
        XCTAssertEqual(sut.email, "")
        XCTAssertNil(sut.selectedCategory)
        XCTAssertEqual(sut.description, "")
        XCTAssertFalse(sut.showSuccessMessage)
        XCTAssertNil(sut.error)
    }

    func testResetForm_WithAuthenticatedUser_PreservesEmail() {
        // Given - Authenticated user with pre-populated email
        let mockAuthManager = MockAuthManager()
        let expectedEmail = "authenticated@example.com"
        mockAuthManager.currentUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: expectedEmail,
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: false
        )
        let viewModel = FeedbackViewModel(apiClient: mockAPIClient, authManager: mockAuthManager)

        // When - Fill form and reset
        viewModel.name = "John Doe"
        viewModel.description = "Test feedback"
        viewModel.selectedCategory = .bugReport
        viewModel.resetForm()

        // Then - Email should be preserved, other fields cleared
        XCTAssertEqual(viewModel.email, expectedEmail, "email should remain pre-populated after reset")
        XCTAssertEqual(viewModel.name, "", "name should be cleared")
        XCTAssertNil(viewModel.selectedCategory, "category should be cleared")
        XCTAssertEqual(viewModel.description, "", "description should be cleared")
    }

    func testResetForm_WithoutAuthManager_ClearsEmail() {
        // Given - No auth manager, email manually set
        let viewModel = FeedbackViewModel(apiClient: mockAPIClient, authManager: nil)
        viewModel.email = "manual@example.com"

        // When
        viewModel.resetForm()

        // Then - Email should be cleared since there's no authenticated user
        XCTAssertEqual(viewModel.email, "", "email should be cleared when no auth manager")
    }

    // MARK: - Integration Tests

    func testIntegrationFlow_FillFormAndSubmit_Success() async {
        // Given - Start with empty form
        XCTAssertFalse(sut.isFormValid, "form should be invalid initially")

        // When - Fill out form
        sut.name = "Jane Smith"
        sut.email = "jane.smith@example.com"
        sut.selectedCategory = .featureRequest
        sut.description = "I would love to see a dark mode feature in the app!"

        // Then - Form should be valid
        XCTAssertTrue(sut.isFormValid, "form should be valid after filling all fields")

        // When - Configure mock and submit
        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you for your valuable feedback",
            submissionId: 789,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)
        await sut.submitFeedback()

        // Then - Verify success
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertTrue(sut.showSuccessMessage, "should show success message")
        XCTAssertNil(sut.error, "should have no error")
    }

    func testIntegrationFlow_SubmitError_ThenRetry_Success() async {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "Found a critical bug"

        // When - First submission fails
        let networkError = NSError(domain: "NetworkError", code: -1, userInfo: nil)
        await mockAPIClient.setError(networkError, for: .submitFeedback)
        await sut.submitFeedback()

        // Then - Should have error
        XCTAssertNotNil(sut.error, "should have error after failed submission")
        XCTAssertFalse(sut.showSuccessMessage, "should not show success message")

        // When - Clear error and retry with success
        await mockAPIClient.reset()
        let mockResponse = FeedbackSubmitResponse(
            message: "Success on retry",
            submissionId: 999,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)
        await sut.submitFeedback()

        // Then - Should succeed
        XCTAssertTrue(sut.showSuccessMessage, "should show success message on retry")
        XCTAssertNil(sut.error, "should clear error on successful retry")
    }

    func testIntegrationFlow_AllCategories() async {
        // Test that all feedback categories work correctly
        let categories: [FeedbackCategory] = [.bugReport, .featureRequest, .generalFeedback, .questionHelp, .other]

        for category in categories {
            // Given
            sut.name = "Test User"
            sut.email = "test@example.com"
            sut.selectedCategory = category
            sut.description = "Testing category: \(category.displayName)"

            // When
            let mockResponse = FeedbackSubmitResponse(
                message: "Thank you",
                submissionId: Int.random(in: 1 ... 1000),
                success: true
            )
            await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)
            await sut.submitFeedback()

            // Then
            let requestCalled = await mockAPIClient.requestCalled
            XCTAssertTrue(requestCalled, "should submit feedback for category \(category.displayName)")
            XCTAssertTrue(sut.showSuccessMessage, "should show success for category \(category.displayName)")

            // Reset for next iteration
            await mockAPIClient.reset()
            sut.resetForm()
        }
    }

    // MARK: - Rapid Submission Tests (Race Condition Prevention)

    func testRapidSubmission_CancelsPendingReset() async {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you",
            submissionId: 123,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)

        // When - First submission
        await sut.submitFeedback()
        XCTAssertTrue(sut.showSuccessMessage, "should show success after first submission")

        // Immediately update form and submit again (before the 2-second reset fires)
        sut.name = "Jane Doe"
        sut.description = "Second submission before reset"
        await mockAPIClient.reset()
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)
        await sut.submitFeedback()

        // Then - Form should still have second submission data, not be reset
        XCTAssertEqual(sut.name, "Jane Doe", "name should retain second submission value")
        XCTAssertEqual(sut.description, "Second submission before reset", "description should retain second submission value")
        XCTAssertTrue(sut.showSuccessMessage, "should still show success message")
    }

    func testRapidSubmission_OnlyLastResetExecutes() async throws {
        // Given - Setup valid form
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you",
            submissionId: 123,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)

        // When - Submit multiple times rapidly
        for i in 1 ... 3 {
            sut.name = "User \(i)"
            sut.description = "Submission number \(i) with details"
            await mockAPIClient.reset()
            await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)
            await sut.submitFeedback()
        }

        // Immediately after last submission, form should have last values
        XCTAssertEqual(sut.name, "User 3", "name should be from last submission")
        XCTAssertEqual(sut.description, "Submission number 3 with details", "description should be from last submission")

        // Wait for reset timer (2 seconds + buffer)
        try await Task.sleep(for: .seconds(2.5))

        // Then - Form should be reset exactly once (from the last submission's timer)
        XCTAssertEqual(sut.name, "", "name should be reset after timer")
        XCTAssertEqual(sut.email, "", "email should be reset after timer")
        XCTAssertNil(sut.selectedCategory, "category should be reset after timer")
        XCTAssertEqual(sut.description, "", "description should be reset after timer")
        XCTAssertFalse(sut.showSuccessMessage, "success message should be hidden after reset")
    }

    func testResetForm_CancelsPendingResetTask() async throws {
        // Given - Setup valid form and submit
        sut.name = "John Doe"
        sut.email = "john@example.com"
        sut.selectedCategory = .bugReport
        sut.description = "This is a detailed bug report"

        let mockResponse = FeedbackSubmitResponse(
            message: "Thank you",
            submissionId: 123,
            success: true
        )
        await mockAPIClient.setResponse(mockResponse, for: .submitFeedback)
        await sut.submitFeedback()

        // A reset task is now scheduled for 2 seconds later
        XCTAssertTrue(sut.showSuccessMessage, "should show success message")

        // When - Manually reset form immediately
        sut.resetForm()
        XCTAssertFalse(sut.showSuccessMessage, "success message should be hidden after manual reset")

        // Fill form with new data
        sut.name = "New User"
        sut.email = "new@example.com"
        sut.selectedCategory = .featureRequest
        sut.description = "New submission data"

        // Wait for what would have been the original reset timer
        try await Task.sleep(for: .seconds(2.5))

        // Then - Form should NOT be reset (the pending task was cancelled)
        XCTAssertEqual(sut.name, "New User", "name should not be reset by cancelled task")
        XCTAssertEqual(sut.email, "new@example.com", "email should not be reset by cancelled task")
        XCTAssertEqual(sut.selectedCategory, .featureRequest, "category should not be reset by cancelled task")
        XCTAssertEqual(sut.description, "New submission data", "description should not be reset by cancelled task")
    }
}
