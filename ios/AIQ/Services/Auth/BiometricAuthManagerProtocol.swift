import Combine
import Foundation
import LocalAuthentication
import SharedKit

// BiometricType, BiometricAuthError, and BiometricAuthManagerProtocol
// are now defined in SharedKit. Re-export them for the AIQ app target.
typealias BiometricType = SharedKit.BiometricType
typealias BiometricAuthError = SharedKit.BiometricAuthError
typealias BiometricAuthManagerProtocol = SharedKit.BiometricAuthManagerProtocol
