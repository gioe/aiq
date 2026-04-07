import AIQSharedKit
import Combine
import Foundation
import LocalAuthentication

// BiometricType, BiometricAuthError, and BiometricAuthManagerProtocol
// are now defined in AIQSharedKit. Re-export them for the AIQ app target.
typealias BiometricType = AIQSharedKit.BiometricType
typealias BiometricAuthError = AIQSharedKit.BiometricAuthError
typealias BiometricAuthManagerProtocol = AIQSharedKit.BiometricAuthManagerProtocol
