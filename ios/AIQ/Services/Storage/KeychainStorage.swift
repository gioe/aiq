import Foundation
import Security

/// Keychain storage implementation for secure data persistence
class KeychainStorage: SecureStorageProtocol {
    static let shared = KeychainStorage()

    private let serviceName: String

    init(serviceName: String = Bundle.main.bundleIdentifier ?? "com.aiq.app") {
        self.serviceName = serviceName
    }

    func save(_ value: String, forKey key: String) throws {
        guard let data = value.data(using: .utf8) else {
            throw KeychainError.encodingFailed
        }

        // Delete any existing item first
        try? delete(forKey: key)

        // Create query dictionary
        // Using kSecAttrAccessibleWhenUnlockedThisDeviceOnly for maximum security
        // - Data only accessible when device is unlocked
        // - Data not included in backups or migrations
        // - Data tied to this device only
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        // Add item to keychain
        let status = SecItemAdd(query as CFDictionary, nil)

        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status: status)
        }
    }

    func retrieve(forKey key: String) throws -> String? {
        // Create query dictionary
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        // Retrieve item from keychain
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        switch status {
        case errSecSuccess:
            guard let data = result as? Data,
                  let string = String(data: data, encoding: .utf8)
            else {
                throw KeychainError.decodingFailed
            }
            return string

        case errSecItemNotFound:
            return nil

        default:
            throw KeychainError.retrievalFailed(status: status)
        }
    }

    func delete(forKey key: String) throws {
        // Create query dictionary
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key
        ]

        // Delete item from keychain
        let status = SecItemDelete(query as CFDictionary)

        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.deletionFailed(status: status)
        }
    }

    func deleteAll() throws {
        // Create query dictionary for all items
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName
        ]

        // Delete all items
        let status = SecItemDelete(query as CFDictionary)

        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.deletionFailed(status: status)
        }
    }
}

/// Keychain-specific errors
enum KeychainError: Error, LocalizedError {
    case encodingFailed
    case decodingFailed
    case saveFailed(status: OSStatus)
    case retrievalFailed(status: OSStatus)
    case deletionFailed(status: OSStatus)

    var errorDescription: String? {
        switch self {
        case .encodingFailed:
            "Failed to encode data for keychain storage"
        case .decodingFailed:
            "Failed to decode data from keychain"
        case let .saveFailed(status):
            "Failed to save to keychain (status: \(status))"
        case let .retrievalFailed(status):
            "Failed to retrieve from keychain (status: \(status))"
        case let .deletionFailed(status):
            "Failed to delete from keychain (status: \(status))"
        }
    }
}
