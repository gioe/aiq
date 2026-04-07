import AIQSharedKit
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
/// mockContainer.register(OpenAPIServiceProtocol.self) { MockOpenAPIService() }
/// let view = DashboardView(serviceContainer: mockContainer)
/// ```
enum ViewModelFactory {
    // MARK: - Tab-Level ViewModel Cache

    /// Cached tab-level ViewModels to prevent re-creation on tab switch.
    /// SwiftUI's TabView can destroy and recreate child view state when switching tabs,
    /// causing @StateObject to create new ViewModel instances. Caching here ensures the
    /// same instance is returned regardless of how many times the factory is called.
    @MainActor private static var cachedDashboardVM: DashboardViewModel?
    @MainActor private static var cachedHistoryVM: HistoryViewModel?
    @MainActor private static var cachedSettingsVM: SettingsViewModel?

    /// Reset cached tab-level ViewModels. Call on logout or account deletion
    /// so that re-login creates fresh instances with no stale state.
    @MainActor
    static func resetTabViewModels() {
        cachedDashboardVM = nil
        cachedHistoryVM = nil
        cachedSettingsVM = nil
    }

    // MARK: - Dashboard

    /// Create or return a cached DashboardViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured DashboardViewModel instance
    @MainActor
    static func makeDashboardViewModel(container: ServiceContainer) -> DashboardViewModel {
        if let cached = cachedDashboardVM { return cached }
        let apiService: OpenAPIServiceProtocol = container.resolve()
        let vm = DashboardViewModel(apiService: apiService)
        cachedDashboardVM = vm
        return vm
    }

    // MARK: - History

    /// Create or return a cached HistoryViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured HistoryViewModel instance
    @MainActor
    static func makeHistoryViewModel(container: ServiceContainer) -> HistoryViewModel {
        if let cached = cachedHistoryVM { return cached }
        let apiService: OpenAPIServiceProtocol = container.resolve()
        let preferencesStorage: HistoryPreferencesStorageProtocol = container.resolve()
        let vm = HistoryViewModel(apiService: apiService, preferencesStorage: preferencesStorage)
        cachedHistoryVM = vm
        return vm
    }

    // MARK: - Test Taking

    /// Create a TestTakingViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured TestTakingViewModel instance
    @MainActor
    static func makeTestTakingViewModel(container: ServiceContainer) -> TestTakingViewModel {
        let apiService: OpenAPIServiceProtocol = container.resolve()
        let answerStorage: LocalAnswerStorageProtocol = container.resolve()
        return TestTakingViewModel(apiService: apiService, answerStorage: answerStorage)
    }

    // MARK: - Feedback

    /// Create a FeedbackViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured FeedbackViewModel instance
    @MainActor
    static func makeFeedbackViewModel(container: ServiceContainer) -> FeedbackViewModel {
        let apiService: OpenAPIServiceProtocol = container.resolve()
        let authManager: AuthManagerProtocol? = container.resolveOptional()
        return FeedbackViewModel(apiService: apiService, authManager: authManager)
    }

    // MARK: - Notification Settings

    /// Create a NotificationSettingsViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured NotificationSettingsViewModel instance
    @MainActor
    static func makeNotificationSettingsViewModel(container: ServiceContainer) -> NotificationSettingsViewModel {
        let notificationService: NotificationServiceProtocol = container.resolve()
        let notificationManager: NotificationManagerProtocol = container.resolve()
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
        let authManager: AuthManagerProtocol = container.resolve()
        return LoginViewModel(authManager: authManager)
    }

    // MARK: - Registration

    /// Create a RegistrationViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured RegistrationViewModel instance
    @MainActor
    static func makeRegistrationViewModel(container: ServiceContainer) -> RegistrationViewModel {
        let authManager: AuthManagerProtocol = container.resolve()
        return RegistrationViewModel(authManager: authManager)
    }

    // MARK: - Settings

    /// Create or return a cached SettingsViewModel with resolved dependencies
    /// - Parameter container: ServiceContainer to resolve dependencies from
    /// - Returns: Configured SettingsViewModel instance
    @MainActor
    static func makeSettingsViewModel(container: ServiceContainer) -> SettingsViewModel {
        if let cached = cachedSettingsVM { return cached }
        let authManager: AuthManagerProtocol = container.resolve()
        let biometricAuthManager: BiometricAuthManagerProtocol = container.resolve()
        let biometricPreferenceStorage: BiometricPreferenceStorageProtocol = container.resolve()
        let vm = SettingsViewModel(
            authManager: authManager,
            biometricAuthManager: biometricAuthManager,
            biometricPreferenceStorage: biometricPreferenceStorage
        )
        cachedSettingsVM = vm
        return vm
    }
}
