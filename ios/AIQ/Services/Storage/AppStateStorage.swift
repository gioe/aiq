import AIQSharedKit

// AppStateStorageProtocol and AppStateStorage are now provided by ios-libs SharedKit
// (re-exported via AIQSharedKit). This file adds the app-level shared singleton.

extension AppStateStorage {
    static let shared = AppStateStorage()
}
