import Combine
import Foundation

/// ViewModel for managing dashboard data and state
@MainActor
class DashboardViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var testCount: Int = 0
    @Published var isRefreshing: Bool = false

    // Active session tracking
    @Published var activeTestSession: TestSession?
    @Published var activeSessionQuestionsAnswered: Int?

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol
    private let analyticsService: AnalyticsService

    // MARK: - Initialization

    init(apiService: OpenAPIServiceProtocol, analyticsService: AnalyticsService = .shared) {
        self.apiService = apiService
        self.analyticsService = analyticsService
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch dashboard data from API (with caching)
    func fetchDashboardData(forceRefresh: Bool = false) async {
        setLoading(true)
        clearError()

        // Fetch count and active session in parallel
        async let countError: Error? = fetchTestCount(forceRefresh: forceRefresh)
        async let activeSessionError: Error? = fetchActiveSession(forceRefresh: forceRefresh)

        let countResult = await countError
        _ = await activeSessionError // Active session errors are logged but non-blocking

        if let countError = countResult {
            handleError(countError, context: .fetchDashboard) { [weak self] in
                await self?.fetchDashboardData(forceRefresh: forceRefresh)
            }
            return
        }

        setLoading(false)
    }

    /// Refresh dashboard data (pull-to-refresh)
    func refreshDashboard() async {
        isRefreshing = true
        defer { isRefreshing = false }
        // Clear cache and force refresh
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
        await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
        await fetchDashboardData(forceRefresh: true)
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
            analyticsService.trackTestAbandonedFromDashboard(
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

    /// Fetch test count using a lightweight single-item request
    /// - Parameter forceRefresh: If true, bypass cache and fetch from API
    /// - Returns: The error if one occurred, nil on success
    @discardableResult
    func fetchTestCount(forceRefresh: Bool = false) async -> Error? {
        if !forceRefresh {
            if let cached: [TestResult] = await DataCache.shared.get(forKey: DataCache.Key.testHistory) {
                testCount = cached.count
                return nil
            }
        }

        do {
            let paginatedResponse = try await apiService.getTestHistory(limit: 1, offset: nil)
            testCount = paginatedResponse.totalCount
            return nil

        } catch is CancellationError {
            return nil // view is gone; discard silently
        } catch {
            testCount = 0
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
                // Cache hit: skip trackActiveSessionDetected — the session was
                // already detected on the previous API fetch; re-firing here
                // would inflate analytics counts with no new discovery.
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

            // Track first detection on fresh API fetch (not on cache-hit reloads)
            if let response {
                analyticsService.trackActiveSessionDetected(
                    sessionId: response.session.id,
                    questionsAnswered: response.questionsCount
                )
            }
            return nil

        } catch is CancellationError {
            return nil // view is gone; discard silently
        } catch {
            // Record non-fatal error to Crashlytics for production monitoring
            CrashlyticsErrorRecorder.recordError(error, context: .fetchActiveSession)
            // Clear active session state on error
            updateActiveSessionState(nil)
            return error
        }
    }

    /// Update active session state from response
    /// - Parameter response: The session status response, or nil if no active session
    private func updateActiveSessionState(_ response: TestSessionStatusResponse?) {
        if let response {
            activeTestSession = response.session
            activeSessionQuestionsAnswered = response.questionsCount
            // Note: analytics tracking is the caller's responsibility;
            // cache-hit loads skip trackActiveSessionDetected to avoid
            // inflating session-detection counts with repeated reads of
            // already-known state.
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

        analyticsService.trackTestResumedFromDashboard(
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

    func setActiveTestSession(_ session: TestSession) {
        activeTestSession = session
    }
}
