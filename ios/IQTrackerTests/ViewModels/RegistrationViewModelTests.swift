import Combine
import XCTest

@testable import IQTracker

@MainActor
final class RegistrationViewModelTests: XCTestCase {
    var sut: RegistrationViewModel!
    var mockAuthManager: MockAuthManager!

    override func setUp() {
        super.setUp()
        mockAuthManager = MockAuthManager()
        sut = RegistrationViewModel(authManager: mockAuthManager)
    }

    override func tearDown() {
        sut = nil
        mockAuthManager = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        // Then
        XCTAssertEqual(sut.email, "", "email should be empty initially")
        XCTAssertEqual(sut.password, "", "password should be empty initially")
        XCTAssertEqual(sut.confirmPassword, "", "confirmPassword should be empty initially")
        XCTAssertEqual(sut.firstName, "", "firstName should be empty initially")
        XCTAssertEqual(sut.lastName, "", "lastName should be empty initially")
        XCTAssertFalse(sut.isLoading, "isLoading should be false initially")
        XCTAssertNil(sut.error, "error should be nil initially")
    }

    // MARK: - Email Validation Tests

    func testEmailValidation_EmptyEmail() {
        // Given
        sut.email = ""

        // Then
        XCTAssertFalse(sut.isEmailValid, "empty email should be invalid")
        XCTAssertNil(sut.emailError, "empty email should not show error")
    }

    func testEmailValidation_InvalidEmail() {
        // Given
        sut.email = "invalidemail"

        // Then
        XCTAssertFalse(sut.isEmailValid, "email without @ and . should be invalid")
        XCTAssertEqual(
            sut.emailError,
            "Please enter a valid email address",
            "should show error message for invalid email"
        )
    }

    func testEmailValidation_ValidEmail() {
        // Given
        sut.email = "test@example.com"

        // Then
        XCTAssertTrue(sut.isEmailValid, "valid email should be valid")
        XCTAssertNil(sut.emailError, "valid email should not show error")
    }

    // MARK: - Password Validation Tests

    func testPasswordValidation_EmptyPassword() {
        // Given
        sut.password = ""

        // Then
        XCTAssertFalse(sut.isPasswordValid, "empty password should be invalid")
        XCTAssertNil(sut.passwordError, "empty password should not show error")
    }

    func testPasswordValidation_ShortPassword() {
        // Given
        sut.password = "short"

        // Then
        XCTAssertFalse(sut.isPasswordValid, "password less than 8 characters should be invalid")
        XCTAssertEqual(
            sut.passwordError,
            "Password must be at least 8 characters",
            "should show error message for short password"
        )
    }

    func testPasswordValidation_ValidPassword() {
        // Given
        sut.password = "validpassword123"

        // Then
        XCTAssertTrue(sut.isPasswordValid, "password with 8+ characters should be valid")
        XCTAssertNil(sut.passwordError, "valid password should not show error")
    }

    // MARK: - Confirm Password Validation Tests

    func testConfirmPasswordValidation_EmptyConfirmPassword() {
        // Given
        sut.password = "password123"
        sut.confirmPassword = ""

        // Then
        XCTAssertFalse(sut.isConfirmPasswordValid, "empty confirm password should be invalid")
        XCTAssertNil(
            sut.confirmPasswordError,
            "empty confirm password should not show error"
        )
    }

    func testConfirmPasswordValidation_PasswordsDoNotMatch() {
        // Given
        sut.password = "password123"
        sut.confirmPassword = "differentpassword"

        // Then
        XCTAssertFalse(sut.isConfirmPasswordValid, "mismatched passwords should be invalid")
        XCTAssertEqual(
            sut.confirmPasswordError,
            "Passwords do not match",
            "should show error message for mismatched passwords"
        )
    }

    func testConfirmPasswordValidation_PasswordsMatch() {
        // Given
        sut.password = "password123"
        sut.confirmPassword = "password123"

        // Then
        XCTAssertTrue(sut.isConfirmPasswordValid, "matching passwords should be valid")
        XCTAssertNil(sut.confirmPasswordError, "matching passwords should not show error")
    }

    // MARK: - First Name Validation Tests

    func testFirstNameValidation_EmptyFirstName() {
        // Given
        sut.firstName = ""

        // Then
        XCTAssertFalse(sut.isFirstNameValid, "empty first name should be invalid")
        XCTAssertNil(sut.firstNameError, "empty first name should not show error")
    }

    func testFirstNameValidation_WhitespaceOnly() {
        // Given
        sut.firstName = "   "

        // Then
        XCTAssertFalse(sut.isFirstNameValid, "whitespace-only first name should be invalid")
        XCTAssertEqual(
            sut.firstNameError,
            "First name is required",
            "should show error message for whitespace-only name"
        )
    }

    func testFirstNameValidation_ValidFirstName() {
        // Given
        sut.firstName = "John"

        // Then
        XCTAssertTrue(sut.isFirstNameValid, "valid first name should be valid")
        XCTAssertNil(sut.firstNameError, "valid first name should not show error")
    }

    func testFirstNameValidation_ValidFirstNameWithWhitespace() {
        // Given
        sut.firstName = "  John  "

        // Then
        XCTAssertTrue(sut.isFirstNameValid, "first name with surrounding whitespace should be valid")
        XCTAssertNil(sut.firstNameError, "should not show error for name with whitespace")
    }

    // MARK: - Last Name Validation Tests

    func testLastNameValidation_EmptyLastName() {
        // Given
        sut.lastName = ""

        // Then
        XCTAssertFalse(sut.isLastNameValid, "empty last name should be invalid")
        XCTAssertNil(sut.lastNameError, "empty last name should not show error")
    }

    func testLastNameValidation_WhitespaceOnly() {
        // Given
        sut.lastName = "   "

        // Then
        XCTAssertFalse(sut.isLastNameValid, "whitespace-only last name should be invalid")
        XCTAssertEqual(
            sut.lastNameError,
            "Last name is required",
            "should show error message for whitespace-only name"
        )
    }

    func testLastNameValidation_ValidLastName() {
        // Given
        sut.lastName = "Doe"

        // Then
        XCTAssertTrue(sut.isLastNameValid, "valid last name should be valid")
        XCTAssertNil(sut.lastNameError, "valid last name should not show error")
    }

    // MARK: - Form Validation Tests

    func testFormValidation_AllFieldsEmpty() {
        // Given - all fields empty

        // Then
        XCTAssertFalse(sut.isFormValid, "form with empty fields should be invalid")
    }

    func testFormValidation_PartiallyFilledForm() {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        // Missing confirmPassword, firstName, lastName

        // Then
        XCTAssertFalse(sut.isFormValid, "partially filled form should be invalid")
    }

    func testFormValidation_PasswordMismatch() {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "differentpassword"
        sut.firstName = "John"
        sut.lastName = "Doe"

        // Then
        XCTAssertFalse(sut.isFormValid, "form with password mismatch should be invalid")
    }

    func testFormValidation_AllFieldsValid() {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"

        // Then
        XCTAssertTrue(sut.isFormValid, "form with all valid fields should be valid")
    }

    // MARK: - Registration Action Tests

    func testRegister_SuccessfulRegistration() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        mockAuthManager.shouldSucceedRegister = true

        // When
        await sut.register()

        // Then
        XCTAssertTrue(mockAuthManager.registerCalled, "register should be called on authManager")
        XCTAssertEqual(mockAuthManager.lastRegisterEmail, "test@example.com")
        XCTAssertEqual(mockAuthManager.lastRegisterPassword, "password123")
        XCTAssertEqual(mockAuthManager.lastRegisterFirstName, "John")
        XCTAssertEqual(mockAuthManager.lastRegisterLastName, "Doe")
        XCTAssertEqual(sut.email, "", "email should be cleared after successful registration")
        XCTAssertEqual(sut.password, "", "password should be cleared after successful registration")
        XCTAssertEqual(
            sut.confirmPassword,
            "",
            "confirmPassword should be cleared after successful registration"
        )
        XCTAssertEqual(
            sut.firstName,
            "",
            "firstName should be cleared after successful registration"
        )
        XCTAssertEqual(sut.lastName, "", "lastName should be cleared after successful registration")
    }

    func testRegister_TrimsWhitespace() async {
        // Given
        sut.email = "  test@example.com  "
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "  John  "
        sut.lastName = "  Doe  "
        mockAuthManager.shouldSucceedRegister = true

        // When
        await sut.register()

        // Then
        XCTAssertEqual(
            mockAuthManager.lastRegisterEmail,
            "test@example.com",
            "email should be trimmed"
        )
        XCTAssertEqual(
            mockAuthManager.lastRegisterFirstName,
            "John",
            "firstName should be trimmed"
        )
        XCTAssertEqual(
            mockAuthManager.lastRegisterLastName,
            "Doe",
            "lastName should be trimmed"
        )
    }

    func testRegister_FailedRegistration() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        mockAuthManager.shouldSucceedRegister = false

        // When
        await sut.register()

        // Then
        XCTAssertTrue(mockAuthManager.registerCalled, "register should be called on authManager")
        XCTAssertNotNil(mockAuthManager.authError, "authError should be set on failure")
    }

    func testRegister_InvalidForm_DoesNotCallAuthManager() async {
        // Given
        sut.email = "invalidemail"
        sut.password = "short"

        // When
        await sut.register()

        // Then
        XCTAssertFalse(
            mockAuthManager.registerCalled,
            "register should not be called with invalid form"
        )
        XCTAssertNotNil(sut.error, "error should be set for invalid form")
        XCTAssertEqual(
            (sut.error as NSError?)?.localizedDescription,
            "Please fill in all fields correctly"
        )
    }

    // MARK: - Loading State Tests

    func testRegister_LoadingStateBindingFromAuthManager() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        mockAuthManager.shouldSucceedRegister = true
        mockAuthManager.registerDelay = 0.1

        // When
        let registerTask = Task {
            await sut.register()
        }

        // Small delay to allow loading state to propagate
        try? await Task.sleep(nanoseconds: 10_000_000) // 0.01 seconds

        // Then - during registration
        XCTAssertTrue(sut.isLoading, "isLoading should be true during registration")

        // Wait for registration to complete
        await registerTask.value

        // Then - after registration
        XCTAssertFalse(sut.isLoading, "isLoading should be false after registration completes")
    }

    // MARK: - Error Binding Tests

    func testErrorBindingFromAuthManager() async {
        // Given
        mockAuthManager.shouldSucceedRegister = false

        // When
        mockAuthManager.authError = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )

        // Small delay to allow binding to propagate
        try? await Task.sleep(nanoseconds: 10_000_000)

        // Then
        XCTAssertNotNil(sut.error, "error should be bound from authManager")
    }

    // MARK: - Clear Form Tests

    func testClearForm() {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.error = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )
        mockAuthManager.authError = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Auth error"]
        )

        // When
        sut.clearForm()

        // Then
        XCTAssertEqual(sut.email, "", "email should be cleared")
        XCTAssertEqual(sut.password, "", "password should be cleared")
        XCTAssertEqual(sut.confirmPassword, "", "confirmPassword should be cleared")
        XCTAssertEqual(sut.firstName, "", "firstName should be cleared")
        XCTAssertEqual(sut.lastName, "", "lastName should be cleared")
        XCTAssertNil(sut.error, "error should be cleared")
        XCTAssertTrue(
            mockAuthManager.clearErrorCalled,
            "clearError should be called on authManager"
        )
    }

    // MARK: - Integration Tests

    func testCompleteRegistrationFlow() async {
        // Given - Start with empty form
        XCTAssertFalse(sut.isFormValid)

        // When - Fill in valid information
        sut.email = "newuser@example.com"
        sut.password = "securepassword123"
        sut.confirmPassword = "securepassword123"
        sut.firstName = "Jane"
        sut.lastName = "Smith"

        // Then - Form should be valid
        XCTAssertTrue(sut.isFormValid)

        // When - Submit registration
        await sut.register()

        // Then - Should successfully register and clear form
        XCTAssertTrue(mockAuthManager.registerCalled)
        XCTAssertEqual(sut.email, "")
        XCTAssertEqual(sut.password, "")
        XCTAssertEqual(sut.confirmPassword, "")
        XCTAssertEqual(sut.firstName, "")
        XCTAssertEqual(sut.lastName, "")
    }

    func testInvalidEmailFlow() {
        // Given
        sut.email = "invalid"

        // When - User starts typing
        // Then - Should show validation error
        XCTAssertFalse(sut.isEmailValid)
        XCTAssertNotNil(sut.emailError)
        XCTAssertFalse(sut.isFormValid)

        // When - User corrects email
        sut.email = "valid@example.com"

        // Then - Error should be cleared
        XCTAssertTrue(sut.isEmailValid)
        XCTAssertNil(sut.emailError)
    }

    func testPasswordMismatchFlow() {
        // Given
        sut.password = "password123"
        sut.confirmPassword = "different"

        // Then - Should show validation error
        XCTAssertFalse(sut.isConfirmPasswordValid)
        XCTAssertNotNil(sut.confirmPasswordError)
        XCTAssertFalse(sut.isFormValid)

        // When - User corrects confirm password
        sut.confirmPassword = "password123"

        // Then - Error should be cleared
        XCTAssertTrue(sut.isConfirmPasswordValid)
        XCTAssertNil(sut.confirmPasswordError)
    }
}
