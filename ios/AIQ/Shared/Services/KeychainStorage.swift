import AIQSharedKit
import Foundation

// Re-export SharedKit's KeychainStorage types for the AIQ app.
// Note: SecureStorageProtocol is now defined in AIQSharedKit.
typealias KeychainStorage = AIQSharedKit.KeychainStorage
typealias KeychainError = AIQSharedKit.KeychainError
