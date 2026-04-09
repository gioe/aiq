import AIQAPIClientCore
import AIQSharedKit
import Combine
import Foundation

/// Sort order for test history
enum TestHistorySortOrder: String, CaseIterable, Identifiable {
    case newestFirst = "Newest First"
    case oldestFirst = "Oldest First"

    var id: String {
        rawValue
    }
}

/// Date filter for test history
enum TestHistoryDateFilter: String, CaseIterable, Identifiable {
    case all = "All Time"
    case lastMonth = "Last 30 Days"
    case lastSixMonths = "Last 6 Months"
    case lastYear = "Last Year"

    var id: String {
        rawValue
    }

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

    /// Sort order with persistence across app launches.
    /// Defaults to .newestFirst on first launch or if stored value is invalid.
    @Published var sortOrder: TestHistorySortOrder = .newestFirst

    /// Date filter with persistence across app launches.
    /// Defaults to .all on first launch or if stored value is invalid.
    @Published var dateFilter: TestHistoryDateFilter = .all

    /// AI model benchmark data for chart reference lines
    @Published private(set) var benchmarkModels: [Components.Schemas.ModelSummary] = []

    // MARK: - Pagination State

    /// Whether there are more results to load from the server
    @Published private(set) var hasMore: Bool = false

    /// Whether we're currently loading more results
    @Published private(set) var isLoadingMore: Bool = false

    /// Total number of test results on the server
    @Published private(set) var totalCount: Int = 0

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol
    private let preferencesStorage: HistoryPreferencesStorageProtocol
    private var allTestHistory: [TestResult] = []
    private var cachedInsights: PerformanceInsights?

    /// Current offset for pagination
    private var currentOffset: Int = 0

    /// Page size for API requests
    private let pageSize: Int = Constants.Pagination.historyPageSize

    // MARK: - Initialization

    init(apiService: OpenAPIServiceProtocol, preferencesStorage: HistoryPreferencesStorageProtocol) {
        self.apiService = apiService
        self.preferencesStorage = preferencesStorage
        super.init()
        // Load stored preferences after initialization
        sortOrder = preferencesStorage.sortOrder
        dateFilter = preferencesStorage.dateFilter
    }

    // MARK: - Public Methods

    /// Fetch test history from API (with caching)
    /// - Parameters:
    ///   - forceRefresh: If true, bypass cache and fetch from API
    ///   - showLoadingIndicator: If false, skip `setLoading` calls so the system
    ///     pull-to-refresh spinner handles UI feedback and the ScrollView is not
    ///     destroyed mid-flight (which would cancel the `.refreshable` task with
    ///     NSURLErrorDomain Code=-999).
    func fetchHistory(forceRefresh: Bool = false, showLoadingIndicator: Bool = true) async {
        if showLoadingIndicator { setLoading(true) }
        clearError()
        currentOffset = 0

        // Try to get from cache first if not forcing refresh
        if !forceRefresh, let cached = await loadFromCache() {
            updateState(with: cached, fromCache: true)
            return
        }

        do {
            let response = try await fetchFromAPI()
            await cacheResults(response.results)
            updateState(with: response, fromCache: false)
        } catch is CancellationError {
            if showLoadingIndicator { setLoading(false) }
            return // view is gone; discard silently
        } catch {
            let contextualError = ContextualError(
                error: error as? APIError ?? .api(.unknown(message: error.localizedDescription)),
                operation: .fetchHistory
            )
            let historyCtx = CrashlyticsErrorRecorder.ErrorContext.fetchHistory.rawValue
            handleError(contextualError, context: historyCtx) { [weak self] in
                await self?.fetchHistory(forceRefresh: forceRefresh, showLoadingIndicator: showLoadingIndicator)
            }
        }
    }

    /// Fetch AI benchmark summary for chart reference lines.
    /// Failures are silently ignored — reference lines are supplemental.
    func fetchBenchmarks() async {
        do {
            let summary = try await apiService.getBenchmarkSummary()
            // Take top 3 models by mean IQ (already sorted descending from API)
            benchmarkModels = Array(summary.models.prefix(3))
        } catch {
            benchmarkModels = []
        }
    }

    // MARK: - Private Fetch Helpers

    private func loadFromCache() async -> [TestResult]? {
        await AppCache.shared.get(forKey: .testHistory)
    }

    private func fetchFromAPI() async throws -> PaginatedTestHistoryResponse {
        try await apiService.getTestHistory(limit: pageSize, offset: 0)
    }

    private func cacheResults(_ results: [TestResult]) async {
        await AppCache.shared.set(results, forKey: .testHistory)
    }

    private func updateState(with cached: [TestResult], fromCache _: Bool) {
        allTestHistory = cached
        cachedInsights = nil
        hasMore = false
        totalCount = cached.count
        applyFiltersAndSort()
        setLoading(false)
    }

    private func updateState(with response: PaginatedTestHistoryResponse, fromCache _: Bool) {
        allTestHistory = response.results
        cachedInsights = nil
        hasMore = response.hasMore
        totalCount = response.totalCount
        currentOffset = response.results.count
        applyFiltersAndSort()
        setLoading(false)
    }

    /// Load more test results from the next page
    func loadMore() async {
        // Guard against duplicate requests or when there's nothing more to load
        guard hasMore, !isLoadingMore, !isLoading else { return }

        isLoadingMore = true
        clearError()

        do {
            let paginatedResponse = try await apiService.getTestHistory(
                limit: pageSize,
                offset: currentOffset
            )

            let newResults = paginatedResponse.results

            // Append new results to existing history
            allTestHistory.append(contentsOf: newResults)

            // Update pagination state
            hasMore = paginatedResponse.hasMore
            totalCount = paginatedResponse.totalCount
            currentOffset += newResults.count

            // Update cache with all results
            await AppCache.shared.set(allTestHistory, forKey: .testHistory)

            cachedInsights = nil // Invalidate insights cache
            applyFiltersAndSort()
            isLoadingMore = false
        } catch is CancellationError {
            isLoadingMore = false
            return // view is gone; discard silently
        } catch {
            isLoadingMore = false
            let contextualError = ContextualError(
                error: error as? APIError ?? .api(.unknown(message: error.localizedDescription)),
                operation: .fetchHistory
            )
            let historyCtx = CrashlyticsErrorRecorder.ErrorContext.fetchHistory.rawValue
            handleError(contextualError, context: historyCtx) { [weak self] in
                await self?.loadMore()
            }
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
        preferencesStorage.sortOrder = order
        applyFiltersAndSort()
    }

    /// Update date filter and refresh display
    func setDateFilter(_ filter: TestHistoryDateFilter) {
        dateFilter = filter
        preferencesStorage.dateFilter = filter
        applyFiltersAndSort()
    }

    /// Refresh history data (pull-to-refresh)
    func refreshHistory() async {
        await withRefreshing {
            // Clear cache and force refresh
            await AppCache.shared.remove(forKey: .testHistory)
            // Pass showLoadingIndicator: false so the system pull-to-refresh spinner
            // handles UI feedback. Calling setLoading(true) here would swap the
            // ScrollView for LoadingView, destroying the refreshable context and
            // cancelling the in-flight network request (NSURLErrorDomain Code=-999).
            await self.fetchHistory(forceRefresh: true, showLoadingIndicator: false)
        }
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

    /// Performance insights calculated from all test history (cached for performance)
    var performanceInsights: PerformanceInsights? {
        guard !allTestHistory.isEmpty else {
            cachedInsights = nil
            return nil
        }

        // Return cached insights if available and data hasn't changed
        if let cached = cachedInsights {
            return cached
        }

        // Calculate new insights and cache
        let insights = PerformanceInsights(from: allTestHistory)
        cachedInsights = insights
        return insights
    }
}
