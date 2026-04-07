import AIQSharedKit
import Foundation

/// SecureStorageProtocol is now defined in AIQSharedKit.
/// Re-export for the AIQ app target.
typealias SecureStorageProtocol = AIQSharedKit.SecureStorageProtocol

/// Common keys used for secure storage
enum SecureStorageKey: String {
    case accessToken = "access_token"
    case refreshToken = "refresh_token"
    case userId = "user_id"
}
