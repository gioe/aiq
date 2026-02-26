import Foundation

#if DEBUG

    /// In-memory biometric preference storage for UI tests
    ///
    /// Reads initial state from the `BIOMETRIC_LOCK_ENABLED` environment variable.
    /// Set `BIOMETRIC_LOCK_ENABLED=true` in launch environment to simulate biometric lock being enabled.
    final class UITestMockBiometricPreferenceStorage: BiometricPreferenceStorageProtocol {
        var isBiometricEnabled: Bool

        init() {
            isBiometricEnabled = ProcessInfo.processInfo.environment["BIOMETRIC_LOCK_ENABLED"] == "true"
        }
    }

#endif
