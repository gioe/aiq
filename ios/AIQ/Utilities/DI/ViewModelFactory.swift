import Foundation

/// Factory for creating ViewModels with resolved dependencies
///
/// This utility simplifies ViewModel creation in SwiftUI views by automatically
/// resolving dependencies from the ServiceContainer. It provides type-safe factory
/// methods for each ViewModel that requires dependency injection.
///
/// ## Usage in Views
///
/// Views accept a `ServiceContainer` parameter with a default value, enabling both
/// production use (with the shared container) and testing (with mock containers):
///
/// ```swift
/// struct DashboardView: View {
///     @StateObject private var viewModel: DashboardViewModel
///
///     /// - Parameter serviceContainer: Container for resolving dependencies.
///     ///   Defaults to the shared container for production use.
///     init(serviceContainer: ServiceContainer = .shared) {
///         let vm = ViewModelFactory.makeDashboardViewModel(container: serviceContainer)
///         _viewModel = StateObject(wrappedValue: vm)
///     }
/// }
/// ```
///
/// ## Testing
///
/// For UI tests, inject a mock container:
/// ```swift
/// let mockContainer = ServiceContainer()
/// mockContainer.register(APIClientProtocol.self) { MockAPIClient() }
/// let view = DashboardView(serviceContainer: mockContainer)
/// ```
enum ViewModelFactory {
    // MARK: - Dashboard

    /// Create a DashboardViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured DashboardViewModel instance
    @MainActor
    static func makeDashboardViewModel(container: ServiceContainer) -> DashboardViewModel {
        guard let apiClient = container.resolve(APIClientProtocol.self) else {
            fatalError("APIClientProtocol not registered in ServiceContainer")
        }
        return DashboardViewModel(apiClient: apiClient)
    }

    // MARK: - History

    /// Create a HistoryViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured HistoryViewModel instance
    @MainActor
    static func makeHistoryViewModel(container: ServiceContainer) -> HistoryViewModel {
        guard let apiClient = container.resolve(APIClientProtocol.self) else {
            fatalError("APIClientProtocol not registered in ServiceContainer")
        }
        return HistoryViewModel(apiClient: apiClient)
    }

    // MARK: - Test Taking

    /// Create a TestTakingViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured TestTakingViewModel instance
    @MainActor
    static func makeTestTakingViewModel(container: ServiceContainer) -> TestTakingViewModel {
        guard let apiClient = container.resolve(APIClientProtocol.self) else {
            fatalError("APIClientProtocol not registered in ServiceContainer")
        }
        guard let answerStorage = container.resolve(LocalAnswerStorageProtocol.self) else {
            fatalError("LocalAnswerStorageProtocol not registered in ServiceContainer")
        }
        return TestTakingViewModel(apiClient: apiClient, answerStorage: answerStorage)
    }

    // MARK: - Feedback

    /// Create a FeedbackViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured FeedbackViewModel instance
    @MainActor
    static func makeFeedbackViewModel(container: ServiceContainer) -> FeedbackViewModel {
        guard let apiClient = container.resolve(APIClientProtocol.self) else {
            fatalError("APIClientProtocol not registered in ServiceContainer")
        }
        let authManager = container.resolve(AuthManagerProtocol.self)
        return FeedbackViewModel(apiClient: apiClient, authManager: authManager)
    }

    // MARK: - Notification Settings

    /// Create a NotificationSettingsViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured NotificationSettingsViewModel instance
    @MainActor
    static func makeNotificationSettingsViewModel(container: ServiceContainer) -> NotificationSettingsViewModel {
        guard let notificationService = container.resolve(NotificationServiceProtocol.self) else {
            fatalError("NotificationServiceProtocol not registered in ServiceContainer")
        }
        guard let notificationManager = container.resolve(NotificationManagerProtocol.self) else {
            fatalError("NotificationManagerProtocol not registered in ServiceContainer")
        }
        return NotificationSettingsViewModel(
            notificationService: notificationService,
            notificationManager: notificationManager
        )
    }

    // MARK: - Login

    /// Create a LoginViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured LoginViewModel instance
    @MainActor
    static func makeLoginViewModel(container: ServiceContainer) -> LoginViewModel {
        guard let authManager = container.resolve(AuthManagerProtocol.self) else {
            fatalError("AuthManagerProtocol not registered in ServiceContainer")
        }
        return LoginViewModel(authManager: authManager)
    }

    // MARK: - Registration

    /// Create a RegistrationViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured RegistrationViewModel instance
    @MainActor
    static func makeRegistrationViewModel(container: ServiceContainer) -> RegistrationViewModel {
        guard let authManager = container.resolve(AuthManagerProtocol.self) else {
            fatalError("AuthManagerProtocol not registered in ServiceContainer")
        }
        return RegistrationViewModel(authManager: authManager)
    }

    // MARK: - Settings

    /// Create a SettingsViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured SettingsViewModel instance
    @MainActor
    static func makeSettingsViewModel(container: ServiceContainer) -> SettingsViewModel {
        guard let authManager = container.resolve(AuthManagerProtocol.self) else {
            fatalError("AuthManagerProtocol not registered in ServiceContainer")
        }
        return SettingsViewModel(authManager: authManager)
    }
}
