@testable import AIQ
import XCTest

/// Tests for ServiceConfiguration to ensure all services are properly registered
@MainActor
final class ServiceConfigurationTests: XCTestCase {
    var container: ServiceContainer!

    override func setUp() async throws {
        try await super.setUp()
        // Use the shared instance since the initializer is private
        container = ServiceContainer.shared
        // Reset before each test to start fresh
        container.reset()
        // Configure services for testing
        ServiceConfiguration.configureServices(container: container)
    }

    override func tearDown() async throws {
        // Reset after each test to clean up
        container.reset()
        // Re-configure services for the app (in case other tests need them)
        ServiceConfiguration.configureServices(container: container)
        container = nil
        try await super.tearDown()
    }

    // MARK: - Registration Tests

    func testAPIClientProtocolIsRegistered() {
        // Given & When
        let apiClient = container.resolve(APIClientProtocol.self)

        // Then
        XCTAssertNotNil(apiClient, "APIClientProtocol should be registered")
        XCTAssertTrue(apiClient is APIClient, "Resolved instance should be APIClient")
    }

    func testAuthManagerProtocolIsRegistered() {
        // Given & When
        let authManager = container.resolve(AuthManagerProtocol.self)

        // Then
        XCTAssertNotNil(authManager, "AuthManagerProtocol should be registered")
        XCTAssertTrue(authManager is AuthManager, "Resolved instance should be AuthManager")
    }

    func testNotificationServiceProtocolIsRegistered() {
        // Given & When
        let notificationService = container.resolve(NotificationServiceProtocol.self)

        // Then
        XCTAssertNotNil(notificationService, "NotificationServiceProtocol should be registered")
        XCTAssertTrue(notificationService is NotificationService, "Resolved instance should be NotificationService")
    }

    func testNotificationManagerProtocolIsRegistered() {
        // Given & When
        let notificationManager = container.resolve(NotificationManagerProtocol.self)

        // Then
        XCTAssertNotNil(notificationManager, "NotificationManagerProtocol should be registered")
        XCTAssertTrue(notificationManager is NotificationManager, "Resolved instance should be NotificationManager")
    }

    func testLocalAnswerStorageProtocolIsRegistered() {
        // Given & When
        let answerStorage = container.resolve(LocalAnswerStorageProtocol.self)

        // Then
        XCTAssertNotNil(answerStorage, "LocalAnswerStorageProtocol should be registered")
        XCTAssertTrue(answerStorage is LocalAnswerStorage, "Resolved instance should be LocalAnswerStorage")
    }

    // MARK: - Integration Tests

    func testAllServicesAreRegistered() {
        // Verify each expected service is registered
        XCTAssertTrue(
            container.isRegistered(APIClientProtocol.self),
            "APIClientProtocol should be registered in ServiceContainer"
        )
        XCTAssertTrue(
            container.isRegistered(AuthManagerProtocol.self),
            "AuthManagerProtocol should be registered in ServiceContainer"
        )
        XCTAssertTrue(
            container.isRegistered(NotificationServiceProtocol.self),
            "NotificationServiceProtocol should be registered in ServiceContainer"
        )
        XCTAssertTrue(
            container.isRegistered(NotificationManagerProtocol.self),
            "NotificationManagerProtocol should be registered in ServiceContainer"
        )
        XCTAssertTrue(
            container.isRegistered(LocalAnswerStorageProtocol.self),
            "LocalAnswerStorageProtocol should be registered in ServiceContainer"
        )
    }

    func testServiceResolutionReturnsSameInstance() {
        // Given: Services registered as singletons
        let apiClient1 = container.resolve(APIClientProtocol.self)
        let apiClient2 = container.resolve(APIClientProtocol.self)

        // Then: Should return the same singleton instance
        XCTAssertTrue(
            apiClient1 as AnyObject === apiClient2 as AnyObject,
            "Resolving APIClientProtocol multiple times should return the same singleton instance"
        )
    }

    func testContainerResetClearsRegistrations() {
        // Given: Container with registered services
        XCTAssertTrue(container.isRegistered(APIClientProtocol.self))

        // When: Reset is called
        container.reset()

        // Then: Services should no longer be registered
        XCTAssertFalse(
            container.isRegistered(APIClientProtocol.self),
            "Services should be cleared after reset"
        )
        XCTAssertNil(
            container.resolve(APIClientProtocol.self),
            "Resolving after reset should return nil"
        )
    }

    // MARK: - Configuration Validation Tests

    func testConfigurationCanBeCalledMultipleTimes() {
        // Given: Already configured container
        let apiClient1 = container.resolve(APIClientProtocol.self)

        // When: Configuration is called again (should overwrite)
        ServiceConfiguration.configureServices(container: container)
        let apiClient2 = container.resolve(APIClientProtocol.self)

        // Then: Should still resolve successfully
        XCTAssertNotNil(apiClient1, "First resolution should succeed")
        XCTAssertNotNil(apiClient2, "Second resolution should succeed after reconfiguration")
    }
}
