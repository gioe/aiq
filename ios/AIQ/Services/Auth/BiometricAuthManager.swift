import Combine
import Foundation
import LocalAuthentication
import os

/// Manager for biometric authentication (Face ID and Touch ID)
///
/// BiometricAuthManager provides Face ID and Touch ID authentication with
/// optional passcode fallback. It handles permission requests, tracks
/// availability status, and provides appropriate error handling.
///
/// ## Architecture
///
/// BiometricAuthManager is designed to integrate with the ServiceContainer
/// dependency injection system. It is registered in ServiceConfiguration
/// and can be resolved via:
///
/// ```swift
/// let biometricManager = ServiceContainer.shared.resolve(BiometricAuthManagerProtocol.self)
/// ```
///
/// ## Thread Safety
///
/// BiometricAuthManager is marked `@MainActor` to ensure all property access
/// and method calls occur on the main thread, which is required for UI updates
/// when using `@Published` properties with SwiftUI.
///
/// ## Error Handling
///
/// Authentication errors are mapped to `BiometricAuthError` for consistent
/// error handling. The manager distinguishes between:
/// - Device capability issues (not available, not enrolled)
/// - User actions (cancelled, chose passcode)
/// - System events (app backgrounded)
/// - Authentication failures (biometric mismatch)
@MainActor
public class BiometricAuthManager: BiometricAuthManagerProtocol {
    // MARK: - Logger

    private static let logger = Logger(subsystem: "com.aiq.app", category: "BiometricAuthManager")

    // MARK: - Published Properties

    /// Whether biometric authentication is currently available
    @Published public private(set) var isBiometricAvailable: Bool = false

    /// The type of biometric available on this device
    @Published public private(set) var biometricType: BiometricType = .none

    // MARK: - Publishers

    public var isBiometricAvailablePublisher: Published<Bool>.Publisher {
        $isBiometricAvailable
    }

    public var biometricTypePublisher: Published<BiometricType>.Publisher {
        $biometricType
    }

    // MARK: - Initialization

    /// Initialize the biometric authentication manager
    ///
    /// Automatically checks biometric availability on initialization.
    public init() {
        Self.logger.debug("BiometricAuthManager initialized")
        refreshBiometricStatus()
    }

    // MARK: - Public Methods

    /// Authenticate using biometric (Face ID or Touch ID)
    ///
    /// This method prompts the user to authenticate using their enrolled biometric.
    /// It does NOT fall back to passcode if biometric fails.
    ///
    /// - Parameter reason: The reason displayed to the user for authentication
    /// - Throws: `BiometricAuthError` if authentication fails or is unavailable
    public func authenticate(reason: String) async throws {
        Self.logger.info("Attempting biometric authentication")

        let context = LAContext()
        context.localizedFallbackTitle = "" // Empty string hides the "Enter Passcode" button

        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            let biometricError = mapLAError(error)
            Self.logger.error("Biometric not available: \(biometricError.localizedDescription)")
            throw biometricError
        }

        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: reason
            )

            if success {
                Self.logger.info("Biometric authentication successful")
            } else {
                Self.logger.warning("Biometric authentication returned false")
                throw BiometricAuthError.authenticationFailed
            }
        } catch let laError as LAError {
            let biometricError = mapLAError(laError)
            Self.logger.error("Biometric authentication failed: \(biometricError.localizedDescription)")
            throw biometricError
        } catch {
            Self.logger.error("Unknown authentication error: \(error.localizedDescription)")
            throw BiometricAuthError.unknown(error.localizedDescription)
        }
    }

    /// Authenticate using biometric with automatic passcode fallback
    ///
    /// This method prompts the user to authenticate using their enrolled biometric.
    /// If biometric fails or is unavailable, it automatically allows passcode entry.
    ///
    /// - Parameter reason: The reason displayed to the user for authentication
    /// - Throws: `BiometricAuthError` if authentication fails
    public func authenticateWithPasscodeFallback(reason: String) async throws {
        Self.logger.info("Attempting biometric authentication with passcode fallback")

        let context = LAContext()

        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else {
            let biometricError = mapLAError(error)
            Self.logger.error("Device authentication not available: \(biometricError.localizedDescription)")
            throw biometricError
        }

        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: reason
            )

            if success {
                Self.logger.info("Authentication successful (biometric or passcode)")
            } else {
                Self.logger.warning("Authentication returned false")
                throw BiometricAuthError.authenticationFailed
            }
        } catch let laError as LAError {
            let biometricError = mapLAError(laError)
            Self.logger.error("Authentication failed: \(biometricError.localizedDescription)")
            throw biometricError
        } catch {
            Self.logger.error("Unknown authentication error: \(error.localizedDescription)")
            throw BiometricAuthError.unknown(error.localizedDescription)
        }
    }

    /// Refresh the current biometric availability status
    ///
    /// Updates `isBiometricAvailable` and `biometricType` based on current device state.
    /// Call this when the app returns to foreground to detect any changes
    /// (e.g., user enrolled Face ID while app was backgrounded).
    public func refreshBiometricStatus() {
        let context = LAContext()
        var error: NSError?

        let canEvaluate = context.canEvaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            error: &error
        )

        isBiometricAvailable = canEvaluate

        if canEvaluate {
            switch context.biometryType {
            case .faceID:
                biometricType = .faceID
                Self.logger.debug("Biometric available: Face ID")
            case .touchID:
                biometricType = .touchID
                Self.logger.debug("Biometric available: Touch ID")
            case .opticID:
                // Treat Optic ID (Vision Pro) as not available for now
                biometricType = .none
                Self.logger.debug("Optic ID detected, treating as not available")
            @unknown default:
                biometricType = .none
                Self.logger.debug("Unknown biometry type")
            }
        } else {
            biometricType = .none
            if let nsError = error {
                Self.logger.debug("Biometric not available: \(nsError.localizedDescription)")
            }
        }
    }

    // MARK: - Private Methods

    /// Mapping from LAError codes to BiometricAuthError
    private static let laErrorMapping: [LAError.Code: BiometricAuthError] = [
        .biometryNotAvailable: .notAvailable,
        .biometryNotEnrolled: .notEnrolled,
        .biometryLockout: .lockedOut,
        .userCancel: .userCancelled,
        .userFallback: .userFallback,
        .systemCancel: .systemCancelled,
        .authenticationFailed: .authenticationFailed,
        .appCancel: .systemCancelled,
        .passcodeNotSet: .notAvailable
    ]

    /// Map LocalAuthentication errors to BiometricAuthError
    private func mapLAError(_ error: Error?) -> BiometricAuthError {
        guard let laError = error as? LAError else {
            if let nsError = error as NSError? {
                return BiometricAuthError.unknown(nsError.localizedDescription)
            }
            return BiometricAuthError.notAvailable
        }

        // Use dictionary lookup for most cases
        if let mappedError = Self.laErrorMapping[laError.code] {
            return mappedError
        }

        // Handle special cases that need custom messages
        switch laError.code {
        case .invalidContext:
            return .unknown("Authentication context is invalid")
        case .notInteractive:
            return .unknown("Authentication requires user interaction")
        default:
            return .unknown(laError.localizedDescription)
        }
    }
}
