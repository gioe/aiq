import Combine
import Foundation

/// ViewModel for managing test history data and state
@MainActor
class HistoryViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var testHistory: [TestResult] = []
    @Published var isRefreshing: Bool = false

    // MARK: - Private Properties

    private let apiClient: APIClientProtocol

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

            testHistory = history
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

    /// Refresh history data (pull-to-refresh)
    func refreshHistory() async {
        isRefreshing = true
        await fetchHistory()
        isRefreshing = false
    }

    // MARK: - Computed Properties

    var hasHistory: Bool {
        !testHistory.isEmpty
    }

    var averageIQScore: Int? {
        guard !testHistory.isEmpty else { return nil }
        let sum = testHistory.reduce(0) { $0 + $1.iqScore }
        return sum / testHistory.count
    }

    var bestIQScore: Int? {
        testHistory.map(\.iqScore).max()
    }

    var totalTestsTaken: Int {
        testHistory.count
    }
}
