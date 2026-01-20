import Combine
import Foundation

#if DEBUG

    /// Mock BiometricAuthManager for UI tests and previews
    ///
    /// This mock provides configurable biometric authentication behavior
    /// without requiring actual Face ID or Touch ID hardware.
    ///
    /// ## Configuration
    ///
    /// Configure the mock for different test scenarios:
    /// ```swift
    /// let mock = UITestMockBiometricAuthManager()
    ///
    /// // Simulate Face ID available
    /// mock.mockBiometricType = .faceID
    /// mock.mockBiometricAvailable = true
    ///
    /// // Simulate authentication failure
    /// mock.shouldFailAuthentication = true
    /// mock.authenticationError = .userCancelled
    /// ```
    @MainActor
    final class UITestMockBiometricAuthManager: BiometricAuthManagerProtocol {
        // MARK: - Published Properties

        @Published private(set) var isBiometricAvailable: Bool = true
        @Published private(set) var biometricType: BiometricType = .faceID

        // MARK: - Publishers

        var isBiometricAvailablePublisher: Published<Bool>.Publisher {
            $isBiometricAvailable
        }

        var biometricTypePublisher: Published<BiometricType>.Publisher {
            $biometricType
        }

        // MARK: - Mock Configuration

        /// Set to true to simulate biometric being available
        var mockBiometricAvailable: Bool = true {
            didSet {
                isBiometricAvailable = mockBiometricAvailable
            }
        }

        /// The type of biometric to simulate
        var mockBiometricType: BiometricType = .faceID {
            didSet {
                biometricType = mockBiometricType
            }
        }

        /// Set to true to make authentication fail
        var shouldFailAuthentication: Bool = false

        /// The error to throw when authentication fails
        var authenticationError: BiometricAuthError = .userCancelled

        /// Simulated delay for authentication (in nanoseconds)
        var authenticationDelay: UInt64 = 100_000_000 // 0.1 seconds

        // MARK: - Call Tracking

        /// Number of times authenticate was called
        private(set) var authenticateCallCount: Int = 0

        /// Number of times authenticateWithPasscodeFallback was called
        private(set) var authenticateWithFallbackCallCount: Int = 0

        /// Number of times refreshBiometricStatus was called
        private(set) var refreshStatusCallCount: Int = 0

        /// The last reason passed to authenticate
        private(set) var lastAuthenticationReason: String?

        // MARK: - Initialization

        init() {}

        // MARK: - Protocol Methods

        func authenticate(reason: String) async throws {
            authenticateCallCount += 1
            lastAuthenticationReason = reason

            // Simulate processing time
            try await Task.sleep(nanoseconds: authenticationDelay)

            if shouldFailAuthentication {
                throw authenticationError
            }
        }

        func authenticateWithPasscodeFallback(reason: String) async throws {
            authenticateWithFallbackCallCount += 1
            lastAuthenticationReason = reason

            // Simulate processing time
            try await Task.sleep(nanoseconds: authenticationDelay)

            if shouldFailAuthentication {
                throw authenticationError
            }
        }

        func refreshBiometricStatus() {
            refreshStatusCallCount += 1
            // In mock, values are set via mockBiometricAvailable and mockBiometricType
        }

        // MARK: - Test Helpers

        /// Reset all tracking state for test isolation
        func reset() {
            authenticateCallCount = 0
            authenticateWithFallbackCallCount = 0
            refreshStatusCallCount = 0
            lastAuthenticationReason = nil
            shouldFailAuthentication = false
            authenticationError = .userCancelled
            mockBiometricAvailable = true
            mockBiometricType = .faceID
        }

        /// Configure for a specific test scenario
        func configureForScenario(_ scenario: BiometricMockScenario) {
            switch scenario {
            case .faceIDAvailable:
                mockBiometricAvailable = true
                mockBiometricType = .faceID
                shouldFailAuthentication = false

            case .touchIDAvailable:
                mockBiometricAvailable = true
                mockBiometricType = .touchID
                shouldFailAuthentication = false

            case .biometricNotAvailable:
                mockBiometricAvailable = false
                mockBiometricType = .none
                shouldFailAuthentication = true
                authenticationError = .notAvailable

            case .biometricNotEnrolled:
                mockBiometricAvailable = false
                mockBiometricType = .none
                shouldFailAuthentication = true
                authenticationError = .notEnrolled

            case .biometricLockedOut:
                mockBiometricAvailable = true
                mockBiometricType = .faceID
                shouldFailAuthentication = true
                authenticationError = .lockedOut

            case .userCancels:
                mockBiometricAvailable = true
                mockBiometricType = .faceID
                shouldFailAuthentication = true
                authenticationError = .userCancelled

            case .authenticationFails:
                mockBiometricAvailable = true
                mockBiometricType = .faceID
                shouldFailAuthentication = true
                authenticationError = .authenticationFailed
            }
        }
    }

    /// Test scenarios for BiometricAuthManager mocking
    enum BiometricMockScenario {
        /// Face ID is available and works
        case faceIDAvailable
        /// Touch ID is available and works
        case touchIDAvailable
        /// Biometric is not available on device
        case biometricNotAvailable
        /// Biometric not enrolled (no Face ID/Touch ID set up)
        case biometricNotEnrolled
        /// Biometric is locked out due to failed attempts
        case biometricLockedOut
        /// User cancels the authentication prompt
        case userCancels
        /// Biometric authentication fails (no match)
        case authenticationFails
    }

#endif
