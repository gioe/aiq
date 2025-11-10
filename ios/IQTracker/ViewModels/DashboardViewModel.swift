import Combine
import Foundation

/// ViewModel for managing dashboard data and state
@MainActor
class DashboardViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var latestTestResult: TestResult?
    @Published var testCount: Int = 0
    @Published var averageScore: Int?
    @Published var isRefreshing: Bool = false

    // MARK: - Private Properties

    private let apiClient: APIClientProtocol

    // MARK: - Initialization

    init(apiClient: APIClientProtocol = APIClient.shared) {
        self.apiClient = apiClient
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch dashboard data from API (with caching)
    func fetchDashboardData(forceRefresh: Bool = false) async {
        setLoading(true)
        clearError()

        do {
            // Try to get from cache first if not forcing refresh
            var history: [TestResult]

            if !forceRefresh,
               let cachedHistory: [TestResult] = await DataCache.shared.get(
                   forKey: DataCache.Key.testHistory
               ) {
                history = cachedHistory
                #if DEBUG
                    print("✅ Dashboard loaded \(cachedHistory.count) test results from cache")
                #endif
            } else {
                // Fetch from API
                history = try await apiClient.request(
                    endpoint: .testHistory,
                    method: .get,
                    body: nil as String?,
                    requiresAuth: true
                )

                // Cache the results
                await DataCache.shared.set(history, forKey: DataCache.Key.testHistory)

                #if DEBUG
                    print("✅ Dashboard fetched \(history.count) test results from API")
                #endif
            }

            // Update dashboard data
            if !history.isEmpty {
                // Sort by date (newest first)
                let sortedHistory = history.sorted { $0.completedAt > $1.completedAt }
                latestTestResult = sortedHistory.first

                testCount = history.count

                // Calculate average score
                let totalScore = history.reduce(0) { $0 + $1.iqScore }
                averageScore = totalScore / history.count
            } else {
                latestTestResult = nil
                testCount = 0
                averageScore = nil
            }

            setLoading(false)

        } catch {
            handleError(error) {
                await self.fetchDashboardData(forceRefresh: forceRefresh)
            }
        }
    }

    /// Refresh dashboard data (pull-to-refresh)
    func refreshDashboard() async {
        isRefreshing = true
        // Clear cache and force refresh
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
        await fetchDashboardData(forceRefresh: true)
        isRefreshing = false
    }

    // MARK: - Computed Properties

    /// Whether user has taken any tests
    var hasTests: Bool {
        testCount > 0
    }

    /// Formatted latest test date
    var latestTestDateFormatted: String? {
        guard let latest = latestTestResult else { return nil }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: latest.completedAt)
    }
}
