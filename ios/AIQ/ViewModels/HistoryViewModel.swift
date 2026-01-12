import Combine
import Foundation
import SwiftUI

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

    /// Sort order with persistence across app launches.
    /// Defaults to .newestFirst on first launch or if stored value is invalid.
    @AppStorage("com.aiq.historySortOrder") var sortOrder: TestHistorySortOrder = .newestFirst

    /// Date filter with persistence across app launches.
    /// Defaults to .all on first launch or if stored value is invalid.
    @AppStorage("com.aiq.historyDateFilter") var dateFilter: TestHistoryDateFilter = .all

    // MARK: - Pagination State

    /// Whether there are more results to load from the server
    @Published private(set) var hasMore: Bool = false

    /// Whether we're currently loading more results
    @Published private(set) var isLoadingMore: Bool = false

    /// Total number of test results on the server
    @Published private(set) var totalCount: Int = 0

    // MARK: - Private Properties

    private let apiClient: APIClientProtocol
    private var allTestHistory: [TestResult] = []
    private var cachedInsights: PerformanceInsights?

    /// Current offset for pagination
    private var currentOffset: Int = 0

    /// Page size for API requests
    private let pageSize: Int = Constants.Pagination.historyPageSize

    // MARK: - Initialization

    init(apiClient: APIClientProtocol) {
        self.apiClient = apiClient
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch test history from API (with caching)
    func fetchHistory(forceRefresh: Bool = false) async {
        setLoading(true)
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
        } catch {
            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .fetchHistory
            )
            handleError(contextualError, context: .fetchHistory) { [weak self] in
                await self?.fetchHistory(forceRefresh: forceRefresh)
            }
        }
    }

    // MARK: - Private Fetch Helpers

    private func loadFromCache() async -> [TestResult]? {
        await DataCache.shared.get(forKey: DataCache.Key.testHistory)
    }

    private func fetchFromAPI() async throws -> PaginatedTestHistoryResponse {
        try await apiClient.request(
            endpoint: .testHistory(limit: pageSize, offset: 0),
            method: .get,
            body: nil as String?,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )
    }

    private func cacheResults(_ results: [TestResult]) async {
        await DataCache.shared.set(results, forKey: DataCache.Key.testHistory)
    }

    private func updateState(with cached: [TestResult], fromCache _: Bool) {
        allTestHistory = cached
        cachedInsights = nil
        hasMore = false
        totalCount = cached.count
        applyFiltersAndSort()
        setLoading(false)

        #if DEBUG
            print("✅ Loaded \(cached.count) test results from cache")
        #endif
    }

    private func updateState(with response: PaginatedTestHistoryResponse, fromCache _: Bool) {
        allTestHistory = response.results
        cachedInsights = nil
        hasMore = response.hasMore
        totalCount = response.totalCount
        currentOffset = response.results.count
        applyFiltersAndSort()
        setLoading(false)

        #if DEBUG
            print("✅ Fetched \(response.results.count) of \(totalCount) from API (hasMore: \(hasMore))")
        #endif
    }

    /// Load more test results from the next page
    func loadMore() async {
        // Guard against duplicate requests or when there's nothing more to load
        guard hasMore, !isLoadingMore, !isLoading else { return }

        isLoadingMore = true
        clearError()

        do {
            let paginatedResponse: PaginatedTestHistoryResponse = try await apiClient.request(
                endpoint: .testHistory(limit: pageSize, offset: currentOffset),
                method: .get,
                body: nil as String?,
                requiresAuth: true,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )

            let newResults = paginatedResponse.results

            // Append new results to existing history
            allTestHistory.append(contentsOf: newResults)

            // Update pagination state
            hasMore = paginatedResponse.hasMore
            totalCount = paginatedResponse.totalCount
            currentOffset += newResults.count

            // Update cache with all results
            await DataCache.shared.set(allTestHistory, forKey: DataCache.Key.testHistory)

            cachedInsights = nil // Invalidate insights cache
            applyFiltersAndSort()
            isLoadingMore = false

            #if DEBUG
                let loaded = allTestHistory.count
                print("✅ Loaded \(newResults.count) more results (total: \(loaded)/\(totalCount), hasMore: \(hasMore))")
            #endif
        } catch {
            isLoadingMore = false
            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .fetchHistory
            )
            handleError(contextualError, context: .fetchHistory) { [weak self] in
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
        // Reset pagination state
        currentOffset = 0
        hasMore = false
        // Clear cache and force refresh
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
        await fetchHistory(forceRefresh: true)
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
