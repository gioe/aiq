@testable import AIQ
import XCTest

@MainActor
final class HapticManagerTests: XCTestCase {
    var sut: HapticManager!

    override func setUp() async throws {
        try await super.setUp()
        sut = HapticManager()
    }

    // MARK: - Initialization Tests

    func testSharedInstance_ReturnsSameInstance() {
        // Given
        let instance1 = HapticManager.shared
        let instance2 = HapticManager.shared

        // Then
        XCTAssertTrue(instance1 === instance2, "Shared instance should return the same instance")
    }

    func testInit_CreatesValidInstance() {
        // Then
        XCTAssertNotNil(sut, "HapticManager should initialize without errors")
    }

    // MARK: - Trigger Tests

    func testTrigger_Success_DoesNotCrash() {
        // When/Then - should not crash
        sut.trigger(.success)
    }

    func testTrigger_Error_DoesNotCrash() {
        // When/Then - should not crash
        sut.trigger(.error)
    }

    func testTrigger_Warning_DoesNotCrash() {
        // When/Then - should not crash
        sut.trigger(.warning)
    }

    func testTrigger_Selection_DoesNotCrash() {
        // When/Then - should not crash
        sut.trigger(.selection)
    }

    func testTrigger_Light_DoesNotCrash() {
        // When/Then - should not crash
        sut.trigger(.light)
    }

    func testTrigger_Medium_DoesNotCrash() {
        // When/Then - should not crash
        sut.trigger(.medium)
    }

    func testTrigger_Heavy_DoesNotCrash() {
        // When/Then - should not crash
        sut.trigger(.heavy)
    }

    // MARK: - Prepare Tests

    func testPrepare_DoesNotCrash() {
        // When/Then - should not crash
        sut.prepare()
    }

    func testPrepare_CalledMultipleTimes_DoesNotCrash() {
        // When/Then - should not crash when called multiple times
        sut.prepare()
        sut.prepare()
        sut.prepare()
    }

    // MARK: - Protocol Conformance Tests

    func testConformsToProtocol() {
        // Given
        let manager: HapticManagerProtocol = sut

        // Then
        XCTAssertNotNil(manager, "HapticManager should conform to HapticManagerProtocol")
    }

    // MARK: - HapticType Tests

    func testHapticType_AllCasesExist() {
        // Verify all expected haptic types exist by using them
        let types: [HapticType] = [
            .success,
            .error,
            .warning,
            .selection,
            .light,
            .medium,
            .heavy
        ]

        // Then
        XCTAssertEqual(types.count, 7, "Should have 7 haptic types")
    }

    func testHapticType_SuccessDescription() {
        // Given
        let type = HapticType.success

        // Then
        XCTAssertEqual(String(describing: type), "success")
    }

    func testHapticType_ErrorDescription() {
        // Given
        let type = HapticType.error

        // Then
        XCTAssertEqual(String(describing: type), "error")
    }

    func testHapticType_WarningDescription() {
        // Given
        let type = HapticType.warning

        // Then
        XCTAssertEqual(String(describing: type), "warning")
    }

    func testHapticType_SelectionDescription() {
        // Given
        let type = HapticType.selection

        // Then
        XCTAssertEqual(String(describing: type), "selection")
    }

    // MARK: - All Haptic Types Handled Tests

    func testTrigger_AllHapticTypes_DoesNotCrash() {
        // Given - all haptic types
        let allTypes: [HapticType] = [
            .success,
            .error,
            .warning,
            .selection,
            .light,
            .medium,
            .heavy
        ]

        // When/Then - triggering each type should not crash
        for type in allTypes {
            sut.trigger(type)
        }
    }

    // MARK: - Concurrent Trigger Tests

    func testTrigger_ConcurrentCalls_DoesNotCrash() async {
        // Given - multiple concurrent trigger tasks
        let types: [HapticType] = [.success, .error, .warning, .selection, .light, .medium, .heavy]

        // When/Then - concurrent triggers should not crash
        await withTaskGroup(of: Void.self) { group in
            for type in types {
                group.addTask { @MainActor in
                    self.sut.trigger(type)
                }
            }
        }
    }

    // MARK: - Prepare Then Trigger Tests

    func testTrigger_AfterPrepare_DoesNotCrash() {
        // Given
        sut.prepare()

        // When/Then - triggering after prepare should not crash
        sut.trigger(.success)
        sut.trigger(.selection)
        sut.trigger(.medium)
    }

    // MARK: - Mock Tests

    func testMock_TracksTriggeredType() {
        // Given
        let mock = UITestMockHapticManager()

        // When
        mock.trigger(.success)

        // Then
        XCTAssertEqual(mock.lastTriggeredType, .success)
        XCTAssertEqual(mock.triggerCallCount, 1)
    }

    func testMock_TracksPrepareCount() {
        // Given
        let mock = UITestMockHapticManager()

        // When
        mock.prepare()
        mock.prepare()

        // Then
        XCTAssertEqual(mock.prepareCallCount, 2)
    }

    func testMock_Reset_ClearsState() {
        // Given
        let mock = UITestMockHapticManager()
        mock.trigger(.error)
        mock.prepare()

        // When
        mock.reset()

        // Then
        XCTAssertNil(mock.lastTriggeredType)
        XCTAssertEqual(mock.triggerCallCount, 0)
        XCTAssertEqual(mock.prepareCallCount, 0)
    }
}
