import Combine
import Foundation

/// ViewModel for managing dashboard data and state
@MainActor
class DashboardViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var testCount: Int = 0

    // Active session tracking
    @Published var activeTestSession: TestSession?
    @Published var activeSessionQuestionsAnswered: Int?

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol
    private let analyticsService: AnalyticsService
    private let answerStorage: LocalAnswerStorageProtocol

    // MARK: - Initialization

    init(
        apiService: OpenAPIServiceProtocol,
        analyticsService: AnalyticsService = .shared,
        answerStorage: LocalAnswerStorageProtocol = LocalAnswerStorage()
    ) {
        self.apiService = apiService
        self.analyticsService = analyticsService
        self.answerStorage = answerStorage
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch dashboard data from API (with caching)
    /// - Parameters:
    ///   - forceRefresh: If true, bypass cache and fetch from API
    ///   - showLoadingIndicator: If false, skip `setLoading` calls so the system
    ///     pull-to-refresh spinner handles UI feedback and the ScrollView is not
    ///     destroyed mid-flight (which would cancel the `.refreshable` task with
    ///     NSURLErrorDomain Code=-999).
    func fetchDashboardData(forceRefresh: Bool = false, showLoadingIndicator: Bool = true) async {
        if showLoadingIndicator { setLoading(true) }
        clearError()

        // Fetch count and active session in parallel
        async let countError: Error? = fetchTestCount(forceRefresh: forceRefresh)
        async let activeSessionError: Error? = fetchActiveSession(forceRefresh: forceRefresh)

        let countResult = await countError
        _ = await activeSessionError // Active session errors are logged but non-blocking

        if let countError = countResult {
            let dashCtx = CrashlyticsErrorRecorder.ErrorContext.fetchDashboard.rawValue
            handleError(countError, context: dashCtx) { [weak self] in
                await self?.fetchDashboardData(forceRefresh: forceRefresh, showLoadingIndicator: showLoadingIndicator)
            }
            return
        }

        if showLoadingIndicator { setLoading(false) }
    }

    /// Refresh dashboard data (pull-to-refresh)
    func refreshDashboard() async {
        await withRefreshing {
            // Clear cache and force refresh
            await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
            await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
            // Pass showLoadingIndicator: false so the system pull-to-refresh spinner
            // handles UI feedback. Calling setLoading(true) here would swap the
            // ScrollView for LoadingView, destroying the refreshable context and
            // cancelling the in-flight network request (NSURLErrorDomain Code=-999).
            await self.fetchDashboardData(forceRefresh: true, showLoadingIndicator: false)
        }
    }

    /// Abandon the active test session
    /// - Note: This will mark the test as abandoned and clear the active session state
    func abandonActiveTest() async {
        guard let sessionId = activeTestSession?.id else {
            return
        }

        let questionsAnswered = activeSessionQuestionsAnswered ?? 0

        setLoading(true)
        clearError()

        do {
            let response = try await apiService.abandonTest(sessionId: sessionId)

            // Track abandonment from dashboard
            analyticsService.trackTestAbandonedFromDashboard(
                sessionId: sessionId,
                questionsAnswered: questionsAnswered
            )

            // Clear active session state
            activeTestSession = nil
            activeSessionQuestionsAnswered = nil

            // Clear locally saved progress to prevent stale "Resume Test?" dialog
            answerStorage.clearProgress()

            // Refresh dashboard to update test history (abandoned test might appear)
            await refreshDashboard()

            setLoading(false)

        } catch {
            handleError(error, context: CrashlyticsErrorRecorder.ErrorContext.abandonTest.rawValue) { [weak self] in
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
            let newCount = paginatedResponse.totalCount
            if testCount != newCount { testCount = newCount }
            return nil

        } catch is CancellationError {
            return nil // view is gone; discard silently
        } catch let urlError as NSError
            where urlError.domain == NSURLErrorDomain && urlError.code == NSURLErrorCancelled {
            return nil // URLSession cancelled mid-flight; discard silently
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
        } catch let urlError as NSError
            where urlError.domain == NSURLErrorDomain && urlError.code == NSURLErrorCancelled {
            return nil // URLSession cancelled mid-flight; discard silently
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
            activeSessionQuestionsAnswered = localAnswerCount(for: response.session.id)
                ?? response.questionsCount
            // Note: analytics tracking is the caller's responsibility;
            // cache-hit loads skip trackActiveSessionDetected to avoid
            // inflating session-detection counts with repeated reads of
            // already-known state.
        } else {
            // Guard against nil→nil @Published assignments: every assignment fires
            // objectWillChange regardless of whether the value changed, triggering a
            // SwiftUI re-render that cancels the in-flight .refreshable task.
            if activeTestSession != nil { activeTestSession = nil }
            if activeSessionQuestionsAnswered != nil { activeSessionQuestionsAnswered = nil }
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
        guard let session = activeTestSession, session.isInProgress else { return false }
        let elapsed = Date().timeIntervalSince(session.startedAt)
        return elapsed < Double(TestTimerManager.totalTimeSeconds)
    }

    func setActiveTestSession(_ session: TestSession) {
        activeTestSession = session
    }

    // MARK: - Private Helpers

    /// Returns the number of non-empty locally-saved answers for the given session,
    /// or nil if no matching local progress exists.
    private func localAnswerCount(for sessionId: Int) -> Int? {
        guard let saved = answerStorage.loadProgress(),
              saved.sessionId == sessionId
        else { return nil }
        let count = saved.userAnswers.values.filter { !$0.isEmpty }.count
        return count > 0 ? count : nil
    }
}
