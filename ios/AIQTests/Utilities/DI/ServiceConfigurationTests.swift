@testable import AIQ
import XCTest

/// Tests for ServiceConfiguration to ensure all services are properly registered
@MainActor
final class ServiceConfigurationTests: XCTestCase {
    var container: ServiceContainer!

    override func setUp() async throws {
        try await super.setUp()
        container = ServiceContainer()
        ServiceConfiguration.configureServices(container: container)
    }

    override func tearDown() async throws {
        container = nil
        try await super.tearDown()
    }

    // MARK: - Registration Tests

    func testOpenAPIServiceProtocolIsRegistered() {
        // Given & When
        let apiService = container.resolve(OpenAPIServiceProtocol.self)

        // Then
        XCTAssertNotNil(apiService, "OpenAPIServiceProtocol should be registered")
        XCTAssertTrue(apiService is OpenAPIService, "Resolved instance should be OpenAPIService")
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

    func testHapticManagerProtocolIsRegistered() {
        // Given & When
        let hapticManager = container.resolve(HapticManagerProtocol.self)

        // Then
        XCTAssertNotNil(hapticManager, "HapticManagerProtocol should be registered")
        XCTAssertTrue(hapticManager is HapticManager, "Resolved instance should be HapticManager")
    }

    func testToastManagerProtocolIsRegistered() {
        // Given & When
        let toastManager = container.resolve(ToastManagerProtocol.self)

        // Then
        XCTAssertNotNil(toastManager, "ToastManagerProtocol should be registered")
        XCTAssertTrue(toastManager is ToastManager, "Resolved instance should be ToastManager")
    }

    // MARK: - Integration Tests

    func testAllServicesAreRegistered() {
        // Verify each expected service is registered
        XCTAssertTrue(
            container.isRegistered(OpenAPIServiceProtocol.self),
            "OpenAPIServiceProtocol should be registered in ServiceContainer"
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
        let apiService1 = container.resolve(OpenAPIServiceProtocol.self)
        let apiService2 = container.resolve(OpenAPIServiceProtocol.self)

        // Then: Should return the same singleton instance
        XCTAssertTrue(
            apiService1 as AnyObject === apiService2 as AnyObject,
            "Resolving OpenAPIServiceProtocol multiple times should return the same singleton instance"
        )
    }

    func testContainerResetClearsRegistrations() {
        // Given: Container with registered services
        XCTAssertTrue(container.isRegistered(OpenAPIServiceProtocol.self))

        // When: Reset is called
        container.reset()

        // Then: Services should no longer be registered
        XCTAssertFalse(
            container.isRegistered(OpenAPIServiceProtocol.self),
            "Services should be cleared after reset"
        )
        XCTAssertNil(
            container.resolve(OpenAPIServiceProtocol.self),
            "Resolving after reset should return nil"
        )
    }

    // MARK: - Configuration Validation Tests

    func testConfigurationCanBeCalledMultipleTimes() {
        // Given: Already configured container
        let apiService1 = container.resolve(OpenAPIServiceProtocol.self)

        // When: Configuration is called again (should overwrite)
        ServiceConfiguration.configureServices(container: container)
        let apiService2 = container.resolve(OpenAPIServiceProtocol.self)

        // Then: Should still resolve successfully
        XCTAssertNotNil(apiService1, "First resolution should succeed")
        XCTAssertNotNil(apiService2, "Second resolution should succeed after reconfiguration")
    }
}
