import Foundation

/// Protocol for local answer storage during test-taking
protocol LocalAnswerStorageProtocol {
    func saveProgress(_ progress: SavedTestProgress) throws
    func loadProgress() -> SavedTestProgress?
    func clearProgress()
    func hasProgress() -> Bool
}

/// UserDefaults-based implementation for storing test progress locally
class LocalAnswerStorage: LocalAnswerStorageProtocol {
    /// Shared singleton instance
    ///
    /// - Warning: Deprecated. Use `ServiceContainer.shared.resolve(LocalAnswerStorageProtocol.self)` instead.
    ///   ServiceContainer now owns the singleton instances directly, making this property redundant.
    @available(*, deprecated, message: "Use ServiceContainer.shared.resolve(LocalAnswerStorageProtocol.self) instead")
    static let shared = LocalAnswerStorage()

    private let userDefaults: UserDefaults
    private let storageKey = "com.aiq.savedTestProgress"
    /// Serial queue for thread-safe access to storage operations
    private let queue = DispatchQueue(label: "com.aiq.localStorage")

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    func saveProgress(_ progress: SavedTestProgress) throws {
        try queue.sync {
            let encoder = JSONEncoder()
            let data = try encoder.encode(progress)
            userDefaults.set(data, forKey: storageKey)
        }
    }

    func loadProgress() -> SavedTestProgress? {
        queue.sync {
            guard let data = userDefaults.data(forKey: storageKey) else {
                return nil
            }

            let decoder = JSONDecoder()
            guard let progress = try? decoder.decode(SavedTestProgress.self, from: data) else {
                // Clear invalid data
                internalClearProgress()
                return nil
            }

            // Only return if still valid (within 24 hours)
            guard progress.isValid else {
                internalClearProgress()
                return nil
            }

            return progress
        }
    }

    func clearProgress() {
        queue.sync {
            internalClearProgress()
        }
    }

    func hasProgress() -> Bool {
        loadProgress() != nil
    }

    /// Internal clear without queue synchronization (called from within queue.sync blocks)
    private func internalClearProgress() {
        userDefaults.removeObject(forKey: storageKey)
    }
}
