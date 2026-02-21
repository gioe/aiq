@testable import AIQ

@MainActor
final class MockBiometricPreferenceStorage: BiometricPreferenceStorageProtocol {
    var isBiometricEnabled: Bool = false
}
