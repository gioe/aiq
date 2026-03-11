@testable import SharedKit
import XCTest

final class SharedKitTests: XCTestCase {
    // MARK: - Validators Tests

    func testValidateEmail_ValidEmail() {
        let result = Validators.validateEmail("user@example.com")
        XCTAssertTrue(result.isValid)
    }

    func testValidateEmail_EmptyEmail() {
        let result = Validators.validateEmail("")
        XCTAssertFalse(result.isValid)
        XCTAssertEqual(result.errorMessage, "Email is required")
    }

    func testValidateEmail_InvalidFormat() {
        let result = Validators.validateEmail("not-an-email")
        XCTAssertFalse(result.isValid)
        XCTAssertEqual(result.errorMessage, "Please enter a valid email address")
    }

    func testValidatePassword_ValidPassword() {
        let result = Validators.validatePassword("password123")
        XCTAssertTrue(result.isValid)
    }

    func testValidatePassword_TooShort() {
        let result = Validators.validatePassword("short", minLength: 8)
        XCTAssertFalse(result.isValid)
    }

    func testValidatePassword_CustomMinLength() {
        let result = Validators.validatePassword("hi", minLength: 3)
        XCTAssertFalse(result.isValid)
        let resultOk = Validators.validatePassword("hey", minLength: 3)
        XCTAssertTrue(resultOk.isValid)
    }

    func testValidateName_ValidName() {
        let result = Validators.validateName("John")
        XCTAssertTrue(result.isValid)
    }

    func testValidateName_TooShort() {
        let result = Validators.validateName("J", minLength: 2)
        XCTAssertFalse(result.isValid)
    }

    func testValidatePasswordConfirmation_Match() {
        let result = Validators.validatePasswordConfirmation("password", "password")
        XCTAssertTrue(result.isValid)
    }

    func testValidatePasswordConfirmation_Mismatch() {
        let result = Validators.validatePasswordConfirmation("password", "different")
        XCTAssertFalse(result.isValid)
        XCTAssertEqual(result.errorMessage, "Passwords do not match")
    }

    func testValidateMinLength_Valid() {
        let result = Validators.validateMinLength("Hello, this is a description.", fieldName: "Description", min: 10)
        XCTAssertTrue(result.isValid)
    }

    func testValidateMinLength_TooShort() {
        let result = Validators.validateMinLength("Short", fieldName: "Description", min: 10)
        XCTAssertFalse(result.isValid)
    }

    func testValidateBirthYear_Valid() {
        let result = Validators.validateBirthYear("1990", minYear: 1900)
        XCTAssertTrue(result.isValid)
    }

    func testValidateBirthYear_TooOld() {
        let result = Validators.validateBirthYear("1800", minYear: 1900)
        XCTAssertFalse(result.isValid)
    }

    func testValidateBirthYear_Empty() {
        let result = Validators.validateBirthYear("")
        XCTAssertTrue(result.isValid) // Empty is valid (optional field)
    }

    // MARK: - ValidationResult Tests

    func testValidationResult_IsValid() {
        XCTAssertTrue(ValidationResult.valid.isValid)
        XCTAssertFalse(ValidationResult.invalid("error").isValid)
    }

    func testValidationResult_ErrorMessage() {
        XCTAssertNil(ValidationResult.valid.errorMessage)
        XCTAssertEqual(ValidationResult.invalid("some error").errorMessage, "some error")
    }

    // MARK: - String Extensions Tests

    func testStringIsNotEmpty_NonEmpty() {
        XCTAssertTrue("hello".isNotEmpty)
    }

    func testStringIsNotEmpty_WhitespaceOnly() {
        XCTAssertFalse("   ".isNotEmpty)
    }

    func testStringIsNotEmpty_Empty() {
        XCTAssertFalse("".isNotEmpty)
    }

    func testStringTrimmed() {
        XCTAssertEqual("  hello  ".trimmed, "hello")
    }

    // MARK: - Int Extensions Tests

    func testOrdinalSuffix_First() {
        XCTAssertEqual(1.ordinalSuffix, "st")
        XCTAssertEqual(1.ordinalString, "1st")
    }

    func testOrdinalSuffix_Second() {
        XCTAssertEqual(2.ordinalSuffix, "nd")
    }

    func testOrdinalSuffix_Third() {
        XCTAssertEqual(3.ordinalSuffix, "rd")
    }

    func testOrdinalSuffix_Fourth() {
        XCTAssertEqual(4.ordinalSuffix, "th")
    }

    func testOrdinalSuffix_Eleventh() {
        XCTAssertEqual(11.ordinalSuffix, "th")
        XCTAssertEqual(12.ordinalSuffix, "th")
        XCTAssertEqual(13.ordinalSuffix, "th")
    }

    func testOrdinalSuffix_TwentyFirst() {
        XCTAssertEqual(21.ordinalSuffix, "st")
    }

    // MARK: - TimeProvider Tests

    func testSystemTimeProvider_ReturnsCurrentDate() {
        let provider = SystemTimeProvider()
        let before = Date()
        let now = provider.now
        let after = Date()
        XCTAssertGreaterThanOrEqual(now, before)
        XCTAssertLessThanOrEqual(now, after)
    }

    // MARK: - BaseViewModel Tests

    func testBaseViewModel_InitialState() {
        let viewModel = BaseViewModel()
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
        XCTAssertFalse(viewModel.canRetry)
    }

    func testBaseViewModel_HandleError_SetsError() {
        let viewModel = BaseViewModel()
        let error = NSError(domain: "test", code: 1)
        viewModel.handleError(error, context: "test_context")
        XCTAssertNotNil(viewModel.error)
        XCTAssertFalse(viewModel.isLoading)
    }

    func testBaseViewModel_HandleError_CancellationError_DoesNotSetError() {
        let viewModel = BaseViewModel()
        viewModel.handleError(CancellationError(), context: "test")
        XCTAssertNil(viewModel.error)
    }

    func testBaseViewModel_ClearError() {
        let viewModel = BaseViewModel()
        let error = NSError(domain: "test", code: 1)
        viewModel.handleError(error, context: "test")
        viewModel.clearError()
        XCTAssertNil(viewModel.error)
        XCTAssertFalse(viewModel.canRetry)
    }

    func testBaseViewModel_HandleError_CallsErrorRecorder() {
        let recorder = MockErrorRecorder()
        let viewModel = BaseViewModel(errorRecorder: recorder)
        let error = NSError(domain: "test", code: 1)
        viewModel.handleError(error, context: "my_context")
        XCTAssertEqual(recorder.recordedContext, "my_context")
    }

    func testBaseViewModel_HandleError_RetryableError() {
        let viewModel = BaseViewModel()
        let retryableError = MockRetryableError(isRetryable: true)
        viewModel.handleError(retryableError, context: "test")
        XCTAssertTrue(viewModel.canRetry)
    }

    func testBaseViewModel_HandleError_NonRetryableError() {
        let viewModel = BaseViewModel()
        let nonRetryableError = MockRetryableError(isRetryable: false)
        viewModel.handleError(nonRetryableError, context: "test")
        XCTAssertFalse(viewModel.canRetry)
    }

    func testBaseViewModel_ValidationError_EmptyValue_ReturnsNil() {
        let viewModel = BaseViewModel()
        let result = viewModel.validationError(for: "", using: Validators.validateEmail)
        XCTAssertNil(result)
    }

    func testBaseViewModel_ValidationError_InvalidValue_ReturnsMessage() {
        let viewModel = BaseViewModel()
        let result = viewModel.validationError(for: "invalid-email", using: Validators.validateEmail)
        XCTAssertNotNil(result)
    }

    // MARK: - KeychainStorage Tests

    func testKeychainStorage_SaveAndRetrieve() throws {
        let storage = KeychainStorage(serviceName: "com.sharedkit.tests.\(UUID().uuidString)")
        let key = "test_key"
        let value = "test_value"

        try storage.save(value, forKey: key)
        let retrieved = try storage.retrieve(forKey: key)
        XCTAssertEqual(retrieved, value)

        // Cleanup
        try storage.deleteAll()
    }

    func testKeychainStorage_Delete() throws {
        let storage = KeychainStorage(serviceName: "com.sharedkit.tests.\(UUID().uuidString)")
        let key = "test_key"

        try storage.save("value", forKey: key)
        try storage.delete(forKey: key)
        let retrieved = try storage.retrieve(forKey: key)
        XCTAssertNil(retrieved)
    }

    func testKeychainStorage_RetrieveNonExistent_ReturnsNil() throws {
        let storage = KeychainStorage(serviceName: "com.sharedkit.tests.\(UUID().uuidString)")
        let retrieved = try storage.retrieve(forKey: "nonexistent_key")
        XCTAssertNil(retrieved)
    }

    // MARK: - ScrollPositionData Tests

    func testScrollPositionData_InitWithItemId() {
        let data = ScrollPositionData(itemId: 42)
        XCTAssertEqual(data.itemId, 42)
        XCTAssertNil(data.offsetY)
    }

    func testScrollPositionData_InitWithOffset() {
        let data = ScrollPositionData(offsetY: 100.0)
        XCTAssertNil(data.itemId)
        XCTAssertEqual(data.offsetY, 100.0)
    }
}

// MARK: - Test Helpers

private final class MockErrorRecorder: ErrorRecorder {
    var recordedContext: String?
    var recordedError: Error?

    func recordError(_ error: Error, context: String) {
        recordedError = error
        recordedContext = context
    }
}

private struct MockRetryableError: RetryableError {
    let isRetryable: Bool

    var errorDescription: String? {
        "Mock retryable error"
    }
}
