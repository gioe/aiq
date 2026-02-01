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

    private let apiService: OpenAPIServiceProtocol

    // MARK: - Initialization

    init(apiService: OpenAPIServiceProtocol) {
        self.apiService = apiService
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch dashboard data from API (with caching)
    func fetchDashboardData(forceRefresh: Bool = false) async {
        setLoading(true)
        clearError()

        // Fetch test history and active session in parallel
        // Both functions return any errors they encounter
        async let historyError: Error? = fetchTestHistory(forceRefresh: forceRefresh)
        async let activeSessionError: Error? = fetchActiveSession(forceRefresh: forceRefresh)

        // Wait for both tasks to complete and collect errors
        let historyResult = await historyError
        _ = await activeSessionError // Active session errors are logged but non-blocking

        // Handle errors - history is critical, without it we can't show the dashboard
        if let historyError = historyResult {
            handleError(historyError, context: .fetchDashboard) { [weak self] in
                await self?.fetchDashboardData(forceRefresh: forceRefresh)
            }
            return
        }

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
                print("[WARN] No active test session to abandon")
            #endif
            return
        }

        let questionsAnswered = activeSessionQuestionsAnswered ?? 0

        setLoading(true)
        clearError()

        do {
            let response = try await apiService.abandonTest(sessionId: sessionId)

            #if DEBUG
                print("[SUCCESS] Test abandoned: \(response.message)")
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
            handleError(error, context: .abandonTest) { [weak self] in
                await self?.abandonActiveTest()
            }
        }
    }

    /// Fetch test history from API with caching and update dashboard state
    /// - Parameter forceRefresh: If true, bypass cache and fetch from API
    /// - Returns: The error if one occurred, nil on success
    /// - Note: Dashboard only needs the first page of results for summary stats.
    @discardableResult
    func fetchTestHistory(forceRefresh: Bool = false) async -> Error? {
        // Check cache first if not forcing refresh
        if !forceRefresh {
            if let cached: [TestResult] = await DataCache.shared.get(forKey: DataCache.Key.testHistory) {
                updateDashboardState(with: cached, totalCount: cached.count)
                return nil
            }
        }

        do {
            let paginatedResponse = try await apiService.getTestHistory(limit: nil, offset: nil)

            // Cache the results
            await DataCache.shared.set(paginatedResponse.results, forKey: DataCache.Key.testHistory)

            // Update dashboard state with results array
            updateDashboardState(with: paginatedResponse.results, totalCount: paginatedResponse.totalCount)
            return nil

        } catch {
            // Record non-fatal error to Crashlytics for production monitoring
            CrashlyticsErrorRecorder.recordError(error, context: .fetchDashboard)
            // Set empty state on error
            updateDashboardState(with: [], totalCount: 0)
            return error
        }
    }

    /// Fetch active test session from API with caching
    /// - Parameter forceRefresh: If true, bypass cache and fetch from API
    /// - Returns: The error if one occurred, nil on success
    /// - Note: Errors are logged but don't block dashboard loading
    @discardableResult
    func fetchActiveSession(forceRefresh: Bool = false) async -> Error? {
        // Check cache first if not forcing refresh
        if !forceRefresh {
            if let cached: TestSessionStatusResponse = await DataCache.shared.get(
                forKey: DataCache.Key.activeTestSession
            ) {
                updateActiveSessionState(cached)
                return nil
            }
        }

        do {
            let response = try await apiService.getActiveTest()

            // Cache the response
            if let response {
                await DataCache.shared.set(
                    response,
                    forKey: DataCache.Key.activeTestSession,
                    expiration: Constants.Cache.dashboardCacheDuration
                )
            }

            // Update active session state
            updateActiveSessionState(response)
            return nil

        } catch {
            // Record non-fatal error to Crashlytics for production monitoring
            CrashlyticsErrorRecorder.recordError(error, context: .fetchActiveSession)
            // Clear active session state on error
            updateActiveSessionState(nil)
            return error
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
        return latest.completedAt.toShortString()
    }

    func setActiveTestSession(_ session: TestSession) {
        activeTestSession = session
    }
}
