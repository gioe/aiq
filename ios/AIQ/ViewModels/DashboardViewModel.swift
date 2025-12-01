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

        do {
            // Fetch test history and active session in parallel
            // Active session check should not block dashboard load
            async let historyTask: [TestResult] = {
                // Try to get from cache first if not forcing refresh
                if !forceRefresh,
                   let cachedHistory: [TestResult] = await DataCache.shared.get(
                       forKey: DataCache.Key.testHistory
                   ) {
                    #if DEBUG
                        print("✅ Dashboard loaded \(cachedHistory.count) test results from cache")
                    #endif
                    return cachedHistory
                } else {
                    // Fetch from API
                    let history: [TestResult] = try await apiClient.request(
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
                    return history
                }
            }()

            // Fetch active session in parallel (errors handled internally)
            async let activeSessionTask: Void = fetchActiveSession(forceRefresh: forceRefresh)

            // Wait for both tasks to complete
            let history = try await historyTask
            await activeSessionTask

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

        setLoading(true)
        clearError()

        do {
            // Call abandon endpoint
            let response: TestAbandonResponse = try await apiClient.request(
                endpoint: .testAbandon(sessionId),
                method: .post,
                body: nil as String?,
                requiresAuth: true
            )

            #if DEBUG
                print("✅ Test abandoned: \(response.message)")
                print("   Responses saved: \(response.responsesSaved)")
            #endif

            // Clear active session state
            activeTestSession = nil
            activeSessionQuestionsAnswered = nil

            // Invalidate cache
            await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)

            // Refresh dashboard to update test history (abandoned test might appear)
            await fetchDashboardData(forceRefresh: true)

            setLoading(false)

        } catch {
            handleError(error) {
                await self.abandonActiveTest()
            }
        }
    }

    /// Fetch active test session from API with caching
    /// - Parameter forceRefresh: If true, bypass cache and fetch from API
    /// - Note: Errors are logged but don't block dashboard loading
    func fetchActiveSession(forceRefresh: Bool = false) async {
        do {
            let response = try await getActiveSessionResponse(forceRefresh: forceRefresh)
            updateActiveSessionState(response)
        } catch {
            #if DEBUG
                print("⚠️ Failed to fetch active session: \(error)")
            #endif
            updateActiveSessionState(nil)
        }
    }

    /// Get active session response from cache or API
    private func getActiveSessionResponse(forceRefresh: Bool) async throws -> TestSessionStatusResponse? {
        // Check cache first if not forcing refresh
        if !forceRefresh, let cached: TestSessionStatusResponse? = await DataCache.shared.get(
            forKey: DataCache.Key.activeTestSession
        ), let cachedResponse = cached {
            #if DEBUG
                print("✅ Active session loaded from cache: \(cachedResponse.session.id)")
            #endif
            return cachedResponse
        }

        #if DEBUG
            if !forceRefresh {
                print("ℹ️ No active session in cache, fetching from API")
            }
        #endif

        // Fetch from API
        let response: TestSessionStatusResponse? = try await apiClient.request(
            endpoint: .testActive,
            method: .get,
            body: nil as String?,
            requiresAuth: true
        )

        // Cache or remove based on response
        await cacheActiveSessionResponse(response)

        #if DEBUG
            logActiveSessionAPIResponse(response)
        #endif

        return response
    }

    /// Cache or remove active session response
    private func cacheActiveSessionResponse(_ response: TestSessionStatusResponse?) async {
        if let response {
            await DataCache.shared.set(
                response,
                forKey: DataCache.Key.activeTestSession,
                expiration: 120 // 2 minutes
            )
        } else {
            await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
        }
    }

    /// Log active session API response (debug only)
    private func logActiveSessionAPIResponse(_ response: TestSessionStatusResponse?) {
        #if DEBUG
            if let response {
                print(
                    "✅ Active session fetched from API: \(response.session.id) " +
                        "with \(response.questionsCount) questions answered"
                )
            } else {
                print("ℹ️ No active session found")
            }
        #endif
    }

    /// Update active session state from response
    /// - Parameter response: The session status response, or nil if no active session
    private func updateActiveSessionState(_ response: TestSessionStatusResponse?) {
        if let response {
            activeTestSession = response.session
            activeSessionQuestionsAnswered = response.questionsCount
        } else {
            activeTestSession = nil
            activeSessionQuestionsAnswered = nil
        }
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
}
