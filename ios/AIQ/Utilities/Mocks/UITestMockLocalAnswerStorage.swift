import Foundation

#if DEBUG

    /// Mock local answer storage for UI tests
    ///
    /// This mock provides in-memory storage for test progress during UI tests,
    /// avoiding UserDefaults side effects.
    final class UITestMockLocalAnswerStorage: LocalAnswerStorageProtocol {
        private var savedProgress: SavedTestProgress?
        private let lock = NSLock()

        init() {}

        func saveProgress(_ progress: SavedTestProgress) throws {
            lock.lock()
            defer { lock.unlock() }
            savedProgress = progress
        }

        func loadProgress() -> SavedTestProgress? {
            lock.lock()
            defer { lock.unlock() }
            guard let progress = savedProgress, progress.isValid else {
                return nil
            }
            return progress
        }

        func clearProgress() {
            lock.lock()
            defer { lock.unlock() }
            savedProgress = nil
        }

        func hasProgress() -> Bool {
            loadProgress() != nil
        }
    }

#endif
