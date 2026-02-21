@testable import AIQ
import Combine
import XCTest

@MainActor
final class RegistrationViewModelTests: XCTestCase {
    var sut: RegistrationViewModel!
    var mockAuthManager: MockAuthManager!

    override func setUp() {
        super.setUp()
        mockAuthManager = MockAuthManager()
        sut = RegistrationViewModel(authManager: mockAuthManager)
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        XCTAssertEqual(sut.email, "", "email should be empty initially")
        XCTAssertEqual(sut.password, "", "password should be empty initially")
        XCTAssertEqual(sut.confirmPassword, "", "confirmPassword should be empty initially")
        XCTAssertEqual(sut.firstName, "", "firstName should be empty initially")
        XCTAssertEqual(sut.lastName, "", "lastName should be empty initially")
        XCTAssertFalse(sut.isLoading, "isLoading should be false initially")
        XCTAssertNil(sut.error, "error should be nil initially")
    }

    // MARK: - Form Validation Tests

    func testFormValidation_AllFieldsEmpty() {
        XCTAssertFalse(sut.isFormValid, "form with empty fields should be invalid")
    }

    func testFormValidation_PartiallyFilledForm() {
        sut.email = "test@example.com"
        sut.password = "password123"
        XCTAssertFalse(sut.isFormValid, "partially filled form should be invalid")
    }

    func testFormValidation_PasswordMismatch() {
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "differentpassword"
        sut.firstName = "John"
        sut.lastName = "Doe"
        XCTAssertFalse(sut.isFormValid, "form with password mismatch should be invalid")
    }

    func testFormValidation_AllFieldsValid() {
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        XCTAssertTrue(sut.isFormValid, "form with all valid fields should be valid")
    }

    // MARK: - Registration Action Tests

    func testRegister_SuccessfulRegistration() async {
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        mockAuthManager.shouldSucceedRegister = true

        await sut.register()

        XCTAssertTrue(mockAuthManager.registerCalled)
        XCTAssertEqual(mockAuthManager.lastRegisterEmail, "test@example.com")
        XCTAssertEqual(mockAuthManager.lastRegisterPassword, "password123")
        XCTAssertEqual(mockAuthManager.lastRegisterFirstName, "John")
        XCTAssertEqual(mockAuthManager.lastRegisterLastName, "Doe")
        XCTAssertEqual(sut.email, "")
        XCTAssertEqual(sut.password, "")
        XCTAssertEqual(sut.confirmPassword, "")
        XCTAssertEqual(sut.firstName, "")
        XCTAssertEqual(sut.lastName, "")
    }

    func testRegister_TrimsWhitespace() async {
        // Given - Email and names with leading/trailing whitespace
        // Note: Email with whitespace is now correctly rejected by validation
        sut.email = "test@example.com" // No whitespace for valid email
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "  John  "
        sut.lastName = "  Doe  "
        mockAuthManager.shouldSucceedRegister = true

        // When
        await sut.register()

        // Then - Names should be trimmed, email passed without whitespace
        XCTAssertEqual(mockAuthManager.lastRegisterEmail, "test@example.com")
        XCTAssertEqual(mockAuthManager.lastRegisterFirstName, "John")
        XCTAssertEqual(mockAuthManager.lastRegisterLastName, "Doe")
    }

    func testRegister_EmailWithWhitespace_RejectsForm() async {
        // Given - Email with leading/trailing whitespace
        sut.email = "  test@example.com  "
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        mockAuthManager.shouldSucceedRegister = true

        // When
        await sut.register()

        // Then - Form should be rejected due to invalid email
        XCTAssertFalse(mockAuthManager.registerCalled, "register should not be called with email containing whitespace")
        XCTAssertNotNil(sut.error, "error should be set for invalid email")
    }

    func testRegister_FailedRegistration() async {
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        mockAuthManager.shouldSucceedRegister = false

        await sut.register()

        XCTAssertTrue(mockAuthManager.registerCalled)
        XCTAssertNotNil(mockAuthManager.authError)
    }

    func testRegister_InvalidForm_DoesNotCallAuthManager() async {
        sut.email = "invalidemail"
        sut.password = "short"

        await sut.register()

        XCTAssertFalse(mockAuthManager.registerCalled)
        XCTAssertNotNil(sut.error)
        XCTAssertEqual((sut.error as NSError?)?.localizedDescription, "Please fill in all fields correctly")
    }

    // MARK: - Loading State Tests

    func testRegister_LoadingStateBindingFromAuthManager() async {
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        mockAuthManager.shouldSucceedRegister = true
        mockAuthManager.registerDelay = 0.1

        let registerTask = Task { await sut.register() }
        try? await Task.sleep(nanoseconds: 10_000_000)

        XCTAssertTrue(sut.isLoading)
        await registerTask.value
        XCTAssertFalse(sut.isLoading)
    }

    // MARK: - Error Binding Tests

    func testErrorBindingFromAuthManager() async {
        mockAuthManager.shouldSucceedRegister = false
        mockAuthManager.authError = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )
        try? await Task.sleep(nanoseconds: 10_000_000)
        XCTAssertNotNil(sut.error)
    }

    // MARK: - Clear Form Tests

    func testClearForm() {
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

        sut.clearForm()

        XCTAssertEqual(sut.email, "")
        XCTAssertEqual(sut.password, "")
        XCTAssertEqual(sut.confirmPassword, "")
        XCTAssertEqual(sut.firstName, "")
        XCTAssertEqual(sut.lastName, "")
        XCTAssertNil(sut.error)
        XCTAssertTrue(mockAuthManager.clearErrorCalled)
    }

    // MARK: - Integration Tests

    func testCompleteRegistrationFlow() async {
        XCTAssertFalse(sut.isFormValid)
        sut.email = "newuser@example.com"
        sut.password = "securepassword123"
        sut.confirmPassword = "securepassword123"
        sut.firstName = "Jane"
        sut.lastName = "Smith"
        XCTAssertTrue(sut.isFormValid)

        await sut.register()

        XCTAssertTrue(mockAuthManager.registerCalled)
        XCTAssertEqual(sut.email, "")
        XCTAssertEqual(sut.password, "")
        XCTAssertEqual(sut.confirmPassword, "")
        XCTAssertEqual(sut.firstName, "")
        XCTAssertEqual(sut.lastName, "")
    }
}
