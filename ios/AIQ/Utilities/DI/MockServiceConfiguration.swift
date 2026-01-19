import Foundation

#if DEBUG

    /// Configuration for registering mock services with the ServiceContainer
    ///
    /// This mirrors `ServiceConfiguration` but registers mock implementations
    /// suitable for UI testing. Mock services provide pre-configured responses
    /// without requiring a real backend connection.
    ///
    /// ## Usage
    ///
    /// This is called from `AIQApp.init()` when mock mode is detected:
    /// ```swift
    /// if MockModeDetector.isMockMode {
    ///     MockServiceConfiguration.configureServices(container: ServiceContainer.shared)
    /// } else {
    ///     ServiceConfiguration.configureServices(container: ServiceContainer.shared)
    /// }
    /// ```
    ///
    /// ## Architecture
    ///
    /// The mock services follow the same registration pattern as real services:
    /// 1. Layer 1: Services with no dependencies (APIClient, LocalAnswerStorage)
    /// 2. Layer 2: Services depending on Layer 1 (NotificationService)
    /// 3. Layer 3: AuthManager with lazy NotificationManager dependency
    /// 4. Layer 4: NotificationManager
    ///
    /// All mocks are configured based on the current `MockScenario` to provide
    /// appropriate initial state for each test.
    enum MockServiceConfiguration {
        /// Configure all mock services in the dependency injection container
        ///
        /// This method assumes it's called on the main thread during app initialization.
        /// The mock implementations require main actor isolation for their @Published properties.
        ///
        /// - Parameter container: The ServiceContainer to register services with
        @MainActor
        static func configureServices(container: ServiceContainer) {
            print("=== MOCK SERVICE CONFIGURATION CALLED ===")
            MockModeDetector.logStatus()
            let scenario = MockModeDetector.currentScenario
            print("Configuring mocks for scenario: \(scenario.rawValue)")

            // MARK: - Layer 1: Services with no dependencies

            let mockAPIClient = UITestMockAPIClient()
            mockAPIClient.configureForScenario(scenario)
            container.register(APIClientProtocol.self, instance: mockAPIClient)

            let mockLocalAnswerStorage = UITestMockLocalAnswerStorage()
            container.register(LocalAnswerStorageProtocol.self, instance: mockLocalAnswerStorage)

            // MARK: - Layer 2: Services depending on Layer 1

            let mockSecureStorage = UITestMockSecureStorage()
            if scenario == .loggedInWithHistory || scenario == .loggedInNoHistory || scenario == .testInProgress {
                mockSecureStorage.configureAuthenticated()
            }

            let mockNotificationService = UITestMockNotificationService()
            container.register(NotificationServiceProtocol.self, instance: mockNotificationService)

            // MARK: - Layer 3: AuthManager

            let mockAuthManager = UITestMockAuthManager()
            mockAuthManager.configureForScenario(scenario)
            container.register(AuthManagerProtocol.self, instance: mockAuthManager)

            // MARK: - Layer 4: NotificationManager

            let mockNotificationManager = UITestMockNotificationManager()
            mockNotificationManager.configureForScenario(scenario)
            container.register(NotificationManagerProtocol.self, instance: mockNotificationManager)

            print("[MockServiceConfiguration] All mock services registered for scenario: \(scenario.rawValue)")
        }
    }

#endif
