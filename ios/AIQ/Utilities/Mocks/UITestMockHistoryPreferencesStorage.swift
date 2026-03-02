import Foundation

#if DEBUG

    /// Mock HistoryPreferencesStorage for UI tests
    ///
    /// This mock provides simple in-memory storage for history preferences
    /// (sort order and date filter) during UI testing. It does not persist
    /// preferences to UserDefaults, ensuring test isolation.
    final class UITestMockHistoryPreferencesStorage: HistoryPreferencesStorageProtocol {
        var sortOrder: TestHistorySortOrder = .newestFirst
        var dateFilter: TestHistoryDateFilter = .all
    }

#endif
