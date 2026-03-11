import Foundation
import SharedKit

/// SecureStorageProtocol is now defined in SharedKit.
/// Re-export for the AIQ app target.
typealias SecureStorageProtocol = SharedKit.SecureStorageProtocol

/// Common keys used for secure storage
enum SecureStorageKey: String {
    case accessToken = "access_token"
    case refreshToken = "refresh_token"
    case userId = "user_id"
}
