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

    // Active session tracking
    @Published var activeTestSession: TestSession?
    @Published var activeSessionQuestionsAnswered: Int?

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

        // Fetch test history and active session in parallel
        // Both functions handle their own state updates and errors
        async let historyTask: Void = fetchTestHistory(forceRefresh: forceRefresh)
        async let activeSessionTask: Void = fetchActiveSession(forceRefresh: forceRefresh)

        // Wait for both tasks to complete
        await historyTask
        await activeSessionTask

        setLoading(false)
    }

    /// Refresh dashboard data (pull-to-refresh)
    func refreshDashboard() async {
        isRefreshing = true
        // Clear cache and force refresh
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
        await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
        await fetchDashboardData(forceRefresh: true)
        isRefreshing = false
    }

    /// Abandon the active test session
    /// - Note: This will mark the test as abandoned and clear the active session state
    func abandonActiveTest() async {
        guard let sessionId = activeTestSession?.id else {
            #if DEBUG
                print("⚠️ No active test session to abandon")
            #endif
            return
        }

        let questionsAnswered = activeSessionQuestionsAnswered ?? 0

        setLoading(true)
        clearError()

        do {
            // Call abandon endpoint
            let response: TestAbandonResponse = try await apiClient.request(
                endpoint: .testAbandon(sessionId),
                method: .post,
                body: nil as String?,
                requiresAuth: true,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )

            #if DEBUG
                print("✅ Test abandoned: \(response.message)")
                print("   Responses saved: \(response.responsesSaved)")
            #endif

            // Track abandonment from dashboard
            AnalyticsService.shared.trackTestAbandonedFromDashboard(
                sessionId: sessionId,
                questionsAnswered: questionsAnswered
            )

            // Clear active session state
            activeTestSession = nil
            activeSessionQuestionsAnswered = nil

            // Refresh dashboard to update test history (abandoned test might appear)
            await refreshDashboard()

            setLoading(false)

        } catch {
            handleError(error) {
                await self.abandonActiveTest()
            }
        }
    }

    /// Fetch test history from API with caching and update dashboard state
    /// - Parameter forceRefresh: If true, bypass cache and fetch from API
    /// - Note: Errors are logged and result in empty dashboard state.
    ///         Dashboard only needs the first page of results for summary stats.
    func fetchTestHistory(forceRefresh: Bool = false) async {
        do {
            // API now returns paginated response (BCQ-004)
            // Dashboard only needs the first page to show summary stats
            let paginatedResponse: PaginatedTestHistoryResponse = try await apiClient.request(
                endpoint: .testHistory(limit: nil, offset: nil),
                method: .get,
                body: nil as String?,
                requiresAuth: true,
                cacheKey: DataCache.Key.testHistory,
                cacheDuration: nil, // Use default cache duration
                forceRefresh: forceRefresh
            )

            // Update dashboard state with results array
            // Note: For users with >50 tests, this only shows stats from first 50
            // but that's acceptable for dashboard summary display
            updateDashboardState(with: paginatedResponse.results, totalCount: paginatedResponse.totalCount)

        } catch {
            #if DEBUG
                print("⚠️ Failed to fetch test history: \(error)")
            #endif
            // Set empty state on error
            updateDashboardState(with: [], totalCount: 0)
        }
    }

    /// Fetch active test session from API with caching
    /// - Parameter forceRefresh: If true, bypass cache and fetch from API
    /// - Note: Errors are logged but don't block dashboard loading
    func fetchActiveSession(forceRefresh: Bool = false) async {
        do {
            let response: TestSessionStatusResponse? = try await apiClient.request(
                endpoint: .testActive,
                method: .get,
                body: nil as String?,
                requiresAuth: true,
                cacheKey: DataCache.Key.activeTestSession,
                cacheDuration: 120, // 2 minutes
                forceRefresh: forceRefresh
            )

            // Update active session state
            updateActiveSessionState(response)

        } catch {
            #if DEBUG
                print("⚠️ Failed to fetch active session: \(error)")
            #endif
            // Clear active session state on error
            updateActiveSessionState(nil)
        }
    }

    /// Update dashboard state from test history
    /// - Parameters:
    ///   - history: Array of test results (may be partial if paginated)
    ///   - totalCount: Total number of tests across all pages
    private func updateDashboardState(with history: [TestResult], totalCount: Int) {
        if !history.isEmpty {
            // Sort by date (newest first)
            let sortedHistory = history.sorted { $0.completedAt > $1.completedAt }
            latestTestResult = sortedHistory.first

            // Use server's totalCount instead of array count for accuracy
            testCount = totalCount

            // Calculate average score from available results
            // Note: This may be approximate for users with >50 tests
            let totalScore = history.reduce(0) { $0 + $1.iqScore }
            averageScore = totalScore / history.count
        } else {
            latestTestResult = nil
            testCount = 0
            averageScore = nil
        }
    }

    /// Update active session state from response
    /// - Parameter response: The session status response, or nil if no active session
    private func updateActiveSessionState(_ response: TestSessionStatusResponse?) {
        if let response {
            activeTestSession = response.session
            activeSessionQuestionsAnswered = response.questionsCount

            // Track active session detection
            AnalyticsService.shared.trackActiveSessionDetected(
                sessionId: response.session.id,
                questionsAnswered: response.questionsCount
            )
        } else {
            activeTestSession = nil
            activeSessionQuestionsAnswered = nil
        }
    }

    /// Track test resume from dashboard
    /// Called when user navigates to test from dashboard
    func trackTestResumed() {
        guard let sessionId = activeTestSession?.id,
              let questionsAnswered = activeSessionQuestionsAnswered
        else {
            return
        }

        AnalyticsService.shared.trackTestResumedFromDashboard(
            sessionId: sessionId,
            questionsAnswered: questionsAnswered
        )
    }

    // MARK: - Computed Properties

    /// Whether user has taken any tests
    var hasTests: Bool {
        testCount > 0
    }

    /// Whether user has an active (in-progress) test session
    var hasActiveTest: Bool {
        activeTestSession != nil
    }

    /// Formatted latest test date
    var latestTestDateFormatted: String? {
        guard let latest = latestTestResult else { return nil }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: latest.completedAt)
    }

    func setActiveTestSession(_ session: TestSession) {
        activeTestSession = session
    }
}
