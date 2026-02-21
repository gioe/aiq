@testable import AIQ
import Combine
import Foundation

/// Mock implementation of BiometricAuthManagerProtocol for unit testing
@MainActor
final class MockBiometricAuthManager: BiometricAuthManagerProtocol {
    // MARK: - Published Properties

    @Published private(set) var isBiometricAvailable: Bool = false
    @Published private(set) var biometricType: BiometricType = .none

    // MARK: - Publishers

    var isBiometricAvailablePublisher: Published<Bool>.Publisher {
        $isBiometricAvailable
    }

    var biometricTypePublisher: Published<BiometricType>.Publisher {
        $biometricType
    }

    // MARK: - Mock Configuration

    /// Controls whether biometric is reported as available.
    /// Setting this updates the published `isBiometricAvailable` property.
    var mockIsBiometricAvailable: Bool = false {
        didSet { isBiometricAvailable = mockIsBiometricAvailable }
    }

    /// Controls which biometric type is reported.
    /// Setting this updates the published `biometricType` property.
    var mockBiometricType: BiometricType = .none {
        didSet { biometricType = mockBiometricType }
    }

    /// When true, `authenticate(reason:)` and `authenticateWithPasscodeFallback(reason:)` throw `authenticationError`.
    var shouldFailAuthentication: Bool = false

    /// The error thrown when `shouldFailAuthentication` is true.
    var authenticationError: BiometricAuthError = .userCancelled

    // MARK: - Call Tracking

    private(set) var authenticateCallCount: Int = 0
    private(set) var authenticateWithFallbackCallCount: Int = 0
    private(set) var refreshStatusCallCount: Int = 0
    private(set) var lastAuthenticationReason: String?

    // MARK: - Initialization

    init() {}

    // MARK: - Protocol Methods

    func authenticate(reason: String) async throws {
        authenticateCallCount += 1
        lastAuthenticationReason = reason
        if shouldFailAuthentication {
            throw authenticationError
        }
    }

    func authenticateWithPasscodeFallback(reason: String) async throws {
        authenticateWithFallbackCallCount += 1
        lastAuthenticationReason = reason
        if shouldFailAuthentication {
            throw authenticationError
        }
    }

    func refreshBiometricStatus() {
        refreshStatusCallCount += 1
    }

    // MARK: - Test Helpers

    /// Reset all tracking state and configuration for test isolation
    func reset() {
        mockIsBiometricAvailable = false
        mockBiometricType = .none
        shouldFailAuthentication = false
        authenticationError = .userCancelled
        authenticateCallCount = 0
        authenticateWithFallbackCallCount = 0
        refreshStatusCallCount = 0
        lastAuthenticationReason = nil
    }
}
