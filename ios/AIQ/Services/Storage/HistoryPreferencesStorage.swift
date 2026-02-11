import Foundation

/// Protocol for history preferences storage
protocol HistoryPreferencesStorageProtocol: AnyObject {
    var sortOrder: TestHistorySortOrder { get set }
    var dateFilter: TestHistoryDateFilter { get set }
}

/// UserDefaults-based implementation for storing history preferences
class HistoryPreferencesStorage: HistoryPreferencesStorageProtocol {
    private let userDefaults: UserDefaults
    private let sortOrderKey = "com.aiq.historySortOrder"
    private let dateFilterKey = "com.aiq.historyDateFilter"

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    var sortOrder: TestHistorySortOrder {
        get {
            guard let rawValue = userDefaults.string(forKey: sortOrderKey),
                  let value = TestHistorySortOrder(rawValue: rawValue) else {
                return .newestFirst
            }
            return value
        }
        set {
            userDefaults.set(newValue.rawValue, forKey: sortOrderKey)
        }
    }

    var dateFilter: TestHistoryDateFilter {
        get {
            guard let rawValue = userDefaults.string(forKey: dateFilterKey),
                  let value = TestHistoryDateFilter(rawValue: rawValue) else {
                return .all
            }
            return value
        }
        set {
            userDefaults.set(newValue.rawValue, forKey: dateFilterKey)
        }
    }
}
