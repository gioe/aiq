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
    static let shared = LocalAnswerStorage()

    private let userDefaults: UserDefaults
    private let storageKey = "com.aiq.savedTestProgress"

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    func saveProgress(_ progress: SavedTestProgress) throws {
        let encoder = JSONEncoder()
        let data = try encoder.encode(progress)
        userDefaults.set(data, forKey: storageKey)
    }

    func loadProgress() -> SavedTestProgress? {
        guard let data = userDefaults.data(forKey: storageKey) else {
            return nil
        }

        let decoder = JSONDecoder()
        guard let progress = try? decoder.decode(SavedTestProgress.self, from: data) else {
            // Clear invalid data
            clearProgress()
            return nil
        }

        // Only return if still valid (within 24 hours)
        guard progress.isValid else {
            clearProgress()
            return nil
        }

        return progress
    }

    func clearProgress() {
        userDefaults.removeObject(forKey: storageKey)
    }

    func hasProgress() -> Bool {
        loadProgress() != nil
    }
}
