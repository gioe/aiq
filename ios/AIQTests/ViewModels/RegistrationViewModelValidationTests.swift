@testable import AIQ
import Combine
import XCTest

@MainActor
final class RegistrationViewModelValidationTests: XCTestCase {
    var sut: RegistrationViewModel!
    var mockAuthManager: MockAuthManager!

    override func setUp() {
        super.setUp()
        mockAuthManager = MockAuthManager()
        sut = RegistrationViewModel(authManager: mockAuthManager)
    }

    // MARK: - Email Validation Tests

    func testEmailValidation_EmptyEmail() {
        sut.email = ""
        XCTAssertFalse(sut.isEmailValid, "empty email should be invalid")
        XCTAssertNil(sut.emailError, "empty email should not show error")
    }

    func testEmailValidation_InvalidEmail() {
        sut.email = "invalidemail"
        XCTAssertFalse(sut.isEmailValid, "email without @ and . should be invalid")
        XCTAssertEqual(sut.emailError, "Please enter a valid email address")
    }

    func testEmailValidation_ValidEmail() {
        sut.email = "test@example.com"
        XCTAssertTrue(sut.isEmailValid, "valid email should be valid")
        XCTAssertNil(sut.emailError, "valid email should not show error")
    }

    // MARK: - Password Validation Tests

    func testPasswordValidation_EmptyPassword() {
        sut.password = ""
        XCTAssertFalse(sut.isPasswordValid, "empty password should be invalid")
        XCTAssertNil(sut.passwordError, "empty password should not show error")
    }

    func testPasswordValidation_ShortPassword() {
        sut.password = "short"
        XCTAssertFalse(sut.isPasswordValid, "password less than 8 characters should be invalid")
        XCTAssertEqual(sut.passwordError, "Password must be at least 8 characters")
    }

    func testPasswordValidation_ValidPassword() {
        sut.password = "validpassword123"
        XCTAssertTrue(sut.isPasswordValid, "password with 8+ characters should be valid")
        XCTAssertNil(sut.passwordError, "valid password should not show error")
    }

    // MARK: - Confirm Password Validation Tests

    func testConfirmPasswordValidation_EmptyConfirmPassword() {
        sut.password = "password123"
        sut.confirmPassword = ""
        XCTAssertFalse(sut.isConfirmPasswordValid, "empty confirm password should be invalid")
        XCTAssertNil(sut.confirmPasswordError, "empty confirm password should not show error")
    }

    func testConfirmPasswordValidation_PasswordsDoNotMatch() {
        sut.password = "password123"
        sut.confirmPassword = "differentpassword"
        XCTAssertFalse(sut.isConfirmPasswordValid, "mismatched passwords should be invalid")
        XCTAssertEqual(sut.confirmPasswordError, "Passwords do not match")
    }

    func testConfirmPasswordValidation_PasswordsMatch() {
        sut.password = "password123"
        sut.confirmPassword = "password123"
        XCTAssertTrue(sut.isConfirmPasswordValid, "matching passwords should be valid")
        XCTAssertNil(sut.confirmPasswordError)
    }

    // MARK: - First Name Validation Tests

    func testFirstNameValidation_EmptyFirstName() {
        sut.firstName = ""
        XCTAssertFalse(sut.isFirstNameValid, "empty first name should be invalid")
        XCTAssertNil(sut.firstNameError, "empty first name should not show error")
    }

    func testFirstNameValidation_WhitespaceOnly() {
        sut.firstName = "   "
        XCTAssertFalse(sut.isFirstNameValid, "whitespace-only first name should be invalid")
        XCTAssertEqual(sut.firstNameError, "First name is required")
    }

    func testFirstNameValidation_ValidFirstName() {
        sut.firstName = "John"
        XCTAssertTrue(sut.isFirstNameValid, "valid first name should be valid")
        XCTAssertNil(sut.firstNameError, "valid first name should not show error")
    }

    func testFirstNameValidation_ValidFirstNameWithWhitespace() {
        sut.firstName = "  John  "
        XCTAssertTrue(sut.isFirstNameValid)
        XCTAssertNil(sut.firstNameError)
    }

    // MARK: - Last Name Validation Tests

    func testLastNameValidation_EmptyLastName() {
        sut.lastName = ""
        XCTAssertFalse(sut.isLastNameValid, "empty last name should be invalid")
        XCTAssertNil(sut.lastNameError, "empty last name should not show error")
    }

    func testLastNameValidation_WhitespaceOnly() {
        sut.lastName = "   "
        XCTAssertFalse(sut.isLastNameValid, "whitespace-only last name should be invalid")
        XCTAssertEqual(sut.lastNameError, "Last name is required")
    }

    func testLastNameValidation_ValidLastName() {
        sut.lastName = "Doe"
        XCTAssertTrue(sut.isLastNameValid, "valid last name should be valid")
        XCTAssertNil(sut.lastNameError, "valid last name should not show error")
    }
}
