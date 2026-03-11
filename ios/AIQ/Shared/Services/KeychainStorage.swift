import Foundation
import SharedKit

// Re-export SharedKit's KeychainStorage types for the AIQ app.
// Note: SecureStorageProtocol is now defined in SharedKit.
typealias KeychainStorage = SharedKit.KeychainStorage
typealias KeychainError = SharedKit.KeychainError
