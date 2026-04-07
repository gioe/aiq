import Foundation
import Security

/// Protocol defining secure storage interface (typically backed by Keychain)
public protocol SecureStorageProtocol {
    /// Save a string value for a given key
    func save(_ value: String, forKey key: String) throws

    /// Retrieve a string value for a given key
    func retrieve(forKey key: String) throws -> String?

    /// Delete a value for a given key
    func delete(forKey key: String) throws

    /// Delete all values
    func deleteAll() throws
}

/// Keychain storage implementation for secure data persistence
public class KeychainStorage: SecureStorageProtocol {
    private let serviceName: String

    public init(serviceName: String = Bundle.main.bundleIdentifier ?? "com.sharedkit") {
        self.serviceName = serviceName
    }

    public func save(_ value: String, forKey key: String) throws {
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

    public func retrieve(forKey key: String) throws -> String? {
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

    public func delete(forKey key: String) throws {
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

    public func deleteAll() throws {
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
public enum KeychainError: Error, LocalizedError {
    case encodingFailed
    case decodingFailed
    case saveFailed(status: OSStatus)
    case retrievalFailed(status: OSStatus)
    case deletionFailed(status: OSStatus)

    public var errorDescription: String? {
        switch self {
        case .encodingFailed:
            NSLocalizedString("error.keychain.encoding.failed", comment: "")
        case .decodingFailed:
            NSLocalizedString("error.keychain.decoding.failed", comment: "")
        case let .saveFailed(status):
            String(format: NSLocalizedString("error.keychain.save.failed", comment: ""), status)
        case let .retrievalFailed(status):
            String(format: NSLocalizedString("error.keychain.retrieval.failed", comment: ""), status)
        case let .deletionFailed(status):
            String(format: NSLocalizedString("error.keychain.deletion.failed", comment: ""), status)
        }
    }
}
