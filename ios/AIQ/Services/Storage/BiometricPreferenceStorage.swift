import Foundation

/// Protocol for storing the user's biometric authentication preference
protocol BiometricPreferenceStorageProtocol: AnyObject {
    var isBiometricEnabled: Bool { get set }
}

/// Keychain-backed storage for biometric authentication preference
///
/// Stores the user's choice to enable/disable biometric login securely in the Keychain.
class BiometricPreferenceStorage: BiometricPreferenceStorageProtocol {
    private let secureStorage: SecureStorageProtocol
    private let key = "biometric_auth_enabled"

    init(secureStorage: SecureStorageProtocol) {
        self.secureStorage = secureStorage
    }

    var isBiometricEnabled: Bool {
        get {
            guard let value = try? secureStorage.retrieve(forKey: key) else { return false }
            return value == "true"
        }
        set {
            try? secureStorage.save(newValue ? "true" : "false", forKey: key)
        }
    }
}
