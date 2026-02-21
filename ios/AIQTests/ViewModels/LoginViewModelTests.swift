@testable import AIQ
import Combine
import XCTest

@MainActor
final class LoginViewModelTests: XCTestCase {
    var sut: LoginViewModel!
    var mockAuthManager: MockAuthManager!

    override func setUp() {
        super.setUp()
        mockAuthManager = MockAuthManager()
        sut = LoginViewModel(authManager: mockAuthManager)
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        // Then
        XCTAssertEqual(sut.email, "", "email should be empty initially")
        XCTAssertEqual(sut.password, "", "password should be empty initially")
        XCTAssertFalse(sut.showRegistration, "showRegistration should be false initially")
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

    func testEmailValidation_InvalidEmail_NoAtSign() {
        // Given
        sut.email = "invalidemail.com"

        // Then
        XCTAssertFalse(sut.isEmailValid, "email without @ should be invalid")
        XCTAssertEqual(
            sut.emailError,
            "Please enter a valid email address",
            "should show error message for invalid email"
        )
    }

    func testEmailValidation_InvalidEmail_NoDot() {
        // Given
        sut.email = "invalid@emailcom"

        // Then
        XCTAssertFalse(sut.isEmailValid, "email without . should be invalid")
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

    func testPasswordValidation_ExactlyEightCharacters() {
        // Given
        sut.password = "12345678"

        // Then
        XCTAssertTrue(sut.isPasswordValid, "password with exactly 8 characters should be valid")
        XCTAssertNil(sut.passwordError, "valid password should not show error")
    }

    // MARK: - Form Validation Tests

    func testFormValidation_BothFieldsEmpty() {
        // Given
        sut.email = ""
        sut.password = ""

        // Then
        XCTAssertFalse(sut.isFormValid, "form with empty fields should be invalid")
    }

    func testFormValidation_OnlyEmailValid() {
        // Given
        sut.email = "test@example.com"
        sut.password = "short"

        // Then
        XCTAssertFalse(sut.isFormValid, "form with only valid email should be invalid")
    }

    func testFormValidation_OnlyPasswordValid() {
        // Given
        sut.email = "invalidemail"
        sut.password = "validpassword123"

        // Then
        XCTAssertFalse(sut.isFormValid, "form with only valid password should be invalid")
    }

    func testFormValidation_BothFieldsValid() {
        // Given
        sut.email = "test@example.com"
        sut.password = "validpassword123"

        // Then
        XCTAssertTrue(sut.isFormValid, "form with both valid fields should be valid")
    }

    // MARK: - Login Action Tests

    func testLogin_SuccessfulLogin() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "validpassword123"
        mockAuthManager.shouldSucceedLogin = true

        // When
        await sut.login()

        // Then
        XCTAssertTrue(mockAuthManager.loginCalled, "login should be called on authManager")
        XCTAssertEqual(mockAuthManager.lastLoginEmail, "test@example.com")
        XCTAssertEqual(mockAuthManager.lastLoginPassword, "validpassword123")
        XCTAssertEqual(sut.email, "", "email should be cleared after successful login")
        XCTAssertEqual(sut.password, "", "password should be cleared after successful login")
        XCTAssertNil(sut.error, "error should be nil after successful login")
    }

    func testLogin_FailedLogin() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "wrongpassword"
        mockAuthManager.shouldSucceedLogin = false

        // When
        await sut.login()

        // Then
        XCTAssertTrue(mockAuthManager.loginCalled, "login should be called on authManager")
        XCTAssertNotNil(mockAuthManager.authError, "authError should be set on failure")
    }

    func testLogin_InvalidForm_DoesNotCallAuthManager() async {
        // Given
        sut.email = "invalidemail"
        sut.password = "short"

        // When
        await sut.login()

        // Then
        XCTAssertFalse(
            mockAuthManager.loginCalled,
            "login should not be called with invalid form"
        )
        XCTAssertNotNil(sut.error, "error should be set for invalid form")
        XCTAssertEqual(
            (sut.error as NSError?)?.localizedDescription,
            "Please enter valid email and password"
        )
    }

    func testLogin_EmptyFields_DoesNotCallAuthManager() async {
        // Given
        sut.email = ""
        sut.password = ""

        // When
        await sut.login()

        // Then
        XCTAssertFalse(
            mockAuthManager.loginCalled,
            "login should not be called with empty fields"
        )
        XCTAssertNotNil(sut.error, "error should be set for empty fields")
    }

    // MARK: - Loading State Tests

    func testLogin_LoadingStateBindingFromAuthManager() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "validpassword123"
        mockAuthManager.shouldSucceedLogin = true
        mockAuthManager.loginDelay = 0.1

        // When
        let loginTask = Task {
            await sut.login()
        }

        // Small delay to allow loading state to propagate
        try? await Task.sleep(nanoseconds: 10_000_000) // 0.01 seconds

        // Then - during login
        XCTAssertTrue(sut.isLoading, "isLoading should be true during login")

        // Wait for login to complete
        await loginTask.value

        // Then - after login
        XCTAssertFalse(sut.isLoading, "isLoading should be false after login completes")
    }

    // MARK: - Error Binding Tests

    func testErrorBindingFromAuthManager() async {
        // Given
        mockAuthManager.shouldSucceedLogin = false

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

    // MARK: - Show Registration Tests

    func testShowRegistrationScreen() {
        // Given
        XCTAssertFalse(sut.showRegistration, "showRegistration should initially be false")

        // When
        sut.showRegistrationScreen()

        // Then
        XCTAssertTrue(sut.showRegistration, "showRegistration should be true after calling method")
    }

    // MARK: - Clear Form Tests

    func testClearForm() {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
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
        XCTAssertNil(sut.error, "error should be cleared")
        XCTAssertTrue(
            mockAuthManager.clearErrorCalled,
            "clearError should be called on authManager"
        )
    }

    // MARK: - Integration Tests

    func testCompleteLoginFlow() async {
        // Given - Start with empty form
        XCTAssertFalse(sut.isFormValid)

        // When - Fill in valid credentials
        sut.email = "user@example.com"
        sut.password = "securepassword123"

        // Then - Form should be valid
        XCTAssertTrue(sut.isFormValid)

        // When - Submit login
        await sut.login()

        // Then - Should successfully login and clear form
        XCTAssertTrue(mockAuthManager.loginCalled)
        XCTAssertEqual(sut.email, "")
        XCTAssertEqual(sut.password, "")
    }
}
