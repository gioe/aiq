import XCTest

@testable import AIQ

final class ServiceContainerTests: XCTestCase {
    var sut: ServiceContainer!

    override func setUp() {
        super.setUp()
        // Use the shared instance for all tests
        sut = ServiceContainer.shared
        // Reset to ensure test isolation
        sut.reset()
    }

    override func tearDown() {
        // Clean up after tests
        sut.reset()
        sut = nil
        super.tearDown()
    }

    // MARK: - Registration Tests

    func testRegister_ConcreteType() {
        // Given
        let expectedValue = "TestService"

        // When
        sut.register(String.self) {
            expectedValue
        }

        // Then
        XCTAssertTrue(sut.isRegistered(String.self), "String type should be registered")
    }

    func testRegister_ProtocolType() {
        // Given
        let mockService = MockTestService()

        // When
        sut.register(TestServiceProtocol.self) {
            mockService
        }

        // Then
        XCTAssertTrue(sut.isRegistered(TestServiceProtocol.self), "Protocol type should be registered")
    }

    func testRegister_OverwritesPreviousRegistration() {
        // Given
        sut.register(String.self) { "First" }

        // When - Register again with different factory
        sut.register(String.self) { "Second" }

        // Then
        let resolved = sut.resolve(String.self)
        XCTAssertEqual(resolved, "Second", "Should resolve to most recent registration")
    }

    // MARK: - Resolution Tests

    func testResolve_RegisteredType_ReturnsInstance() {
        // Given
        let expectedValue = "TestService"
        sut.register(String.self) {
            expectedValue
        }

        // When
        let resolved = sut.resolve(String.self)

        // Then
        XCTAssertEqual(resolved, expectedValue, "Should resolve to registered instance")
    }

    func testResolve_UnregisteredType_ReturnsNil() {
        // When
        let resolved = sut.resolve(String.self)

        // Then
        XCTAssertNil(resolved, "Should return nil for unregistered type")
    }

    func testResolve_ProtocolType_ReturnsConcreteInstance() {
        // Given
        let mockService = MockTestService()
        sut.register(TestServiceProtocol.self) {
            mockService
        }

        // When
        let resolved = sut.resolve(TestServiceProtocol.self)

        // Then
        XCTAssertNotNil(resolved, "Should resolve protocol to concrete instance")
        XCTAssertTrue(resolved is MockTestService, "Resolved instance should be MockTestService, got \(type(of: resolved))")
    }

    func testResolve_TransientLifetime_ReturnsNewInstanceEachTime() {
        // Given - Register factory that creates new instances
        sut.register(TransientService.self) {
            TransientService()
        }

        // When
        let instance1 = sut.resolve(TransientService.self)
        let instance2 = sut.resolve(TransientService.self)

        // Then
        XCTAssertNotNil(instance1, "First resolution should succeed")
        XCTAssertNotNil(instance2, "Second resolution should succeed")
        XCTAssertFalse(instance1 === instance2, "Should return different instances for transient lifetime")
    }

    func testResolve_SingletonLifetime_ReturnsSameInstance() {
        // Given - Register factory that returns singleton
        let sharedInstance = SingletonService.shared
        sut.register(SingletonService.self) {
            SingletonService.shared
        }

        // When
        let instance1 = sut.resolve(SingletonService.self)
        let instance2 = sut.resolve(SingletonService.self)

        // Then
        XCTAssertNotNil(instance1, "First resolution should succeed")
        XCTAssertNotNil(instance2, "Second resolution should succeed")
        XCTAssertTrue(instance1 === instance2, "Should return same instance for singleton lifetime")
        XCTAssertTrue(instance1 === sharedInstance, "Should return the singleton instance")
    }

    // MARK: - Thread Safety Tests

    func testConcurrentRegistration_ThreadSafety() {
        // VERIFIED: Implementation uses NSLock to synchronize access to factories dictionary,
        // so concurrent registration tests are valid

        // Given
        let iterations = 100
        let expectation = expectation(description: "All registrations complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Register from multiple threads concurrently
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                self.sut.register(String.self) {
                    "Service-\(i)"
                }
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 5.0)
        XCTAssertTrue(sut.isRegistered(String.self), "String type should be registered after concurrent operations")
    }

    func testConcurrentResolution_ThreadSafety() {
        // VERIFIED: Implementation uses NSLock to synchronize access to factories dictionary,
        // so concurrent resolution tests are valid

        // Given
        sut.register(String.self) { "TestService" }

        let iterations = 100
        let expectation = expectation(description: "All resolutions complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Resolve from multiple threads concurrently
        for _ in 0 ..< iterations {
            DispatchQueue.global().async {
                let resolved = self.sut.resolve(String.self)
                XCTAssertNotNil(resolved, "Should resolve successfully from concurrent thread")
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 5.0)
    }

    func testConcurrentRegistrationAndResolution_ThreadSafety() {
        // VERIFIED: Implementation uses NSLock to synchronize access to factories dictionary,
        // so mixed concurrent operations are valid

        // Given
        let iterations = 50
        let expectation = expectation(description: "All operations complete")
        expectation.expectedFulfillmentCount = iterations * 2 // Register + resolve for each iteration

        // When - Mix registration and resolution from multiple threads
        for i in 0 ..< iterations {
            // Registration thread
            DispatchQueue.global().async {
                self.sut.register(Int.self) {
                    i
                }
                expectation.fulfill()
            }

            // Resolution thread
            DispatchQueue.global().async {
                _ = self.sut.resolve(Int.self)
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 5.0)
        XCTAssertTrue(sut.isRegistered(Int.self), "Int type should be registered after concurrent operations")
    }

    // MARK: - isRegistered Tests

    func testIsRegistered_RegisteredType_ReturnsTrue() {
        // Given
        sut.register(String.self) { "Test" }

        // When
        let isRegistered = sut.isRegistered(String.self)

        // Then
        XCTAssertTrue(isRegistered, "Should return true for registered type")
    }

    func testIsRegistered_UnregisteredType_ReturnsFalse() {
        // When
        let isRegistered = sut.isRegistered(String.self)

        // Then
        XCTAssertFalse(isRegistered, "Should return false for unregistered type")
    }

    // MARK: - Reset Tests

    func testReset_ClearsAllRegistrations() {
        // Given
        sut.register(String.self) { "Test1" }
        sut.register(Int.self) { 42 }
        sut.register(TestServiceProtocol.self) { MockTestService() }

        // When
        sut.reset()

        // Then
        XCTAssertFalse(sut.isRegistered(String.self), "String should not be registered after reset")
        XCTAssertFalse(sut.isRegistered(Int.self), "Int should not be registered after reset")
        XCTAssertFalse(sut.isRegistered(TestServiceProtocol.self), "Protocol should not be registered after reset")

        XCTAssertNil(sut.resolve(String.self), "Should not resolve String after reset")
        XCTAssertNil(sut.resolve(Int.self), "Should not resolve Int after reset")
        XCTAssertNil(sut.resolve(TestServiceProtocol.self), "Should not resolve Protocol after reset")
    }

    // MARK: - Shared Instance Tests

    func testSharedInstance_PersistsRegistrations() {
        // Given
        sut.register(String.self) { "SharedTest" }

        // When
        let resolved = sut.resolve(String.self)

        // Then
        XCTAssertEqual(resolved, "SharedTest", "Should persist registrations across resolutions")
    }

    // MARK: - Complex Type Tests

    func testRegisterAndResolve_MultipleProtocols() {
        // Given
        let mockService1 = MockTestService()
        let mockService2 = AnotherMockService()

        sut.register(TestServiceProtocol.self) { mockService1 }
        sut.register(AnotherServiceProtocol.self) { mockService2 }

        // When
        let resolved1 = sut.resolve(TestServiceProtocol.self)
        let resolved2 = sut.resolve(AnotherServiceProtocol.self)

        // Then
        XCTAssertNotNil(resolved1, "Should resolve first protocol")
        XCTAssertNotNil(resolved2, "Should resolve second protocol")
        XCTAssertTrue(resolved1 is MockTestService, "First service should be MockTestService, got \(type(of: resolved1))")
        XCTAssertTrue(resolved2 is AnotherMockService, "Second service should be AnotherMockService, got \(type(of: resolved2))")
    }

    func testRegisterAndResolve_ClassAndProtocol() {
        // Given
        let mockService = MockTestService()

        // Register same instance under both concrete type and protocol
        sut.register(MockTestService.self) { mockService }
        sut.register(TestServiceProtocol.self) { mockService }

        // When
        let resolvedClass = sut.resolve(MockTestService.self)
        let resolvedProtocol = sut.resolve(TestServiceProtocol.self)

        // Then
        XCTAssertNotNil(resolvedClass, "Should resolve concrete class")
        XCTAssertNotNil(resolvedProtocol, "Should resolve protocol")
        XCTAssertTrue(resolvedClass === mockService, "Should resolve to same instance for concrete type")
        XCTAssertTrue(resolvedProtocol as AnyObject === mockService, "Should resolve to same instance for protocol")
    }
}

// MARK: - Test Helpers

/// Protocol for testing protocol-based injection
protocol TestServiceProtocol: AnyObject {
    func doSomething()
}

/// Mock service implementing TestServiceProtocol
final class MockTestService: TestServiceProtocol {
    func doSomething() {}
}

/// Another protocol for testing multiple protocol registration
protocol AnotherServiceProtocol: AnyObject {
    func doSomethingElse()
}

/// Mock service implementing AnotherServiceProtocol
final class AnotherMockService: AnotherServiceProtocol {
    func doSomethingElse() {}
}

/// Service with transient lifetime (new instance each time)
final class TransientService {
    let id = UUID()
}

/// Service with singleton lifetime
final class SingletonService {
    static let shared = SingletonService()
    private init() {}
}
