@testable import AIQ
import AIQSharedKit

@MainActor
final class MockBiometricPreferenceStorage: BiometricPreferenceStorageProtocol {
    var isBiometricEnabled: Bool = false
}
