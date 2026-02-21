@testable import AIQ
import Combine
import XCTest

@MainActor
final class RegistrationViewModelBirthYearTests: XCTestCase {
    var sut: RegistrationViewModel!
    var mockAuthManager: MockAuthManager!

    override func setUp() {
        super.setUp()
        mockAuthManager = MockAuthManager()
        sut = RegistrationViewModel(authManager: mockAuthManager)
    }

    // MARK: - Birth Year Validation Tests

    func testBirthYearValidation_EmptyBirthYear() {
        // Given
        sut.birthYear = ""

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "empty birth year should be valid (optional field)")
        XCTAssertNil(sut.birthYearError, "empty birth year should not show error")
    }

    func testBirthYearValidation_WhitespaceOnly() {
        // Given
        sut.birthYear = "   "

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "whitespace-only birth year should be valid (treated as empty)")
        XCTAssertNil(sut.birthYearError, "whitespace-only birth year should not show error")
    }

    func testBirthYearValidation_InvalidFormat_NonNumeric() {
        // Given
        sut.birthYear = "abc"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "non-numeric birth year should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year must be a valid year")
    }

    func testBirthYearValidation_InvalidFormat_Decimal() {
        // Given
        sut.birthYear = "1990.5"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "decimal birth year should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year must be a valid year")
    }

    func testBirthYearValidation_TooOld_1899() {
        // Given
        sut.birthYear = "1899"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "year before 1900 should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year must be 1900 or later")
    }

    func testBirthYearValidation_TooOld_0() {
        // Given
        sut.birthYear = "0"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "year 0 should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year must be 1900 or later")
    }

    func testBirthYearValidation_Negative() {
        // Given
        sut.birthYear = "-100"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "negative year should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year must be 1900 or later")
    }

    func testBirthYearValidation_FutureYear() {
        // Given
        let currentYear = Calendar.current.component(.year, from: Date())
        sut.birthYear = "\(currentYear + 1)"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "year in the future should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year cannot be in the future")
    }

    func testBirthYearValidation_FarFutureYear() {
        // Given
        sut.birthYear = "2100"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "far future year should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year cannot be in the future")
    }

    func testBirthYearValidation_ValidYear_1900() {
        // Given
        sut.birthYear = "1900"

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "year 1900 (minimum) should be valid")
        XCTAssertNil(sut.birthYearError, "valid birth year should not show error")
    }

    func testBirthYearValidation_ValidYear_CurrentYear() {
        // Given
        let currentYear = Calendar.current.component(.year, from: Date())
        sut.birthYear = "\(currentYear)"

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "current year should be valid")
        XCTAssertNil(sut.birthYearError, "valid birth year should not show error")
    }

    func testBirthYearValidation_ValidYear_MidRange() {
        // Given
        sut.birthYear = "1990"

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "mid-range year should be valid")
        XCTAssertNil(sut.birthYearError, "valid birth year should not show error")
    }

    func testBirthYearValidation_ValidYear_1950() {
        // Given
        sut.birthYear = "1950"

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "1950 should be valid")
        XCTAssertNil(sut.birthYearError, "valid birth year should not show error")
    }

    func testBirthYearValidation_ValidYear_2000() {
        // Given
        sut.birthYear = "2000"

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "2000 should be valid")
        XCTAssertNil(sut.birthYearError, "valid birth year should not show error")
    }

    func testBirthYearValidation_ValidYear_WithWhitespace() {
        // Given
        sut.birthYear = "  1990  "

        // Then
        XCTAssertTrue(sut.isBirthYearValid, "birth year with surrounding whitespace should be valid")
        XCTAssertNil(sut.birthYearError, "valid birth year should not show error")
    }

    // MARK: - Form Validation with Birth Year

    func testFormValidation_WithInvalidBirthYear() {
        // Given - All required fields valid, but birth year invalid
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.birthYear = "3000" // Invalid: future year

        // Then
        XCTAssertFalse(sut.isFormValid, "form with invalid birth year should be invalid")
    }

    func testFormValidation_WithEmptyBirthYear() {
        // Given - All required fields valid, birth year empty (optional)
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.birthYear = ""

        // Then
        XCTAssertTrue(sut.isFormValid, "form should be valid when birth year is empty (optional field)")
    }

    func testFormValidation_WithValidBirthYear() {
        // Given - All fields valid including birth year
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.birthYear = "1990"

        // Then
        XCTAssertTrue(sut.isFormValid, "form with all valid fields should be valid")
    }

    // MARK: - Registration with Birth Year

    func testRegister_WithValidBirthYear() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.birthYear = "1990"
        mockAuthManager.shouldSucceedRegister = true

        // When
        await sut.register()

        // Then
        XCTAssertTrue(mockAuthManager.registerCalled, "register should be called")
        XCTAssertEqual(mockAuthManager.lastRegisterBirthYear, 1990, "birth year should be passed as integer")
    }

    func testRegister_WithEmptyBirthYear() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.birthYear = ""
        mockAuthManager.shouldSucceedRegister = true

        // When
        await sut.register()

        // Then
        XCTAssertTrue(mockAuthManager.registerCalled, "register should be called")
        XCTAssertNil(mockAuthManager.lastRegisterBirthYear, "birth year should be nil when empty")
    }

    func testRegister_WithWhitespaceBirthYear() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.birthYear = "   "
        mockAuthManager.shouldSucceedRegister = true

        // When
        await sut.register()

        // Then
        XCTAssertTrue(mockAuthManager.registerCalled, "register should be called")
        XCTAssertNil(mockAuthManager.lastRegisterBirthYear, "birth year should be nil when whitespace-only")
    }

    func testRegister_WithInvalidBirthYear_DoesNotCallAuthManager() async {
        // Given
        sut.email = "test@example.com"
        sut.password = "password123"
        sut.confirmPassword = "password123"
        sut.firstName = "John"
        sut.lastName = "Doe"
        sut.birthYear = "3000" // Invalid: future year

        // When
        await sut.register()

        // Then
        XCTAssertFalse(mockAuthManager.registerCalled, "register should not be called with invalid birth year")
        XCTAssertNotNil(sut.error, "error should be set for invalid form")
    }

    // MARK: - Clear Form Tests

    func testClearForm_ClearsBirthYear() {
        // Given
        sut.birthYear = "1990"

        // When
        sut.clearForm()

        // Then
        XCTAssertEqual(sut.birthYear, "", "birth year should be cleared")
    }

    // MARK: - Edge Case Tests

    func testBirthYearValidation_LeadingZeros() {
        // Given
        sut.birthYear = "01990"

        // Then
        // Leading zeros are valid (Int() will parse it correctly)
        XCTAssertTrue(sut.isBirthYearValid, "year with leading zeros should be parsed correctly")
        XCTAssertNil(sut.birthYearError)
    }

    func testBirthYearValidation_TrailingCharacters() {
        // Given
        sut.birthYear = "1990abc"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "year with trailing characters should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year must be a valid year")
    }

    func testBirthYearValidation_SpecialCharacters() {
        // Given
        sut.birthYear = "19@90"

        // Then
        XCTAssertFalse(sut.isBirthYearValid, "year with special characters should be invalid")
        XCTAssertEqual(sut.birthYearError, "Birth year must be a valid year")
    }
}
