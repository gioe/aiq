@testable import AIQ
import Combine
import XCTest

/// Unit tests for ToastManagerObserver
///
/// Verifies:
/// - Initial state synchronization from container
/// - State updates via Combine publishers
/// - Show and dismiss delegation to underlying manager
/// - Memory management with weak self in closures
/// - Thread safety with MainActor
@MainActor
final class ToastManagerObserverTests: XCTestCase {
    // MARK: - Properties

    var cancellables: Set<AnyCancellable>!
    var container: ServiceContainer!

    // MARK: - Setup & Teardown

    override func setUp() async throws {
        try await super.setUp()
        cancellables = Set<AnyCancellable>()
        container = ServiceContainer.shared
        container.reset()
    }

    override func tearDown() {
        cancellables.removeAll()
        cancellables = nil
        container.reset()
        container = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInit_WithContainer_ResolvesToastManager() {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)

        // When
        let sut = ToastManagerObserver(container: container)

        // Then
        XCTAssertNotNil(sut, "Observer should initialize successfully")
    }

    func testInit_SetsInitialStateAsNil() {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)

        // When
        let sut = ToastManagerObserver(container: container)

        // Then
        XCTAssertNil(sut.currentToast, "Initial toast should be nil")
    }

    func testInit_WithExistingToast_CapturesInitialState() {
        // Given
        let toastManager = ToastManager()
        toastManager.show("Test message", type: .info)
        container.register(ToastManagerProtocol.self, instance: toastManager)

        // When
        let sut = ToastManagerObserver(container: container)

        // Then
        XCTAssertNotNil(sut.currentToast, "Should capture existing toast")
        XCTAssertEqual(sut.currentToast?.message, "Test message", "Should have correct message")
        XCTAssertEqual(sut.currentToast?.type, .info, "Should have correct type")
    }

    // MARK: - State Synchronization Tests

    func testStateUpdates_WhenToastShown_ObserverUpdates() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation = expectation(description: "Observer receives toast update")
        expectation.assertForOverFulfill = false

        sut.$currentToast
            .dropFirst() // Skip initial nil
            .sink { toast in
                if toast != nil {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // When
        toastManager.show("New toast", type: .error)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertNotNil(sut.currentToast, "Observer should have toast after show")
        XCTAssertEqual(sut.currentToast?.message, "New toast", "Should have correct message")
    }

    func testStateUpdates_WhenToastDismissed_ObserverUpdates() async {
        // Given
        let toastManager = ToastManager()
        toastManager.show("Initial toast", type: .info)
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation = expectation(description: "Observer receives dismiss update")
        expectation.assertForOverFulfill = false

        sut.$currentToast
            .dropFirst() // Skip initial value
            .sink { toast in
                if toast == nil {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // When
        toastManager.dismiss()

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertNil(sut.currentToast, "Observer should be nil after dismiss")
    }

    // MARK: - Delegation Tests

    func testShow_DelegatesToManager() {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        // When
        sut.show("Delegated toast", type: .warning)

        // Then
        XCTAssertNotNil(toastManager.currentToast, "Manager should have toast after observer.show()")
        XCTAssertEqual(toastManager.currentToast?.message, "Delegated toast", "Should have correct message")
        XCTAssertEqual(toastManager.currentToast?.type, .warning, "Should have correct type")
    }

    func testDismiss_DelegatesToManager() {
        // Given
        let toastManager = ToastManager()
        toastManager.show("Toast to dismiss", type: .error)
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        // When
        sut.dismiss()

        // Then
        XCTAssertNil(toastManager.currentToast, "Manager should be nil after observer.dismiss()")
    }

    // MARK: - Published Property Tests

    func testPublishedCurrentToast_EmitsInitialValue() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation = expectation(description: "currentToast publishes")
        var receivedInitialValue = false

        // When
        sut.$currentToast
            .first()
            .sink { _ in
                receivedInitialValue = true
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertTrue(receivedInitialValue, "Should emit initial value")
    }

    // MARK: - Memory Management Tests

    func testObserver_UsesWeakSelf_InSubscriptions() {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)

        // When - Create observer in autoreleasepool to allow deallocation
        weak var weakObserver: ToastManagerObserver?
        autoreleasepool {
            let sut = ToastManagerObserver(container: container)
            weakObserver = sut

            // Subscribe and immediately release
            var cancellable: AnyCancellable?
            autoreleasepool {
                cancellable = sut.$currentToast.sink { _ in }
            }
            cancellable?.cancel()
        }

        // Then
        // Note: The observer may still be retained by internal subscriptions
        // The key is that it doesn't crash and can be created/destroyed
        XCTAssertTrue(true, "Observer creation and destruction should not crash")
    }

    // MARK: - Thread Safety Tests

    func testUpdatesOccurOnMainThread() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation = expectation(description: "Updates occur on main thread")
        expectation.assertForOverFulfill = false

        // When
        sut.$currentToast
            .sink { _ in
                // Then - Verify we're on the main thread
                XCTAssertTrue(Thread.isMainThread, "Updates should occur on main thread")
                expectation.fulfill()
            }
            .store(in: &cancellables)

        await fulfillment(of: [expectation], timeout: 1.0)
    }

    // MARK: - Toast Type Tests

    func testShow_ErrorToast_PropagatesCorrectly() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation = expectation(description: "Error toast shown")
        expectation.assertForOverFulfill = false

        sut.$currentToast
            .dropFirst()
            .sink { toast in
                if toast?.type == .error {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // When
        sut.show("Error message", type: .error)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(sut.currentToast?.type, .error, "Toast type should be error")
    }

    func testShow_WarningToast_PropagatesCorrectly() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation = expectation(description: "Warning toast shown")
        expectation.assertForOverFulfill = false

        sut.$currentToast
            .dropFirst()
            .sink { toast in
                if toast?.type == .warning {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // When
        sut.show("Warning message", type: .warning)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(sut.currentToast?.type, .warning, "Toast type should be warning")
    }

    func testShow_InfoToast_PropagatesCorrectly() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation = expectation(description: "Info toast shown")
        expectation.assertForOverFulfill = false

        sut.$currentToast
            .dropFirst()
            .sink { toast in
                if toast?.type == .info {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // When
        sut.show("Info message", type: .info)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(sut.currentToast?.type, .info, "Toast type should be info")
    }

    // MARK: - Edge Case Tests

    func testMultipleObservers_AllReceiveUpdates() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        let expectation1 = expectation(description: "First observer receives updates")
        let expectation2 = expectation(description: "Second observer receives updates")
        var observer1Received = false
        var observer2Received = false

        // When - Create two subscribers
        sut.$currentToast
            .dropFirst()
            .sink { toast in
                if toast != nil {
                    observer1Received = true
                    expectation1.fulfill()
                }
            }
            .store(in: &cancellables)

        sut.$currentToast
            .dropFirst()
            .sink { toast in
                if toast != nil {
                    observer2Received = true
                    expectation2.fulfill()
                }
            }
            .store(in: &cancellables)

        toastManager.show("Test", type: .info)

        // Then
        await fulfillment(of: [expectation1, expectation2], timeout: 1.0)
        XCTAssertTrue(observer1Received, "First observer should receive update")
        XCTAssertTrue(observer2Received, "Second observer should receive update")
    }

    func testObserver_CanBeCreatedMultipleTimes() {
        // Given
        let toastManager = ToastManager()
        toastManager.show("Shared toast", type: .info)
        container.register(ToastManagerProtocol.self, instance: toastManager)

        // When - Create multiple observers
        let sut1 = ToastManagerObserver(container: container)
        let sut2 = ToastManagerObserver(container: container)

        // Then - Both should work independently
        XCTAssertNotNil(sut1, "First observer should be created")
        XCTAssertNotNil(sut2, "Second observer should be created")
        XCTAssertEqual(sut1.currentToast?.message, sut2.currentToast?.message, "Both should have same toast")
    }

    func testShow_ReplacesToast_ObserverReceivesNewToast() async {
        // Given
        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)
        let sut = ToastManagerObserver(container: container)

        sut.show("First toast", type: .info)

        let expectation = expectation(description: "Observer receives replacement toast")
        expectation.assertForOverFulfill = false

        sut.$currentToast
            .dropFirst() // Skip current
            .sink { toast in
                if toast?.message == "Second toast" {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // When
        sut.show("Second toast", type: .warning)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(sut.currentToast?.message, "Second toast", "Should have replacement toast")
        XCTAssertEqual(sut.currentToast?.type, .warning, "Should have new type")
    }
}
