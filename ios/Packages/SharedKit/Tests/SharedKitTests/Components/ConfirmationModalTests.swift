import SharedKit
import SwiftUI
import XCTest

/// Tests for the ConfirmationModal component.
///
/// These tests verify that the modal correctly stores all configuration values
/// passed through its public initializer and that the confirm and cancel callbacks
/// fire when invoked directly.
///
/// Note: The backdrop tap path (`onTapGesture { onCancel() }` in ConfirmationModal.body)
/// is a distinct UX trigger for `onCancel` that cannot be tested at this unit layer without
/// a SwiftUI hosting environment. It is covered by the UITests suite via the modal's
/// accessibility identifiers.
@MainActor
final class ConfirmationModalTests: XCTestCase {
    // MARK: - Helpers

    private func makeModal(
        iconName: String = "trash.circle",
        title: String = "Test Title",
        message: String = "Test message",
        confirmLabel: String = "Confirm",
        confirmAccessibilityLabel: String = "Confirm action",
        confirmAccessibilityHint: String = "Double tap to confirm",
        confirmAccessibilityIdentifier: String = "test.confirmButton",
        cancelAccessibilityHint: String = "Double tap to cancel",
        cancelAccessibilityIdentifier: String = "test.cancelButton",
        modalAccessibilityIdentifier: String = "test.modal",
        onConfirm: @escaping () -> Void = {},
        onCancel: @escaping () -> Void = {}
    ) -> ConfirmationModal {
        ConfirmationModal(
            iconName: iconName,
            title: title,
            message: message,
            confirmLabel: confirmLabel,
            confirmAccessibilityLabel: confirmAccessibilityLabel,
            confirmAccessibilityHint: confirmAccessibilityHint,
            confirmAccessibilityIdentifier: confirmAccessibilityIdentifier,
            cancelAccessibilityHint: cancelAccessibilityHint,
            cancelAccessibilityIdentifier: cancelAccessibilityIdentifier,
            modalAccessibilityIdentifier: modalAccessibilityIdentifier,
            onConfirm: onConfirm,
            onCancel: onCancel
        )
    }

    // MARK: - Initialization Tests

    func testViewCanBeInitialized() {
        // Given/When — init must not crash; type-system guarantees non-nil for value types
        _ = makeModal()
    }

    // MARK: - Property Storage Tests

    func testViewStoresIconName() {
        // Given
        let expectedIconName = "rectangle.portrait.and.arrow.right"

        // When
        let modal = makeModal(iconName: expectedIconName)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("iconName") as? String {
            XCTAssertEqual(stored, expectedIconName, "iconName should match the value passed to init")
        } else {
            XCTFail("Could not extract iconName from ConfirmationModal")
        }
    }

    func testViewStoresTitle() {
        // Given
        let expectedTitle = "Are you sure?"

        // When
        let modal = makeModal(title: expectedTitle)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("title") as? String {
            XCTAssertEqual(stored, expectedTitle, "title should match the value passed to init")
        } else {
            XCTFail("Could not extract title from ConfirmationModal")
        }
    }

    func testViewStoresMessage() {
        // Given
        let expectedMessage = "This action cannot be undone."

        // When
        let modal = makeModal(message: expectedMessage)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("message") as? String {
            XCTAssertEqual(stored, expectedMessage, "message should match the value passed to init")
        } else {
            XCTFail("Could not extract message from ConfirmationModal")
        }
    }

    func testViewStoresConfirmLabel() {
        // Given
        let expectedConfirmLabel = "Delete Account"

        // When
        let modal = makeModal(confirmLabel: expectedConfirmLabel)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("confirmLabel") as? String {
            XCTAssertEqual(stored, expectedConfirmLabel, "confirmLabel should match the value passed to init")
        } else {
            XCTFail("Could not extract confirmLabel from ConfirmationModal")
        }
    }

    func testViewStoresConfirmAccessibilityLabel() {
        // Given
        let expectedLabel = "Log out of your account"

        // When
        let modal = makeModal(confirmAccessibilityLabel: expectedLabel)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("confirmAccessibilityLabel") as? String {
            XCTAssertEqual(stored, expectedLabel, "confirmAccessibilityLabel should match the value passed to init")
        } else {
            XCTFail("Could not extract confirmAccessibilityLabel from ConfirmationModal")
        }
    }

    func testViewStoresConfirmAccessibilityHint() {
        // Given
        let expectedHint = "Logs you out and returns to the login screen"

        // When
        let modal = makeModal(confirmAccessibilityHint: expectedHint)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("confirmAccessibilityHint") as? String {
            XCTAssertEqual(stored, expectedHint, "confirmAccessibilityHint should match the value passed to init")
        } else {
            XCTFail("Could not extract confirmAccessibilityHint from ConfirmationModal")
        }
    }

    func testViewStoresConfirmAccessibilityIdentifier() {
        // Given
        let expectedIdentifier = "settingsView.deleteAccountConfirmButton"

        // When
        let modal = makeModal(confirmAccessibilityIdentifier: expectedIdentifier)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("confirmAccessibilityIdentifier") as? String {
            XCTAssertEqual(
                stored,
                expectedIdentifier,
                "confirmAccessibilityIdentifier should match the value passed to init"
            )
        } else {
            XCTFail("Could not extract confirmAccessibilityIdentifier from ConfirmationModal")
        }
    }

    func testViewStoresCancelAccessibilityHint() {
        // Given
        let expectedHint = "Dismisses the confirmation dialog"

        // When
        let modal = makeModal(cancelAccessibilityHint: expectedHint)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("cancelAccessibilityHint") as? String {
            XCTAssertEqual(stored, expectedHint, "cancelAccessibilityHint should match the value passed to init")
        } else {
            XCTFail("Could not extract cancelAccessibilityHint from ConfirmationModal")
        }
    }

    func testViewStoresCancelAccessibilityIdentifier() {
        // Given
        let expectedIdentifier = "settingsView.deleteAccountCancelButton"

        // When
        let modal = makeModal(cancelAccessibilityIdentifier: expectedIdentifier)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("cancelAccessibilityIdentifier") as? String {
            XCTAssertEqual(
                stored,
                expectedIdentifier,
                "cancelAccessibilityIdentifier should match the value passed to init"
            )
        } else {
            XCTFail("Could not extract cancelAccessibilityIdentifier from ConfirmationModal")
        }
    }

    func testViewStoresModalAccessibilityIdentifier() {
        // Given
        let expectedIdentifier = "settingsView.deleteAccountConfirmationModal"

        // When
        let modal = makeModal(modalAccessibilityIdentifier: expectedIdentifier)
        let mirror = Mirror(reflecting: modal)

        // Then
        if let stored = mirror.descendant("modalAccessibilityIdentifier") as? String {
            XCTAssertEqual(
                stored,
                expectedIdentifier,
                "modalAccessibilityIdentifier should match the value passed to init"
            )
        } else {
            XCTFail("Could not extract modalAccessibilityIdentifier from ConfirmationModal")
        }
    }

    // MARK: - Callback Tests

    func testOnConfirmCallbackFires() {
        // Given
        var confirmFired = false
        let modal = makeModal(onConfirm: { confirmFired = true })

        // When
        modal.onConfirm()

        // Then
        XCTAssertTrue(confirmFired, "onConfirm callback should fire when called")
    }

    func testOnCancelCallbackFires() {
        // Given
        var cancelFired = false
        let modal = makeModal(onCancel: { cancelFired = true })

        // When
        modal.onCancel()

        // Then
        XCTAssertTrue(cancelFired, "onCancel callback should fire when called")
    }
}
