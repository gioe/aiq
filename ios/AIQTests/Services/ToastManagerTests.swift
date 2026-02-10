@testable import AIQ
import XCTest

@MainActor
final class ToastManagerTests: XCTestCase {
    var sut: ToastManager!

    override func setUp() async throws {
        try await super.setUp()
        sut = ToastManager.shared
        // Ensure clean state
        sut.dismiss()
    }

    override func tearDown() {
        sut.dismiss()
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testSharedInstance_ReturnsSameInstance() {
        // Given
        let instance1 = ToastManager.shared
        let instance2 = ToastManager.shared

        // Then
        XCTAssertTrue(instance1 === instance2, "Shared instance should return the same instance")
    }

    func testInitialState_NoToastDisplayed() {
        // Then
        XCTAssertNil(sut.currentToast, "currentToast should be nil initially")
    }

    // MARK: - Show Toast Tests

    func testShow_ErrorToast_SetsCurrentToast() {
        // Given
        let message = "Test error message"

        // When
        sut.show(message, type: .error)

        // Then
        XCTAssertNotNil(sut.currentToast, "currentToast should not be nil after showing")
        XCTAssertEqual(sut.currentToast?.message, message, "Toast message should match")
        XCTAssertEqual(sut.currentToast?.type, .error, "Toast type should be error")
    }

    func testShow_WarningToast_SetsCurrentToast() {
        // Given
        let message = "Test warning message"

        // When
        sut.show(message, type: .warning)

        // Then
        XCTAssertNotNil(sut.currentToast, "currentToast should not be nil after showing")
        XCTAssertEqual(sut.currentToast?.message, message, "Toast message should match")
        XCTAssertEqual(sut.currentToast?.type, .warning, "Toast type should be warning")
    }

    func testShow_InfoToast_SetsCurrentToast() {
        // Given
        let message = "Test info message"

        // When
        sut.show(message, type: .info)

        // Then
        XCTAssertNotNil(sut.currentToast, "currentToast should not be nil after showing")
        XCTAssertEqual(sut.currentToast?.message, message, "Toast message should match")
        XCTAssertEqual(sut.currentToast?.type, .info, "Toast type should be info")
    }

    func testShow_ReplacesExistingToast() {
        // Given
        let firstMessage = "First message"
        let secondMessage = "Second message"

        // When
        sut.show(firstMessage, type: .error)
        let firstToast = sut.currentToast
        sut.show(secondMessage, type: .warning)

        // Then
        XCTAssertNotNil(firstToast, "First toast should have been set")
        XCTAssertNotNil(sut.currentToast, "Current toast should not be nil")
        XCTAssertNotEqual(sut.currentToast?.id, firstToast?.id, "Toast ID should be different")
        XCTAssertEqual(sut.currentToast?.message, secondMessage, "Should show second message")
        XCTAssertEqual(sut.currentToast?.type, .warning, "Should show warning type")
    }

    func testRapidSuccession_LastToastWins() {
        // Given
        let toastCount = 5

        // When - Show multiple toasts in rapid succession
        for i in 0 ..< toastCount {
            sut.show("Toast \(i)", type: .info)
        }

        // Then - Last toast should be the one displayed
        XCTAssertNotNil(sut.currentToast, "A toast should be displayed")
        XCTAssertEqual(sut.currentToast?.message, "Toast 4", "Last toast should win in rapid succession")
        XCTAssertEqual(sut.currentToast?.type, .info, "Toast type should match")
    }

    // MARK: - Dismiss Tests

    func testDismiss_ClearsCurrentToast() {
        // Given
        sut.show("Test message", type: .error)
        XCTAssertNotNil(sut.currentToast, "Toast should be shown")

        // When
        sut.dismiss()

        // Then
        XCTAssertNil(sut.currentToast, "currentToast should be nil after dismissal")
    }

    func testDismiss_WhenNoToast_DoesNotCrash() {
        // Given
        XCTAssertNil(sut.currentToast, "No toast should be shown initially")

        // When/Then
        sut.dismiss() // Should not crash
        XCTAssertNil(sut.currentToast, "currentToast should remain nil")
    }

    // MARK: - Auto-Dismiss Tests

    func testShow_AutoDismissesAfterDelay() async {
        // Given
        let message = "Auto-dismiss test"
        let autoDismissDelay: TimeInterval = 4.0

        // When
        sut.show(message, type: .error)
        XCTAssertNotNil(sut.currentToast, "Toast should be shown initially")

        // Wait for auto-dismiss (4 seconds + buffer)
        try? await Task.sleep(nanoseconds: UInt64((autoDismissDelay + 0.5) * 1_000_000_000))

        // Then
        XCTAssertNil(sut.currentToast, "Toast should auto-dismiss after delay")
    }

    func testShow_ManualDismissBeforeAutoDismiss_CancelsTimer() async {
        // Given
        let message = "Manual dismiss test"

        // When
        sut.show(message, type: .error)
        XCTAssertNotNil(sut.currentToast, "Toast should be shown")

        // Manually dismiss before auto-dismiss
        try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds
        sut.dismiss()

        // Wait past the auto-dismiss time
        try? await Task.sleep(nanoseconds: 4_000_000_000) // 4 seconds

        // Then
        XCTAssertNil(sut.currentToast, "Toast should remain dismissed")
    }

    // MARK: - ToastData Tests

    func testToastData_HasUniqueIDs() {
        // Given
        let message = "Test message"

        // When
        sut.show(message, type: .error)
        let firstID = sut.currentToast?.id
        sut.show(message, type: .error)
        let secondID = sut.currentToast?.id

        // Then
        XCTAssertNotNil(firstID, "First toast should have ID")
        XCTAssertNotNil(secondID, "Second toast should have ID")
        XCTAssertNotEqual(firstID, secondID, "Each toast should have unique ID")
    }

    func testToastData_Equatable_SameContent() {
        // Given
        let toast1 = ToastData(message: "Test", type: .error)
        let toast2 = ToastData(message: "Test", type: .error)

        // Then
        XCTAssertNotEqual(toast1, toast2, "ToastData with same content but different IDs should not be equal")
    }

    func testToastData_Equatable_SameInstance() {
        // Given
        let toast = ToastData(message: "Test", type: .error)

        // Then
        XCTAssertEqual(toast, toast, "ToastData instance should equal itself")
    }
}
