@testable import AIQ
import XCTest

@MainActor
final class HapticManagerTests: XCTestCase {
    var sut: HapticManager!

    override func setUp() async throws {
        try await super.setUp()
        sut = HapticManager()
    }

    override func tearDown() {
        sut = nil
        super.tearDown()
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
}
