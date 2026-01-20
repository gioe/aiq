@testable import AIQ
import LocalAuthentication
import XCTest

@MainActor
final class BiometricAuthManagerTests: XCTestCase {
    var sut: BiometricAuthManager!

    override func setUp() async throws {
        try await super.setUp()
        sut = BiometricAuthManager()
    }

    override func tearDown() {
        sut = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInit_CreatesValidInstance() {
        // Then
        XCTAssertNotNil(sut, "BiometricAuthManager should initialize without errors")
    }

    func testInit_RefreshesBiometricStatus() {
        // Then - biometricType should be set (even if to .none)
        // On simulator, this will likely be .none
        XCTAssertNotNil(sut.biometricType)
    }

    // MARK: - Protocol Conformance Tests

    func testConformsToProtocol() {
        // Given
        let manager: BiometricAuthManagerProtocol = sut

        // Then
        XCTAssertNotNil(manager, "BiometricAuthManager should conform to BiometricAuthManagerProtocol")
    }

    // MARK: - Publisher Tests

    func testIsBiometricAvailablePublisher_Exists() {
        // Given
        var receivedValues: [Bool] = []
        let cancellable = sut.isBiometricAvailablePublisher
            .sink { value in
                receivedValues.append(value)
            }

        // Then
        XCTAssertFalse(receivedValues.isEmpty, "Publisher should emit initial value")
        cancellable.cancel()
    }

    func testBiometricTypePublisher_Exists() {
        // Given
        var receivedValues: [BiometricType] = []
        let cancellable = sut.biometricTypePublisher
            .sink { value in
                receivedValues.append(value)
            }

        // Then
        XCTAssertFalse(receivedValues.isEmpty, "Publisher should emit initial value")
        cancellable.cancel()
    }

    // MARK: - RefreshBiometricStatus Tests

    func testRefreshBiometricStatus_DoesNotCrash() {
        // When/Then - should not crash
        sut.refreshBiometricStatus()
    }

    func testRefreshBiometricStatus_UpdatesProperties() {
        // Given
        let initialAvailable = sut.isBiometricAvailable
        let initialType = sut.biometricType

        // When
        sut.refreshBiometricStatus()

        // Then - values should be consistent (same or updated)
        // On simulator, both calls should return the same value
        XCTAssertEqual(sut.isBiometricAvailable, initialAvailable)
        XCTAssertEqual(sut.biometricType, initialType)
    }

    // MARK: - Error Mapping Tests

    func testMapLAError_BiometryNotAvailable_ReturnsNotAvailable() {
        // Given
        let laError = LAError(.biometryNotAvailable)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .notAvailable)
    }

    func testMapLAError_BiometryNotEnrolled_ReturnsNotEnrolled() {
        // Given
        let laError = LAError(.biometryNotEnrolled)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .notEnrolled)
    }

    func testMapLAError_BiometryLockout_ReturnsLockedOut() {
        // Given
        let laError = LAError(.biometryLockout)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .lockedOut)
    }

    func testMapLAError_UserCancel_ReturnsUserCancelled() {
        // Given
        let laError = LAError(.userCancel)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .userCancelled)
    }

    func testMapLAError_UserFallback_ReturnsUserFallback() {
        // Given
        let laError = LAError(.userFallback)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .userFallback)
    }

    func testMapLAError_SystemCancel_ReturnsSystemCancelled() {
        // Given
        let laError = LAError(.systemCancel)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .systemCancelled)
    }

    func testMapLAError_AuthenticationFailed_ReturnsAuthenticationFailed() {
        // Given
        let laError = LAError(.authenticationFailed)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .authenticationFailed)
    }

    func testMapLAError_AppCancel_ReturnsSystemCancelled() {
        // Given
        let laError = LAError(.appCancel)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .systemCancelled)
    }

    func testMapLAError_PasscodeNotSet_ReturnsNotAvailable() {
        // Given
        let laError = LAError(.passcodeNotSet)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .notAvailable)
    }

    func testMapLAError_InvalidContext_ReturnsUnknownWithMessage() {
        // Given
        let laError = LAError(.invalidContext)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .unknown("Authentication context is invalid"))
    }

    func testMapLAError_NotInteractive_ReturnsUnknownWithMessage() {
        // Given
        let laError = LAError(.notInteractive)

        // When
        let result = sut.mapLAError(laError)

        // Then
        XCTAssertEqual(result, .unknown("Authentication requires user interaction"))
    }

    func testMapLAError_NilError_ReturnsNotAvailable() {
        // Given
        let error: Error? = nil

        // When
        let result = sut.mapLAError(error)

        // Then
        XCTAssertEqual(result, .notAvailable)
    }

    func testMapLAError_NonLAError_ReturnsUnknownWithDescription() {
        // Given
        let nsError = NSError(domain: "TestDomain", code: 42, userInfo: [NSLocalizedDescriptionKey: "Test error"])

        // When
        let result = sut.mapLAError(nsError)

        // Then
        XCTAssertEqual(result, .unknown("Test error"))
    }

    func testLAErrorMapping_ContainsAllExpectedCodes() {
        // Given
        let expectedCodes: [LAError.Code] = [
            .biometryNotAvailable,
            .biometryNotEnrolled,
            .biometryLockout,
            .userCancel,
            .userFallback,
            .systemCancel,
            .authenticationFailed,
            .appCancel,
            .passcodeNotSet
        ]

        // Then
        for code in expectedCodes {
            XCTAssertNotNil(
                BiometricAuthManager.laErrorMapping[code],
                "laErrorMapping should contain mapping for \(code)"
            )
        }
    }

    // MARK: - BiometricType Tests

    func testBiometricType_AllCasesExist() {
        // Verify all expected biometric types exist
        let types: [BiometricType] = [
            .faceID,
            .touchID,
            .none
        ]

        // Then
        XCTAssertEqual(types.count, 3, "Should have 3 biometric types")
    }

    func testBiometricType_Equatable() {
        // Given
        let type1 = BiometricType.faceID
        let type2 = BiometricType.faceID
        let type3 = BiometricType.touchID

        // Then
        XCTAssertEqual(type1, type2)
        XCTAssertNotEqual(type1, type3)
    }

    // MARK: - BiometricAuthError Tests

    func testBiometricAuthError_AllCasesExist() {
        // Verify all expected error cases exist
        let errors: [BiometricAuthError] = [
            .notAvailable,
            .notEnrolled,
            .lockedOut,
            .userCancelled,
            .userFallback,
            .systemCancelled,
            .authenticationFailed,
            .unknown("test")
        ]

        // Then
        XCTAssertEqual(errors.count, 8, "Should have 8 error cases")
    }

    func testBiometricAuthError_NotAvailable_HasLocalizedDescription() {
        // Given
        let error = BiometricAuthError.notAvailable

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
    }

    func testBiometricAuthError_NotEnrolled_HasLocalizedDescription() {
        // Given
        let error = BiometricAuthError.notEnrolled

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
    }

    func testBiometricAuthError_LockedOut_HasLocalizedDescription() {
        // Given
        let error = BiometricAuthError.lockedOut

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
    }

    func testBiometricAuthError_UserCancelled_HasLocalizedDescription() {
        // Given
        let error = BiometricAuthError.userCancelled

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
    }

    func testBiometricAuthError_UserFallback_HasLocalizedDescription() {
        // Given
        let error = BiometricAuthError.userFallback

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
    }

    func testBiometricAuthError_SystemCancelled_HasLocalizedDescription() {
        // Given
        let error = BiometricAuthError.systemCancelled

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
    }

    func testBiometricAuthError_AuthenticationFailed_HasLocalizedDescription() {
        // Given
        let error = BiometricAuthError.authenticationFailed

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
    }

    func testBiometricAuthError_Unknown_HasLocalizedDescription() {
        // Given
        let message = "Custom error message"
        let error = BiometricAuthError.unknown(message)

        // Then
        XCTAssertEqual(error.errorDescription, message)
    }

    func testBiometricAuthError_Equatable() {
        // Given
        let error1 = BiometricAuthError.userCancelled
        let error2 = BiometricAuthError.userCancelled
        let error3 = BiometricAuthError.lockedOut

        // Then
        XCTAssertEqual(error1, error2)
        XCTAssertNotEqual(error1, error3)
    }

    func testBiometricAuthError_UnknownEquatable() {
        // Given
        let error1 = BiometricAuthError.unknown("test")
        let error2 = BiometricAuthError.unknown("test")
        let error3 = BiometricAuthError.unknown("different")

        // Then
        XCTAssertEqual(error1, error2)
        XCTAssertNotEqual(error1, error3)
    }

    // MARK: - Mock Tests

    func testMock_Init_DefaultsToFaceIDAvailable() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // Then
        XCTAssertTrue(mock.isBiometricAvailable)
        XCTAssertEqual(mock.biometricType, .faceID)
    }

    func testMock_Authenticate_TracksCallCount() async throws {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        try await mock.authenticate(reason: "Test reason")

        // Then
        XCTAssertEqual(mock.authenticateCallCount, 1)
        XCTAssertEqual(mock.lastAuthenticationReason, "Test reason")
    }

    func testMock_AuthenticateWithPasscodeFallback_TracksCallCount() async throws {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        try await mock.authenticateWithPasscodeFallback(reason: "Test fallback")

        // Then
        XCTAssertEqual(mock.authenticateWithFallbackCallCount, 1)
        XCTAssertEqual(mock.lastAuthenticationReason, "Test fallback")
    }

    func testMock_RefreshBiometricStatus_TracksCallCount() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.refreshBiometricStatus()
        mock.refreshBiometricStatus()

        // Then
        XCTAssertEqual(mock.refreshStatusCallCount, 2)
    }

    func testMock_ShouldFailAuthentication_ThrowsError() async {
        // Given
        let mock = UITestMockBiometricAuthManager()
        mock.shouldFailAuthentication = true
        mock.authenticationError = .userCancelled

        // When/Then
        do {
            try await mock.authenticate(reason: "Test")
            XCTFail("Should have thrown an error")
        } catch let error as BiometricAuthError {
            XCTAssertEqual(error, .userCancelled)
        } catch {
            XCTFail("Wrong error type: \(error)")
        }
    }

    func testMock_Reset_ClearsState() async throws {
        // Given
        let mock = UITestMockBiometricAuthManager()
        try await mock.authenticate(reason: "Test")
        mock.refreshBiometricStatus()

        // When
        mock.reset()

        // Then
        XCTAssertEqual(mock.authenticateCallCount, 0)
        XCTAssertEqual(mock.authenticateWithFallbackCallCount, 0)
        XCTAssertEqual(mock.refreshStatusCallCount, 0)
        XCTAssertNil(mock.lastAuthenticationReason)
        XCTAssertFalse(mock.shouldFailAuthentication)
        XCTAssertTrue(mock.mockBiometricAvailable)
        XCTAssertEqual(mock.mockBiometricType, .faceID)
    }

    // MARK: - Mock Scenario Tests

    func testMock_ConfigureForScenario_FaceIDAvailable() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.configureForScenario(.faceIDAvailable)

        // Then
        XCTAssertTrue(mock.isBiometricAvailable)
        XCTAssertEqual(mock.biometricType, .faceID)
        XCTAssertFalse(mock.shouldFailAuthentication)
    }

    func testMock_ConfigureForScenario_TouchIDAvailable() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.configureForScenario(.touchIDAvailable)

        // Then
        XCTAssertTrue(mock.isBiometricAvailable)
        XCTAssertEqual(mock.biometricType, .touchID)
        XCTAssertFalse(mock.shouldFailAuthentication)
    }

    func testMock_ConfigureForScenario_BiometricNotAvailable() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.configureForScenario(.biometricNotAvailable)

        // Then
        XCTAssertFalse(mock.isBiometricAvailable)
        XCTAssertEqual(mock.biometricType, .none)
        XCTAssertTrue(mock.shouldFailAuthentication)
        XCTAssertEqual(mock.authenticationError, .notAvailable)
    }

    func testMock_ConfigureForScenario_BiometricNotEnrolled() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.configureForScenario(.biometricNotEnrolled)

        // Then
        XCTAssertFalse(mock.isBiometricAvailable)
        XCTAssertEqual(mock.biometricType, .none)
        XCTAssertTrue(mock.shouldFailAuthentication)
        XCTAssertEqual(mock.authenticationError, .notEnrolled)
    }

    func testMock_ConfigureForScenario_BiometricLockedOut() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.configureForScenario(.biometricLockedOut)

        // Then
        XCTAssertTrue(mock.isBiometricAvailable)
        XCTAssertEqual(mock.biometricType, .faceID)
        XCTAssertTrue(mock.shouldFailAuthentication)
        XCTAssertEqual(mock.authenticationError, .lockedOut)
    }

    func testMock_ConfigureForScenario_UserCancels() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.configureForScenario(.userCancels)

        // Then
        XCTAssertTrue(mock.isBiometricAvailable)
        XCTAssertTrue(mock.shouldFailAuthentication)
        XCTAssertEqual(mock.authenticationError, .userCancelled)
    }

    func testMock_ConfigureForScenario_AuthenticationFails() {
        // Given
        let mock = UITestMockBiometricAuthManager()

        // When
        mock.configureForScenario(.authenticationFails)

        // Then
        XCTAssertTrue(mock.isBiometricAvailable)
        XCTAssertTrue(mock.shouldFailAuthentication)
        XCTAssertEqual(mock.authenticationError, .authenticationFailed)
    }

    // MARK: - Mock Publisher Tests

    func testMock_BiometricAvailablePublisher_UpdatesWhenMockValueChanges() {
        // Given
        let mock = UITestMockBiometricAuthManager()
        var receivedValues: [Bool] = []
        let cancellable = mock.isBiometricAvailablePublisher
            .sink { value in
                receivedValues.append(value)
            }

        // When
        mock.mockBiometricAvailable = false

        // Then
        XCTAssertTrue(receivedValues.contains(true), "Should have initial value")
        XCTAssertTrue(receivedValues.contains(false), "Should have updated value")
        cancellable.cancel()
    }

    func testMock_BiometricTypePublisher_UpdatesWhenMockValueChanges() {
        // Given
        let mock = UITestMockBiometricAuthManager()
        var receivedValues: [BiometricType] = []
        let cancellable = mock.biometricTypePublisher
            .sink { value in
                receivedValues.append(value)
            }

        // When
        mock.mockBiometricType = .touchID

        // Then
        XCTAssertTrue(receivedValues.contains(.faceID), "Should have initial value")
        XCTAssertTrue(receivedValues.contains(.touchID), "Should have updated value")
        cancellable.cancel()
    }
}
