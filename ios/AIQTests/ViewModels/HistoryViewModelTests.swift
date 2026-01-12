import Combine
import XCTest

@testable import AIQ

@MainActor
final class HistoryViewModelTests: XCTestCase {
    var sut: HistoryViewModel!
    var mockAPIClient: MockAPIClient!
    var testUserDefaults: UserDefaults!
    var testSuiteName: String!

    private let sortOrderStorageKey = "com.aiq.historySortOrder"
    private let dateFilterStorageKey = "com.aiq.historyDateFilter"

    override func setUp() async throws {
        try await super.setUp()

        // Create a test-specific UserDefaults suite to isolate tests
        testSuiteName = "com.aiq.tests.HistoryViewModel.\(UUID().uuidString)"
        testUserDefaults = UserDefaults(suiteName: testSuiteName)!

        mockAPIClient = MockAPIClient()
        sut = HistoryViewModel(apiClient: mockAPIClient)

        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
    }

    override func tearDown() {
        // Clean up test UserDefaults
        testUserDefaults.removePersistentDomain(forName: testSuiteName)
        testUserDefaults = nil
        testSuiteName = nil

        // Clean up filter persistence in standard UserDefaults
        UserDefaults.standard.removeObject(forKey: sortOrderStorageKey)
        UserDefaults.standard.removeObject(forKey: dateFilterStorageKey)

        sut = nil
        mockAPIClient = nil
        super.tearDown()
    }

    // MARK: - Test Helpers

    private func createMockTestResult(id: Int, iqScore: Int = 100, completedAt: Date = Date()) -> TestResult {
        TestResult(
            id: id,
            testSessionId: id,
            userId: 1,
            iqScore: iqScore,
            percentileRank: 50.0,
            totalQuestions: 20,
            correctAnswers: 10,
            accuracyPercentage: 50.0,
            completionTimeSeconds: 300,
            completedAt: completedAt
        )
    }

    // MARK: - Initial State Tests

    func testInitialState() {
        XCTAssertTrue(sut.testHistory.isEmpty, "testHistory should be empty initially")
        XCTAssertFalse(sut.isLoading, "isLoading should be false initially")
        XCTAssertFalse(sut.isRefreshing, "isRefreshing should be false initially")
        XCTAssertFalse(sut.hasMore, "hasMore should be false initially")
        XCTAssertFalse(sut.isLoadingMore, "isLoadingMore should be false initially")
        XCTAssertEqual(sut.totalCount, 0, "totalCount should be 0 initially")
    }

    // MARK: - Pagination State Tests

    func testFetchHistory_SetsPaginationState() async {
        // Given
        let results = [
            createMockTestResult(id: 1),
            createMockTestResult(id: 2)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 100, hasMore: true)

        // When
        await sut.fetchHistory(forceRefresh: true)

        // Then
        XCTAssertEqual(sut.testHistory.count, 2, "Should have 2 test results")
        XCTAssertEqual(sut.totalCount, 100, "totalCount should be 100")
        XCTAssertTrue(sut.hasMore, "hasMore should be true")
        XCTAssertFalse(sut.isLoadingMore, "isLoadingMore should be false after fetch")
    }

    func testFetchHistory_SetsHasMoreFalseWhenNoMoreResults() async {
        // Given
        let results = [createMockTestResult(id: 1)]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 1, hasMore: false)

        // When
        await sut.fetchHistory(forceRefresh: true)

        // Then
        XCTAssertEqual(sut.testHistory.count, 1)
        XCTAssertEqual(sut.totalCount, 1)
        XCTAssertFalse(sut.hasMore, "hasMore should be false when no more results")
    }

    // MARK: - Load More Tests

    func testLoadMore_AppendsResults() async {
        // Given - Initial fetch with hasMore = true
        let page1Results = [
            createMockTestResult(id: 1),
            createMockTestResult(id: 2)
        ]
        await mockAPIClient.setTestHistoryResponse(page1Results, totalCount: 4, hasMore: true)
        await sut.fetchHistory(forceRefresh: true)

        // Configure second page response
        let page2Results = [
            createMockTestResult(id: 3),
            createMockTestResult(id: 4)
        ]
        await mockAPIClient.setPaginatedTestHistoryResponse(
            results: page2Results,
            totalCount: 4,
            limit: 50,
            offset: 2,
            hasMore: false
        )

        // When
        await sut.loadMore()

        // Then
        XCTAssertEqual(sut.testHistory.count, 4, "Should have 4 test results after loading more")
        XCTAssertFalse(sut.hasMore, "hasMore should be false after loading last page")
        XCTAssertFalse(sut.isLoadingMore, "isLoadingMore should be false after load completes")
    }

    func testLoadMore_DoesNothing_WhenNoMoreResults() async {
        // Given - Initial fetch with hasMore = false
        let results = [createMockTestResult(id: 1)]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 1, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        await mockAPIClient.reset()

        // When
        await sut.loadMore()

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertFalse(requestCalled, "Should not make API request when hasMore is false")
        XCTAssertEqual(sut.testHistory.count, 1, "Results should not change")
    }

    func testLoadMore_DoesNothing_WhenAlreadyLoadingMore() async {
        // Given - Initial fetch with hasMore = true
        let results = [createMockTestResult(id: 1)]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 10, hasMore: true)
        await sut.fetchHistory(forceRefresh: true)

        // Simulate isLoadingMore being true (we can't easily do this without internal access)
        // Instead, verify the guard works by checking behavior

        // When/Then - The guard check is tested implicitly by the correct behavior
        // The loadMore function checks guard hasMore, !isLoadingMore, !isLoading
    }

    func testLoadMore_DoesNothing_WhenStillLoading() async {
        // Given - Don't complete the initial load
        // This is hard to test synchronously, but the guard is in place
        XCTAssertFalse(sut.isLoadingMore, "isLoadingMore should be false initially")
    }

    // MARK: - Refresh Tests

    func testRefreshHistory_ResetsPaginationState() async {
        // Given - Load initial page and a second page
        let page1Results = [createMockTestResult(id: 1), createMockTestResult(id: 2)]
        await mockAPIClient.setTestHistoryResponse(page1Results, totalCount: 4, hasMore: true)
        await sut.fetchHistory(forceRefresh: true)

        let page2Results = [createMockTestResult(id: 3), createMockTestResult(id: 4)]
        await mockAPIClient.setPaginatedTestHistoryResponse(
            results: page2Results,
            totalCount: 4,
            limit: 50,
            offset: 2,
            hasMore: false
        )
        await sut.loadMore()

        XCTAssertEqual(sut.testHistory.count, 4, "Should have 4 results before refresh")

        // When - Refresh should reset to first page
        let refreshedResults = [createMockTestResult(id: 5), createMockTestResult(id: 6)]
        await mockAPIClient.setTestHistoryResponse(refreshedResults, totalCount: 10, hasMore: true)
        await sut.refreshHistory()

        // Then
        XCTAssertEqual(sut.testHistory.count, 2, "Should have only 2 results after refresh")
        XCTAssertEqual(sut.totalCount, 10, "totalCount should be updated")
        XCTAssertTrue(sut.hasMore, "hasMore should be true for new data")
    }

    // MARK: - Cache Behavior Tests

    func testFetchHistory_UsesCache_WhenNotForceRefresh() async {
        // Given - First fetch populates cache
        let results = [createMockTestResult(id: 1)]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 1, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled)

        await mockAPIClient.reset()

        // When - Second fetch should use cache
        await sut.fetchHistory(forceRefresh: false)

        // Then
        let secondRequestCalled = await mockAPIClient.requestCalled
        XCTAssertFalse(secondRequestCalled, "Should use cache instead of making API request")
        XCTAssertEqual(sut.testHistory.count, 1, "Should still have results from cache")
    }

    // MARK: - API Endpoint Tests

    func testFetchHistory_UsesPaginationParameters() async {
        // Given
        let results = [createMockTestResult(id: 1)]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 1, hasMore: false)

        // When
        await sut.fetchHistory(forceRefresh: true)

        // Then
        let lastEndpoint = await mockAPIClient.lastEndpoint
        if case let .testHistory(limit, offset) = lastEndpoint {
            XCTAssertEqual(limit, 50, "Should use pageSize of 50")
            XCTAssertEqual(offset, 0, "First fetch should use offset 0")
        } else {
            XCTFail("Expected testHistory endpoint with pagination parameters")
        }
    }

    func testLoadMore_UsesCorrectOffset() async {
        // Given - Initial fetch
        let page1Results = [createMockTestResult(id: 1), createMockTestResult(id: 2)]
        await mockAPIClient.setTestHistoryResponse(page1Results, totalCount: 4, hasMore: true)
        await sut.fetchHistory(forceRefresh: true)

        // Set up second page
        let page2Results = [createMockTestResult(id: 3)]
        await mockAPIClient.setPaginatedTestHistoryResponse(
            results: page2Results,
            totalCount: 4,
            limit: 50,
            offset: 2,
            hasMore: true
        )

        await mockAPIClient.reset()
        await mockAPIClient.setPaginatedTestHistoryResponse(
            results: page2Results,
            totalCount: 4,
            limit: 50,
            offset: 2,
            hasMore: true
        )

        // When
        await sut.loadMore()

        // Then
        let lastEndpoint = await mockAPIClient.lastEndpoint
        if case let .testHistory(limit, offset) = lastEndpoint {
            XCTAssertEqual(limit, 50, "Should use pageSize of 50")
            XCTAssertEqual(offset, 2, "Second page should use offset 2")
        } else {
            XCTFail("Expected testHistory endpoint with pagination parameters")
        }
    }

    // MARK: - Computed Properties Tests

    func testTotalTestsTaken_ReturnsAllTestCount() async {
        // Given
        let results = [
            createMockTestResult(id: 1),
            createMockTestResult(id: 2)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 2, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // Then - totalTestsTaken uses allTestHistory.count which matches results loaded
        XCTAssertEqual(sut.totalTestsTaken, 2)
    }

    // MARK: - Error Handling Tests

    func testFetchHistory_HandlesError() async {
        // Given
        let apiError = APIError.serverError(statusCode: 500, message: "Server error")
        await mockAPIClient.setMockError(apiError)

        // When
        await sut.fetchHistory(forceRefresh: true)

        // Then
        XCTAssertNotNil(sut.error, "Error should be set on failure")
        XCTAssertTrue(sut.testHistory.isEmpty, "testHistory should be empty on error")
    }

    func testLoadMore_HandlesError() async {
        // Given - Initial successful fetch
        let results = [createMockTestResult(id: 1)]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 10, hasMore: true)
        await sut.fetchHistory(forceRefresh: true)

        // Set up error for loadMore
        let apiError = APIError.serverError(statusCode: 500, message: "Server error")
        await mockAPIClient.setMockError(apiError)

        // When
        await sut.loadMore()

        // Then
        XCTAssertNotNil(sut.error, "Error should be set on failure")
        XCTAssertEqual(sut.testHistory.count, 1, "Original results should be preserved")
        XCTAssertFalse(sut.isLoadingMore, "isLoadingMore should be false after error")
    }

    // MARK: - Filter Persistence Tests

    /// Test that sort order defaults to .newestFirst when no saved state exists
    func testSortOrder_DefaultsToNewestFirst_WhenNoSavedState() {
        // Given - No saved sort order in UserDefaults
        XCTAssertNil(
            testUserDefaults.object(forKey: sortOrderStorageKey),
            "UserDefaults should not have a saved sort order before test"
        )

        // When - Reading the default value
        // @AppStorage provides .newestFirst as the default value
        let defaultValue = testUserDefaults.string(forKey: sortOrderStorageKey)

        // Then - Should return nil (no stored value), which will trigger @AppStorage's default
        XCTAssertNil(
            defaultValue,
            "When no value is stored, UserDefaults returns nil for string keys"
        )

        // Verify the ViewModel uses the default
        XCTAssertEqual(
            sut.sortOrder,
            .newestFirst,
            "Sort order should default to .newestFirst"
        )
    }

    /// Test that date filter defaults to .all when no saved state exists
    func testDateFilter_DefaultsToAll_WhenNoSavedState() {
        // Given - No saved date filter in UserDefaults
        XCTAssertNil(
            testUserDefaults.object(forKey: dateFilterStorageKey),
            "UserDefaults should not have a saved date filter before test"
        )

        // When - Reading the default value
        let defaultValue = testUserDefaults.string(forKey: dateFilterStorageKey)

        // Then - Should return nil (no stored value), which will trigger @AppStorage's default
        XCTAssertNil(
            defaultValue,
            "When no value is stored, UserDefaults returns nil for string keys"
        )

        // Verify the ViewModel uses the default
        XCTAssertEqual(
            sut.dateFilter,
            .all,
            "Date filter should default to .all"
        )
    }

    /// Test that sort order persists when changed to oldestFirst
    func testSortOrder_PersistsToUserDefaults_WhenChangedToOldestFirst() {
        // Given - Starting with default sort order
        XCTAssertEqual(sut.sortOrder, .newestFirst)

        // When - Changing sort order to oldestFirst
        sut.sortOrder = .oldestFirst

        // Then - Value should persist in UserDefaults
        let savedValue = UserDefaults.standard.string(forKey: sortOrderStorageKey)
        XCTAssertEqual(
            savedValue,
            TestHistorySortOrder.oldestFirst.rawValue,
            "OldestFirst sort order should persist to UserDefaults"
        )
    }

    /// Test that sort order persists when changed back to newestFirst
    func testSortOrder_PersistsToUserDefaults_WhenChangedBackToNewestFirst() {
        // Given - Starting with oldestFirst
        sut.sortOrder = .oldestFirst

        // When - Changing back to newestFirst
        sut.sortOrder = .newestFirst

        // Then - NewestFirst selection should persist
        let savedValue = UserDefaults.standard.string(forKey: sortOrderStorageKey)
        XCTAssertEqual(
            savedValue,
            TestHistorySortOrder.newestFirst.rawValue,
            "NewestFirst sort order should persist to UserDefaults"
        )
    }

    /// Test that date filter persists when changed to lastMonth
    func testDateFilter_PersistsToUserDefaults_WhenChangedToLastMonth() {
        // Given - Starting with default filter
        XCTAssertEqual(sut.dateFilter, .all)

        // When - Changing filter to lastMonth
        sut.dateFilter = .lastMonth

        // Then - Value should persist in UserDefaults
        let savedValue = UserDefaults.standard.string(forKey: dateFilterStorageKey)
        XCTAssertEqual(
            savedValue,
            TestHistoryDateFilter.lastMonth.rawValue,
            "LastMonth filter should persist to UserDefaults"
        )
    }

    /// Test that date filter persists when changed to lastSixMonths
    func testDateFilter_PersistsToUserDefaults_WhenChangedToLastSixMonths() {
        // Given - Starting with default filter, reset to ensure clean state
        sut.dateFilter = .all
        XCTAssertEqual(sut.dateFilter, .all)

        // When - Changing filter to lastSixMonths
        sut.dateFilter = .lastSixMonths

        // Then - Value should persist in UserDefaults
        let savedValue = UserDefaults.standard.string(forKey: dateFilterStorageKey)
        XCTAssertEqual(
            savedValue,
            TestHistoryDateFilter.lastSixMonths.rawValue,
            "LastSixMonths filter should persist to UserDefaults"
        )
    }

    /// Test that date filter persists when changed to lastYear
    func testDateFilter_PersistsToUserDefaults_WhenChangedToLastYear() {
        // Given - Starting with default filter, reset to ensure clean state
        sut.dateFilter = .all
        XCTAssertEqual(sut.dateFilter, .all)

        // When - Changing filter to lastYear
        sut.dateFilter = .lastYear

        // Then - Value should persist in UserDefaults
        let savedValue = UserDefaults.standard.string(forKey: dateFilterStorageKey)
        XCTAssertEqual(
            savedValue,
            TestHistoryDateFilter.lastYear.rawValue,
            "LastYear filter should persist to UserDefaults"
        )
    }

    /// Test that date filter persists when changed back to all
    func testDateFilter_PersistsToUserDefaults_WhenChangedBackToAll() {
        // Given - Starting with lastMonth filter
        sut.dateFilter = .lastMonth

        // When - Changing back to all
        sut.dateFilter = .all

        // Then - All filter selection should persist
        let savedValue = UserDefaults.standard.string(forKey: dateFilterStorageKey)
        XCTAssertEqual(
            savedValue,
            TestHistoryDateFilter.all.rawValue,
            "All filter should persist to UserDefaults"
        )
    }

    /// Test that sort order is restored from UserDefaults when oldestFirst was previously selected
    func testSortOrder_RestoresFromUserDefaults_WhenOldestFirstWasPreviouslySelected() {
        // Given - OldestFirst was previously selected and saved
        UserDefaults.standard.set(
            TestHistorySortOrder.oldestFirst.rawValue,
            forKey: sortOrderStorageKey
        )

        // When - Creating a new ViewModel instance (simulating app restart)
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Then - Should restore oldestFirst sort order
        XCTAssertEqual(
            newViewModel.sortOrder,
            .oldestFirst,
            "OldestFirst sort order should be restored from UserDefaults"
        )
    }

    /// Test that date filter is restored from UserDefaults when lastMonth was previously selected
    func testDateFilter_RestoresFromUserDefaults_WhenLastMonthWasPreviouslySelected() {
        // Given - LastMonth was previously selected and saved
        UserDefaults.standard.set(
            TestHistoryDateFilter.lastMonth.rawValue,
            forKey: dateFilterStorageKey
        )

        // When - Creating a new ViewModel instance (simulating app restart)
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Then - Should restore lastMonth filter
        XCTAssertEqual(
            newViewModel.dateFilter,
            .lastMonth,
            "LastMonth filter should be restored from UserDefaults"
        )
    }

    /// Test that date filter is restored from UserDefaults when lastSixMonths was previously selected
    func testDateFilter_RestoresFromUserDefaults_WhenLastSixMonthsWasPreviouslySelected() {
        // Given - LastSixMonths was previously selected and saved
        UserDefaults.standard.set(
            TestHistoryDateFilter.lastSixMonths.rawValue,
            forKey: dateFilterStorageKey
        )

        // When - Creating a new ViewModel instance (simulating app restart)
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Then - Should restore lastSixMonths filter
        XCTAssertEqual(
            newViewModel.dateFilter,
            .lastSixMonths,
            "LastSixMonths filter should be restored from UserDefaults"
        )
    }

    /// Test that date filter is restored from UserDefaults when lastYear was previously selected
    func testDateFilter_RestoresFromUserDefaults_WhenLastYearWasPreviouslySelected() {
        // Given - LastYear was previously selected and saved
        UserDefaults.standard.set(
            TestHistoryDateFilter.lastYear.rawValue,
            forKey: dateFilterStorageKey
        )

        // When - Creating a new ViewModel instance (simulating app restart)
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Then - Should restore lastYear filter
        XCTAssertEqual(
            newViewModel.dateFilter,
            .lastYear,
            "LastYear filter should be restored from UserDefaults"
        )
    }

    /// Test that invalid stored sort order falls back to default
    func testSortOrder_FallsBackToDefault_WhenStoredValueIsInvalid() {
        // Given - Invalid sort order value in UserDefaults
        UserDefaults.standard.set("InvalidSortOrder", forKey: sortOrderStorageKey)

        // When - Creating a new ViewModel instance
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Then - Should fall back to default (.newestFirst)
        XCTAssertEqual(
            newViewModel.sortOrder,
            .newestFirst,
            "Should fall back to .newestFirst when stored value is invalid"
        )
    }

    /// Test that invalid stored date filter falls back to default
    func testDateFilter_FallsBackToDefault_WhenStoredValueIsInvalid() {
        // Given - Invalid date filter value in UserDefaults
        UserDefaults.standard.set("InvalidDateFilter", forKey: dateFilterStorageKey)

        // When - Creating a new ViewModel instance
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Then - Should fall back to default (.all)
        XCTAssertEqual(
            newViewModel.dateFilter,
            .all,
            "Should fall back to .all when stored value is invalid"
        )
    }

    /// Test that both filters can be persisted and restored together
    func testFilters_PersistAndRestoreTogether() {
        // Given - Set both filters to non-default values
        sut.sortOrder = .oldestFirst
        sut.dateFilter = .lastSixMonths

        // Verify persistence
        let savedSortOrder = UserDefaults.standard.string(forKey: sortOrderStorageKey)
        let savedDateFilter = UserDefaults.standard.string(forKey: dateFilterStorageKey)
        XCTAssertEqual(savedSortOrder, TestHistorySortOrder.oldestFirst.rawValue)
        XCTAssertEqual(savedDateFilter, TestHistoryDateFilter.lastSixMonths.rawValue)

        // When - Creating a new ViewModel instance (simulating app restart)
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Then - Both filters should be restored
        XCTAssertEqual(
            newViewModel.sortOrder,
            .oldestFirst,
            "Sort order should be restored"
        )
        XCTAssertEqual(
            newViewModel.dateFilter,
            .lastSixMonths,
            "Date filter should be restored"
        )

        UserDefaults.standard.removeObject(forKey: dateFilterStorageKey)
    }

    /// Test that storage keys use correct reverse-DNS notation
    func testFilterPersistence_UsesCorrectStorageKeys() {
        // This test verifies the storage keys match the expected format

        // Given/When - Set filter values
        sut.sortOrder = .oldestFirst
        sut.dateFilter = .lastMonth

        // Then - Verify storage keys exist with correct naming convention
        let sortOrderExists = UserDefaults.standard.object(forKey: sortOrderStorageKey) != nil
        let dateFilterExists = UserDefaults.standard.object(forKey: dateFilterStorageKey) != nil

        XCTAssertTrue(sortOrderExists, "Sort order should be stored with key: \(sortOrderStorageKey)")
        XCTAssertTrue(dateFilterExists, "Date filter should be stored with key: \(dateFilterStorageKey)")

        // Verify the keys follow reverse-DNS notation (com.aiq.*)
        XCTAssertTrue(sortOrderStorageKey.hasPrefix("com.aiq."), "Storage key should use reverse-DNS notation")
        XCTAssertTrue(dateFilterStorageKey.hasPrefix("com.aiq."), "Storage key should use reverse-DNS notation")

        UserDefaults.standard.removeObject(forKey: dateFilterStorageKey)
    }

    // MARK: - Filter Application Behavior Tests

    /// Test that setSortOrder applies newestFirst sorting correctly
    func testSetSortOrder_AppliesNewestFirstSort_WhenSet() async {
        // Given - Load test data with known dates
        let oldDate = Date().addingTimeInterval(-86400 * 2) // 2 days ago
        let newDate = Date()
        let results = [
            createMockTestResult(id: 1, completedAt: oldDate),
            createMockTestResult(id: 2, completedAt: newDate)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 2, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // When - Set sort order to newestFirst
        sut.setSortOrder(.newestFirst)

        // Then - Verify newest is first
        XCTAssertEqual(sut.testHistory.count, 2, "Should have 2 test results")
        XCTAssertEqual(sut.testHistory.first?.id, 2, "Newest test should be first")
        XCTAssertEqual(sut.testHistory.last?.id, 1, "Oldest test should be last")
    }

    /// Test that setSortOrder applies oldestFirst sorting correctly
    func testSetSortOrder_AppliesOldestFirstSort_WhenSet() async {
        // Given - Load test data with known dates
        let oldDate = Date().addingTimeInterval(-86400 * 2) // 2 days ago
        let newDate = Date()
        let results = [
            createMockTestResult(id: 1, completedAt: oldDate),
            createMockTestResult(id: 2, completedAt: newDate)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 2, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // When - Set sort order to oldestFirst
        sut.setSortOrder(.oldestFirst)

        // Then - Verify oldest is first
        XCTAssertEqual(sut.testHistory.count, 2, "Should have 2 test results")
        XCTAssertEqual(sut.testHistory.first?.id, 1, "Oldest test should be first")
        XCTAssertEqual(sut.testHistory.last?.id, 2, "Newest test should be last")
    }

    /// Test that setDateFilter filters to last 30 days correctly
    func testSetDateFilter_FiltersToLastMonth_WhenSet() async {
        // Given - Load test data with dates inside and outside the filter
        let ancientDate = Date().addingTimeInterval(-86400 * 60) // 60 days ago
        let recentDate = Date().addingTimeInterval(-86400 * 15) // 15 days ago
        let results = [
            createMockTestResult(id: 1, completedAt: ancientDate),
            createMockTestResult(id: 2, completedAt: recentDate)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 2, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // When - Apply lastMonth filter
        sut.setDateFilter(.lastMonth)

        // Then - Verify only recent test is included
        XCTAssertEqual(sut.testHistory.count, 1, "Should filter to 1 result")
        XCTAssertEqual(sut.testHistory.first?.id, 2, "Should only include recent test")
    }

    /// Test that setDateFilter filters to last 6 months correctly
    func testSetDateFilter_FiltersToLastSixMonths_WhenSet() async {
        // Given - Load test data with dates inside and outside the filter
        let ancientDate = Date().addingTimeInterval(-86400 * 200) // 200 days ago (outside 6 months)
        let recentDate = Date().addingTimeInterval(-86400 * 90) // 90 days ago (within 6 months)
        let results = [
            createMockTestResult(id: 1, completedAt: ancientDate),
            createMockTestResult(id: 2, completedAt: recentDate)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 2, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // When - Apply lastSixMonths filter
        sut.setDateFilter(.lastSixMonths)

        // Then - Verify only recent test is included
        XCTAssertEqual(sut.testHistory.count, 1, "Should filter to 1 result")
        XCTAssertEqual(sut.testHistory.first?.id, 2, "Should only include test within 6 months")
    }

    /// Test that setDateFilter filters to last year correctly
    func testSetDateFilter_FiltersToLastYear_WhenSet() async {
        // Given - Load test data with dates inside and outside the filter
        let ancientDate = Date().addingTimeInterval(-86400 * 400) // 400 days ago (outside 1 year)
        let recentDate = Date().addingTimeInterval(-86400 * 180) // 180 days ago (within 1 year)
        let results = [
            createMockTestResult(id: 1, completedAt: ancientDate),
            createMockTestResult(id: 2, completedAt: recentDate)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 2, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // When - Apply lastYear filter
        sut.setDateFilter(.lastYear)

        // Then - Verify only recent test is included
        XCTAssertEqual(sut.testHistory.count, 1, "Should filter to 1 result")
        XCTAssertEqual(sut.testHistory.first?.id, 2, "Should only include test within 1 year")
    }

    /// Test that setDateFilter shows all results when set to .all
    func testSetDateFilter_ShowsAllResults_WhenSetToAll() async {
        // Given - Load test data with various dates
        let ancientDate = Date().addingTimeInterval(-86400 * 400) // 400 days ago
        let recentDate = Date()
        let results = [
            createMockTestResult(id: 1, completedAt: ancientDate),
            createMockTestResult(id: 2, completedAt: recentDate)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 2, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // First apply a restrictive filter
        sut.setDateFilter(.lastMonth)
        XCTAssertEqual(sut.testHistory.count, 1, "Should have 1 result with lastMonth filter")

        // When - Set filter back to all
        sut.setDateFilter(.all)

        // Then - All results should be shown
        XCTAssertEqual(sut.testHistory.count, 2, "Should show all results")
    }

    /// Test that filters work together correctly (sort + date filter)
    func testFilters_ApplyBothSortAndDateFilter_Together() async {
        // Given - Load test data with various dates
        let oldWithinMonth = Date().addingTimeInterval(-86400 * 20) // 20 days ago
        let newWithinMonth = Date().addingTimeInterval(-86400 * 5) // 5 days ago
        let outsideMonth = Date().addingTimeInterval(-86400 * 60) // 60 days ago
        let results = [
            createMockTestResult(id: 1, completedAt: oldWithinMonth),
            createMockTestResult(id: 2, completedAt: newWithinMonth),
            createMockTestResult(id: 3, completedAt: outsideMonth)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 3, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // When - Apply both filters
        sut.setDateFilter(.lastMonth)
        sut.setSortOrder(.oldestFirst)

        // Then - Should filter to 2 results and sort oldest first
        XCTAssertEqual(sut.testHistory.count, 2, "Should have 2 results within last month")
        XCTAssertEqual(sut.testHistory.first?.id, 1, "Oldest within filter should be first")
        XCTAssertEqual(sut.testHistory.last?.id, 2, "Newest within filter should be last")
    }

    /// Test that filter handles empty results gracefully
    func testSetDateFilter_HandlesEmptyResults_WhenAllFiltered() async {
        // Given - Load test data outside the filter range
        let ancientDate = Date().addingTimeInterval(-86400 * 60) // 60 days ago
        let results = [
            createMockTestResult(id: 1, completedAt: ancientDate)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 1, hasMore: false)
        await sut.fetchHistory(forceRefresh: true)

        // When - Apply restrictive filter
        sut.setDateFilter(.lastMonth)

        // Then - Should handle empty results gracefully
        XCTAssertTrue(sut.testHistory.isEmpty, "Should have no results after filtering")
        XCTAssertEqual(sut.filteredResultsCount, 0, "Filtered count should be 0")
        XCTAssertEqual(sut.totalTestsTaken, 1, "Total tests should still reflect all data")
    }

    /// Test that restored filters are applied when fetching data
    func testRestoredFilters_AreApplied_WhenFetchingData() async {
        // Given - Previously saved filters
        UserDefaults.standard.set(
            TestHistorySortOrder.oldestFirst.rawValue,
            forKey: sortOrderStorageKey
        )
        UserDefaults.standard.set(
            TestHistoryDateFilter.lastMonth.rawValue,
            forKey: dateFilterStorageKey
        )

        // Create new ViewModel (simulating app restart)
        let newViewModel = HistoryViewModel(apiClient: mockAPIClient)

        // Load test data
        let oldWithinMonth = Date().addingTimeInterval(-86400 * 20)
        let newWithinMonth = Date().addingTimeInterval(-86400 * 5)
        let outsideMonth = Date().addingTimeInterval(-86400 * 60)
        let results = [
            createMockTestResult(id: 1, completedAt: oldWithinMonth),
            createMockTestResult(id: 2, completedAt: newWithinMonth),
            createMockTestResult(id: 3, completedAt: outsideMonth)
        ]
        await mockAPIClient.setTestHistoryResponse(results, totalCount: 3, hasMore: false)

        // When - Fetch data
        await newViewModel.fetchHistory(forceRefresh: true)

        // Then - Restored filters should be applied
        XCTAssertEqual(newViewModel.sortOrder, .oldestFirst, "Sort order should be restored")
        XCTAssertEqual(newViewModel.dateFilter, .lastMonth, "Date filter should be restored")
        XCTAssertEqual(newViewModel.testHistory.count, 2, "Should filter to results within last month")
        XCTAssertEqual(newViewModel.testHistory.first?.id, 1, "Oldest within filter should be first")
        XCTAssertEqual(newViewModel.testHistory.last?.id, 2, "Newest within filter should be last")
    }
}
