import Foundation

/// Protocol defining secure storage interface (typically backed by Keychain)
protocol SecureStorageProtocol {
    /// Save a string value for a given key
    func save(_ value: String, forKey key: String) throws

    /// Retrieve a string value for a given key
    func retrieve(forKey key: String) throws -> String?

    /// Delete a value for a given key
    func delete(forKey key: String) throws

    /// Delete all values
    func deleteAll() throws
}

/// Common keys used for secure storage
enum SecureStorageKey: String {
    case accessToken = "access_token"
    case refreshToken = "refresh_token"
    case userId = "user_id"
}
