import Combine
import Foundation
import LocalAuthentication

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
///
/// BiometricAuthManagerProtocol provides a standardized interface for Face ID and Touch ID
/// authentication with fallback to device passcode. It enables dependency injection
/// for testing and is designed to work with the ServiceContainer.
///
/// Example Usage:
/// ```swift
/// let biometricManager = ServiceContainer.shared.resolve(BiometricAuthManagerProtocol.self)
///
/// if biometricManager.isBiometricAvailable {
///     do {
///         try await biometricManager.authenticate(reason: "Verify your identity")
///         // Authentication successful
///     } catch {
///         // Handle authentication error
///     }
/// }
/// ```
@MainActor
public protocol BiometricAuthManagerProtocol: AnyObject {
    /// Whether biometric authentication is available on this device
    ///
    /// Returns `true` if Face ID or Touch ID is available and enrolled,
    /// `false` otherwise.
    var isBiometricAvailable: Bool { get }

    /// Publisher for biometric availability changes
    var isBiometricAvailablePublisher: Published<Bool>.Publisher { get }

    /// The type of biometric authentication available on this device
    ///
    /// Returns `.faceID`, `.touchID`, or `.none` based on device capabilities.
    var biometricType: BiometricType { get }

    /// Publisher for biometric type changes
    var biometricTypePublisher: Published<BiometricType>.Publisher { get }

    /// Authenticate using biometric (Face ID or Touch ID)
    ///
    /// Prompts the user to authenticate using their enrolled biometric.
    /// If biometric fails or is unavailable, throws a `BiometricAuthError`.
    ///
    /// - Parameter reason: The reason displayed to the user explaining why authentication is needed
    /// - Throws: `BiometricAuthError` if authentication fails
    func authenticate(reason: String) async throws

    /// Authenticate using biometric with automatic passcode fallback
    ///
    /// Prompts the user to authenticate using their enrolled biometric.
    /// If biometric fails, automatically falls back to device passcode.
    ///
    /// - Parameter reason: The reason displayed to the user explaining why authentication is needed
    /// - Throws: `BiometricAuthError` if authentication fails (including passcode fallback)
    func authenticateWithPasscodeFallback(reason: String) async throws

    /// Check and update the current biometric availability status
    ///
    /// Call this to refresh the `isBiometricAvailable` and `biometricType` properties,
    /// for example when the app returns to the foreground.
    func refreshBiometricStatus()
}
