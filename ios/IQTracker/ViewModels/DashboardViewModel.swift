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

    /// Fetch dashboard data from API
    func fetchDashboardData() async {
        setLoading(true)
        clearError()

        do {
            // Fetch test history
            let history: [TestResult] = try await apiClient.request(
                endpoint: .testHistory,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )

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
                await self.fetchDashboardData()
            }
        }
    }

    /// Refresh dashboard data (pull-to-refresh)
    func refreshDashboard() async {
        isRefreshing = true
        await fetchDashboardData()
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
