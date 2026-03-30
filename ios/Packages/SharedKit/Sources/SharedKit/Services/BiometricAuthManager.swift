import Combine
import Foundation
import LocalAuthentication
import os

/// The type of biometric authentication available on the device
public enum BiometricType: Equatable {
    /// Face ID is available
    case faceID
    /// Touch ID is available
    case touchID
    /// No biometric authentication is available
    case none
}

/// Errors that can occur during biometric authentication
public enum BiometricAuthError: Error, LocalizedError, Equatable {
    /// Biometric authentication is not available on this device
    case notAvailable
    /// Biometric authentication has not been enrolled (no Face ID/Touch ID set up)
    case notEnrolled
    /// Biometric authentication is locked out due to too many failed attempts
    case lockedOut
    /// The user cancelled the authentication
    case userCancelled
    /// The user chose to enter their passcode instead
    case userFallback
    /// The system cancelled authentication (e.g., app went to background)
    case systemCancelled
    /// Authentication failed (biometric did not match)
    case authenticationFailed
    /// An unknown error occurred
    case unknown(String)

    public var errorDescription: String? {
        switch self {
        case .notAvailable:
            NSLocalizedString(
                "error.biometric.not.available",
                value: "Biometric authentication is not available on this device.",
                comment: "Biometric not available error"
            )
        case .notEnrolled:
            NSLocalizedString(
                "error.biometric.not.enrolled",
                value: "Biometric authentication has not been set up. Please enable Face ID or Touch ID in Settings.",
                comment: "Biometric not enrolled error"
            )
        case .lockedOut:
            NSLocalizedString(
                "error.biometric.locked.out",
                value: "Biometric authentication is temporarily locked. Please enter your passcode to re-enable it.",
                comment: "Biometric locked out error"
            )
        case .userCancelled:
            NSLocalizedString(
                "error.biometric.user.cancelled",
                value: "Authentication was cancelled.",
                comment: "User cancelled biometric auth"
            )
        case .userFallback:
            NSLocalizedString(
                "error.biometric.user.fallback",
                value: "User chose to enter passcode instead.",
                comment: "User chose passcode fallback"
            )
        case .systemCancelled:
            NSLocalizedString(
                "error.biometric.system.cancelled",
                value: "Authentication was cancelled by the system.",
                comment: "System cancelled biometric auth"
            )
        case .authenticationFailed:
            NSLocalizedString(
                "error.biometric.authentication.failed",
                value: "Biometric authentication failed. Please try again.",
                comment: "Biometric authentication failed"
            )
        case let .unknown(message):
            message
        }
    }

    public static func == (lhs: BiometricAuthError, rhs: BiometricAuthError) -> Bool {
        switch (lhs, rhs) {
        case (.notAvailable, .notAvailable),
             (.notEnrolled, .notEnrolled),
             (.lockedOut, .lockedOut),
             (.userCancelled, .userCancelled),
             (.userFallback, .userFallback),
             (.systemCancelled, .systemCancelled),
             (.authenticationFailed, .authenticationFailed):
            true
        case let (.unknown(lhsMessage), .unknown(rhsMessage)):
            lhsMessage == rhsMessage
        default:
            false
        }
    }
}

/// Protocol defining the public interface for biometric authentication
@MainActor
public protocol BiometricAuthManagerProtocol: AnyObject {
    /// Whether biometric authentication is available on this device
    var isBiometricAvailable: Bool { get }

    /// Publisher for biometric availability changes
    var isBiometricAvailablePublisher: Published<Bool>.Publisher { get }

    /// The type of biometric authentication available on this device
    var biometricType: BiometricType { get }

    /// Publisher for biometric type changes
    var biometricTypePublisher: Published<BiometricType>.Publisher { get }

    /// Authenticate using biometric (Face ID or Touch ID)
    func authenticate(reason: String) async throws

    /// Authenticate using biometric with automatic passcode fallback
    func authenticateWithPasscodeFallback(reason: String) async throws

    /// Check and update the current biometric availability status
    func refreshBiometricStatus()
}

/// Manager for biometric authentication (Face ID and Touch ID)
///
/// BiometricAuthManager provides Face ID and Touch ID authentication with
/// optional passcode fallback. It handles permission requests, tracks
/// availability status, and provides appropriate error handling.
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

    private let logger: Logger

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
    /// - Parameter subsystem: The subsystem identifier for logging. Defaults to the package bundle identifier.
    public init(subsystem: String = "com.sharedkit") {
        logger = Logger(subsystem: subsystem, category: "BiometricAuthManager")
        logger.debug("BiometricAuthManager initialized")
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
        logger.info("Attempting biometric authentication")

        let context = LAContext()
        context.localizedFallbackTitle = "" // Empty string hides the "Enter Passcode" button

        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            let biometricError = mapLAError(error)
            logger.error("Biometric not available: \(biometricError.localizedDescription)")
            throw biometricError
        }

        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: reason
            )

            if success {
                logger.info("Biometric authentication successful")
            } else {
                logger.warning("Biometric authentication returned false")
                throw BiometricAuthError.authenticationFailed
            }
        } catch let laError as LAError {
            let biometricError = mapLAError(laError)
            logger.error("Biometric authentication failed: \(biometricError.localizedDescription)")
            throw biometricError
        } catch {
            logger.error("Unknown authentication error: \(error.localizedDescription)")
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
        logger.info("Attempting biometric authentication with passcode fallback")

        let context = LAContext()

        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else {
            let biometricError = mapLAError(error)
            logger.error("Device authentication not available: \(biometricError.localizedDescription)")
            throw biometricError
        }

        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: reason
            )

            if success {
                logger.info("Authentication successful (biometric or passcode)")
            } else {
                logger.warning("Authentication returned false")
                throw BiometricAuthError.authenticationFailed
            }
        } catch let laError as LAError {
            let biometricError = mapLAError(laError)
            logger.error("Authentication failed: \(biometricError.localizedDescription)")
            throw biometricError
        } catch {
            logger.error("Unknown authentication error: \(error.localizedDescription)")
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
                logger.debug("Biometric available: Face ID")
            case .touchID:
                biometricType = .touchID
                logger.debug("Biometric available: Touch ID")
            case .opticID:
                // Optic ID (Vision Pro) is not supported in v1.0 as the package is designed
                // for iPhone/iPad form factors.
                biometricType = .none
                logger.debug("Optic ID detected - Vision Pro not supported in v1.0")
            @unknown default:
                biometricType = .none
                logger.debug("Unknown biometry type")
            }
        } else {
            biometricType = .none
            if let nsError = error {
                logger.debug("Biometric not available: \(nsError.localizedDescription)")
            }
        }
    }

    // MARK: - Internal Methods (for testing)

    /// Mapping from LAError codes to BiometricAuthError
    /// - Note: Public to enable unit testing from AIQTests, which cannot use @testable import on SharedKit
    public static let laErrorMapping: [LAError.Code: BiometricAuthError] = [
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
    /// - Note: Public to enable unit testing from AIQTests, which cannot use @testable import on SharedKit
    public func mapLAError(_ error: Error?) -> BiometricAuthError {
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
