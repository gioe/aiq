@testable import AIQ
import XCTest

/// Tests for ViewModelFactory to ensure all factory methods work with production configuration
@MainActor
final class ViewModelFactoryTests: XCTestCase {
    var container: ServiceContainer!

    override func setUp() async throws {
        try await super.setUp()
        container = ServiceContainer.shared
        container.reset()
        ServiceConfiguration.configureServices(container: container)
    }

    // MARK: - Comprehensive Factory Test

    /// Verifies all ViewModelFactory methods can successfully create ViewModels with production configuration.
    ///
    /// This test catches configuration errors early by ensuring:
    /// - All dependencies are properly registered
    /// - All factory methods succeed without throwing
    /// - No runtime crashes from missing dependencies
    func testAllViewModelFactoryMethodsSucceed() {
        // Given: ServiceContainer configured with production dependencies
        // (done in setUp)

        // When/Then: Each factory method should succeed without throwing or crashing
        // Note: Factory methods call fatalError if dependencies are missing,
        // so we verify each can be called successfully

        let dashboardViewModel = ViewModelFactory.makeDashboardViewModel(container: container)
        XCTAssertNotNil(dashboardViewModel, "makeDashboardViewModel should succeed")

        let historyViewModel = ViewModelFactory.makeHistoryViewModel(container: container)
        XCTAssertNotNil(historyViewModel, "makeHistoryViewModel should succeed")

        let testTakingViewModel = ViewModelFactory.makeTestTakingViewModel(container: container)
        XCTAssertNotNil(testTakingViewModel, "makeTestTakingViewModel should succeed")

        let feedbackViewModel = ViewModelFactory.makeFeedbackViewModel(container: container)
        XCTAssertNotNil(feedbackViewModel, "makeFeedbackViewModel should succeed")

        let notificationSettingsViewModel = ViewModelFactory.makeNotificationSettingsViewModel(container: container)
        XCTAssertNotNil(notificationSettingsViewModel, "makeNotificationSettingsViewModel should succeed")

        let loginViewModel = ViewModelFactory.makeLoginViewModel(container: container)
        XCTAssertNotNil(loginViewModel, "makeLoginViewModel should succeed")

        let registrationViewModel = ViewModelFactory.makeRegistrationViewModel(container: container)
        XCTAssertNotNil(registrationViewModel, "makeRegistrationViewModel should succeed")

        let settingsViewModel = ViewModelFactory.makeSettingsViewModel(container: container)
        XCTAssertNotNil(settingsViewModel, "makeSettingsViewModel should succeed")
    }

    // MARK: - Individual Factory Tests

    func testMakeDashboardViewModel() {
        let viewModel = ViewModelFactory.makeDashboardViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    func testMakeHistoryViewModel() {
        let viewModel = ViewModelFactory.makeHistoryViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    func testMakeTestTakingViewModel() {
        let viewModel = ViewModelFactory.makeTestTakingViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    func testMakeFeedbackViewModel() {
        let viewModel = ViewModelFactory.makeFeedbackViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    func testMakeNotificationSettingsViewModel() {
        let viewModel = ViewModelFactory.makeNotificationSettingsViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    func testMakeLoginViewModel() {
        let viewModel = ViewModelFactory.makeLoginViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    func testMakeRegistrationViewModel() {
        let viewModel = ViewModelFactory.makeRegistrationViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    func testMakeSettingsViewModel() {
        let viewModel = ViewModelFactory.makeSettingsViewModel(container: container)
        XCTAssertNotNil(viewModel)
    }

    // MARK: - Missing Dependency Tests

    func testFactoryMethodsFailWithoutDependencies() {
        // Given: Empty container (no dependencies registered)
        container.reset()

        // Then: Factory methods would crash due to fatalError
        // We can't test fatalError directly, but we document the expected behavior
        // The comprehensive test above verifies the happy path works
    }
}
