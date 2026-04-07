@testable import AIQ
import AIQSharedKit
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
        let apiService: OpenAPIServiceProtocol = container.resolve()

        // Then
        XCTAssertTrue(apiService is OpenAPIService, "Resolved instance should be OpenAPIService")
    }

    func testAuthManagerProtocolIsRegistered() {
        // Given & When
        let authManager: AuthManagerProtocol = container.resolve()

        // Then
        XCTAssertTrue(authManager is AuthManager, "Resolved instance should be AuthManager")
    }

    func testNotificationServiceProtocolIsRegistered() {
        // Given & When
        let notificationService: NotificationServiceProtocol = container.resolve()

        // Then
        XCTAssertTrue(notificationService is NotificationService, "Resolved instance should be NotificationService")
    }

    func testNotificationManagerProtocolIsRegistered() {
        // Given & When
        let notificationManager: NotificationManagerProtocol = container.resolve()

        // Then
        XCTAssertTrue(notificationManager is NotificationManager, "Resolved instance should be NotificationManager")
    }

    func testLocalAnswerStorageProtocolIsRegistered() {
        // Given & When
        let answerStorage: LocalAnswerStorageProtocol = container.resolve()

        // Then
        XCTAssertTrue(answerStorage is LocalAnswerStorage, "Resolved instance should be LocalAnswerStorage")
    }

    func testHapticManagerProtocolIsRegistered() {
        // Given & When
        let hapticManager: HapticManagerProtocol = container.resolve()

        // Then
        XCTAssertTrue(hapticManager is HapticManager, "Resolved instance should be HapticManager")
    }

    func testToastManagerProtocolIsRegistered() {
        // Given & When
        let toastManager: any ToastManagerProtocol = container.resolve()

        // Then
        XCTAssertTrue(toastManager is ToastManager, "Resolved instance should be ToastManager")
    }

    // MARK: - Integration Tests

    func testAllServicesAreRegistered() {
        // Verify each expected service resolves without fatal error
        XCTAssertNotNil(
            container.resolveOptional(OpenAPIServiceProtocol.self),
            "OpenAPIServiceProtocol should be registered in ServiceContainer"
        )
        XCTAssertNotNil(
            container.resolveOptional(AuthManagerProtocol.self),
            "AuthManagerProtocol should be registered in ServiceContainer"
        )
        XCTAssertNotNil(
            container.resolveOptional(NotificationServiceProtocol.self),
            "NotificationServiceProtocol should be registered in ServiceContainer"
        )
        XCTAssertNotNil(
            container.resolveOptional(NotificationManagerProtocol.self),
            "NotificationManagerProtocol should be registered in ServiceContainer"
        )
        XCTAssertNotNil(
            container.resolveOptional(LocalAnswerStorageProtocol.self),
            "LocalAnswerStorageProtocol should be registered in ServiceContainer"
        )
    }

    func testServiceResolutionReturnsSameInstance() {
        // Given: Services registered as singletons (appLevel scope)
        let apiService1: OpenAPIServiceProtocol = container.resolve()
        let apiService2: OpenAPIServiceProtocol = container.resolve()

        // Then: Should return the same singleton instance
        XCTAssertTrue(
            apiService1 as AnyObject === apiService2 as AnyObject,
            "Resolving OpenAPIServiceProtocol multiple times should return the same singleton instance"
        )
    }

    func testContainerResetClearsRegistrations() {
        // Given: Container with registered services
        XCTAssertNotNil(container.resolveOptional(OpenAPIServiceProtocol.self))

        // When: Reset is called
        container.reset()

        // Then: Services should no longer be registered
        XCTAssertNil(
            container.resolveOptional(OpenAPIServiceProtocol.self),
            "Services should be cleared after reset"
        )
    }

    // MARK: - Configuration Validation Tests

    func testConfigurationCanBeCalledMultipleTimes() {
        // Given: Already configured container
        let apiService1: OpenAPIServiceProtocol = container.resolve()

        // When: Configuration is called again (should overwrite)
        ServiceConfiguration.configureServices(container: container)
        let apiService2: OpenAPIServiceProtocol = container.resolve()

        // Then: Should still resolve successfully
        XCTAssertNotNil(apiService1, "First resolution should succeed")
        XCTAssertNotNil(apiService2, "Second resolution should succeed after reconfiguration")
    }
}
