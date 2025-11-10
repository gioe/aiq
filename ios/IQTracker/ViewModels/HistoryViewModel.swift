import Combine
import Foundation

/// Sort order for test history
enum TestHistorySortOrder: String, CaseIterable, Identifiable {
    case newestFirst = "Newest First"
    case oldestFirst = "Oldest First"

    var id: String { rawValue }
}

/// Date filter for test history
enum TestHistoryDateFilter: String, CaseIterable, Identifiable {
    case all = "All Time"
    case lastMonth = "Last 30 Days"
    case lastSixMonths = "Last 6 Months"
    case lastYear = "Last Year"

    var id: String { rawValue }

    /// Calculate the date threshold for this filter
    var dateThreshold: Date? {
        let calendar = Calendar.current
        let now = Date()

        switch self {
        case .all:
            return nil
        case .lastMonth:
            return calendar.date(byAdding: .day, value: -30, to: now)
        case .lastSixMonths:
            return calendar.date(byAdding: .month, value: -6, to: now)
        case .lastYear:
            return calendar.date(byAdding: .year, value: -1, to: now)
        }
    }
}

/// ViewModel for managing test history data and state
@MainActor
class HistoryViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var testHistory: [TestResult] = []
    @Published var isRefreshing: Bool = false
    @Published var sortOrder: TestHistorySortOrder = .newestFirst
    @Published var dateFilter: TestHistoryDateFilter = .all

    // MARK: - Private Properties

    private let apiClient: APIClientProtocol
    private var allTestHistory: [TestResult] = []

    // MARK: - Initialization

    init(apiClient: APIClientProtocol = APIClient.shared) {
        self.apiClient = apiClient
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch test history from API
    func fetchHistory() async {
        setLoading(true)
        clearError()

        do {
            let history: [TestResult] = try await apiClient.request(
                endpoint: .testHistory,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )

            allTestHistory = history
            applyFiltersAndSort()
            setLoading(false)

            #if DEBUG
                print("✅ Fetched \(history.count) test results")
            #endif
        } catch {
            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .fetchHistory
            )
            handleError(contextualError, retryOperation: { [weak self] in
                await self?.fetchHistory()
            })
        }
    }

    /// Apply current filters and sorting to test history
    func applyFiltersAndSort() {
        var filtered = allTestHistory

        // Apply date filter
        if let threshold = dateFilter.dateThreshold {
            filtered = filtered.filter { $0.completedAt >= threshold }
        }

        // Apply sort order
        switch sortOrder {
        case .newestFirst:
            filtered.sort { $0.completedAt > $1.completedAt }
        case .oldestFirst:
            filtered.sort { $0.completedAt < $1.completedAt }
        }

        testHistory = filtered
    }

    /// Update sort order and refresh display
    func setSortOrder(_ order: TestHistorySortOrder) {
        sortOrder = order
        applyFiltersAndSort()
    }

    /// Update date filter and refresh display
    func setDateFilter(_ filter: TestHistoryDateFilter) {
        dateFilter = filter
        applyFiltersAndSort()
    }

    /// Refresh history data (pull-to-refresh)
    func refreshHistory() async {
        isRefreshing = true
        await fetchHistory()
        isRefreshing = false
    }

    // MARK: - Computed Properties

    var hasHistory: Bool {
        !allTestHistory.isEmpty
    }

    /// Average IQ score across all tests (not filtered)
    var averageIQScore: Int? {
        guard !allTestHistory.isEmpty else { return nil }
        let sum = allTestHistory.reduce(0) { $0 + $1.iqScore }
        return sum / allTestHistory.count
    }

    /// Best IQ score across all tests (not filtered)
    var bestIQScore: Int? {
        allTestHistory.map(\.iqScore).max()
    }

    /// Total tests taken (not filtered)
    var totalTestsTaken: Int {
        allTestHistory.count
    }

    /// Number of filtered results
    var filteredResultsCount: Int {
        testHistory.count
    }
}
