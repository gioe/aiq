import SwiftUI
import XCTest

@testable import AIQ

@MainActor
final class NotificationSoftPromptViewTests: XCTestCase {
    // MARK: - Initialization Tests

    func testViewCanBeInitialized() {
        // Given
        var enableRemindersCalled = false
        var dismissCalled = false

        // When
        let view = NotificationSoftPromptView(
            onEnableReminders: {
                enableRemindersCalled = true
            },
            onDismiss: {
                dismissCalled = true
            }
        )

        // Then
        XCTAssertNotNil(view, "View should be initialized successfully")
        XCTAssertFalse(enableRemindersCalled, "Enable reminders callback should not be called on initialization")
        XCTAssertFalse(dismissCalled, "Dismiss callback should not be called on initialization")
    }

    // MARK: - Callback Tests

    func testEnableRemindersCallback_IsCalled() {
        // Given
        var enableRemindersCalled = false
        var dismissCalled = false

        let view = NotificationSoftPromptView(
            onEnableReminders: {
                enableRemindersCalled = true
            },
            onDismiss: {
                dismissCalled = true
            }
        )

        // When - simulate button tap through reflection
        let mirror = Mirror(reflecting: view)
        if let onEnableReminders = mirror.descendant("onEnableReminders") as? () -> Void {
            onEnableReminders()
        }

        // Then
        XCTAssertTrue(enableRemindersCalled, "Enable reminders callback should be called")
        XCTAssertFalse(dismissCalled, "Dismiss callback should not be called when enabling reminders")
    }

    func testDismissCallback_IsCalled() {
        // Given
        var enableRemindersCalled = false
        var dismissCalled = false

        let view = NotificationSoftPromptView(
            onEnableReminders: {
                enableRemindersCalled = true
            },
            onDismiss: {
                dismissCalled = true
            }
        )

        // When - simulate dismiss through reflection
        let mirror = Mirror(reflecting: view)
        if let onDismiss = mirror.descendant("onDismiss") as? () -> Void {
            onDismiss()
        }

        // Then
        XCTAssertTrue(dismissCalled, "Dismiss callback should be called")
        XCTAssertFalse(enableRemindersCalled, "Enable reminders callback should not be called on dismiss")
    }

    // MARK: - Integration Tests

    func testView_CallbacksAreIndependent() {
        // Given
        var enableRemindersCallCount = 0
        var dismissCallCount = 0

        let view = NotificationSoftPromptView(
            onEnableReminders: {
                enableRemindersCallCount += 1
            },
            onDismiss: {
                dismissCallCount += 1
            }
        )

        // When
        let mirror = Mirror(reflecting: view)

        // Call enable reminders
        if let onEnableReminders = mirror.descendant("onEnableReminders") as? () -> Void {
            onEnableReminders()
        }

        // Call dismiss
        if let onDismiss = mirror.descendant("onDismiss") as? () -> Void {
            onDismiss()
        }

        // Then
        XCTAssertEqual(enableRemindersCallCount, 1, "Enable reminders should be called exactly once")
        XCTAssertEqual(dismissCallCount, 1, "Dismiss should be called exactly once")
    }

    func testView_MultipleInstances_HaveIndependentCallbacks() {
        // Given
        var view1EnableCalled = false
        var view2EnableCalled = false

        let view1 = NotificationSoftPromptView(
            onEnableReminders: {
                view1EnableCalled = true
            },
            onDismiss: {}
        )

        let view2 = NotificationSoftPromptView(
            onEnableReminders: {
                view2EnableCalled = true
            },
            onDismiss: {}
        )

        // When
        let mirror1 = Mirror(reflecting: view1)
        let mirror2 = Mirror(reflecting: view2)

        if let callback1 = mirror1.descendant("onEnableReminders") as? () -> Void {
            callback1()
        }

        // Then
        XCTAssertTrue(view1EnableCalled, "First view's callback should be called")
        XCTAssertFalse(view2EnableCalled, "Second view's callback should not be called")

        // When - call second view's callback
        if let callback2 = mirror2.descendant("onEnableReminders") as? () -> Void {
            callback2()
        }

        // Then
        XCTAssertTrue(view1EnableCalled, "First view's callback should still be true")
        XCTAssertTrue(view2EnableCalled, "Second view's callback should now be called")
    }

    func testCallbacks_CanBeCalledMultipleTimes() {
        // Given
        var callCount = 0

        let view = NotificationSoftPromptView(
            onEnableReminders: {
                callCount += 1
            },
            onDismiss: {}
        )

        // When
        let mirror = Mirror(reflecting: view)
        if let callback = mirror.descendant("onEnableReminders") as? () -> Void {
            callback()
            callback()
            callback()
        }

        // Then - view doesn't debounce, caller is responsible
        XCTAssertEqual(callCount, 3, "Callback should be called each time")
    }
}
