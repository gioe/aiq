@testable import AIQ
import Foundation

/// Mock implementation of LocalAnswerStorageProtocol for testing
class MockLocalAnswerStorage: LocalAnswerStorageProtocol {
    // MARK: - Properties for Testing

    var saveProgressCalled = false
    var loadProgressCalled = false
    var clearProgressCalled = false
    var hasProgressCalled = false

    var lastSavedProgress: SavedTestProgress?
    var mockProgress: SavedTestProgress?
    var shouldThrowOnSave = false

    // MARK: - LocalAnswerStorageProtocol Implementation

    func saveProgress(_ progress: SavedTestProgress) throws {
        saveProgressCalled = true
        lastSavedProgress = progress

        if shouldThrowOnSave {
            throw NSError(
                domain: "MockLocalAnswerStorage",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Failed to save progress"]
            )
        }
    }

    func loadProgress() -> SavedTestProgress? {
        loadProgressCalled = true
        return mockProgress
    }

    func clearProgress() {
        clearProgressCalled = true
        mockProgress = nil
        lastSavedProgress = nil
    }

    func hasProgress() -> Bool {
        hasProgressCalled = true
        return mockProgress != nil
    }

    // MARK: - Helper Methods

    func reset() {
        saveProgressCalled = false
        loadProgressCalled = false
        clearProgressCalled = false
        hasProgressCalled = false
        lastSavedProgress = nil
        mockProgress = nil
        shouldThrowOnSave = false
    }
}
