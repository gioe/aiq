import AIQSharedKit
import SwiftUI

/// Accessibility identifier bundle for the per-site exit-confirmation modal.
/// The shared modal UI is the same across test flows, but each call-site uses
/// its own identifier namespace so XCUITest selectors stay distinct.
struct TestExitConfirmationIdentifiers {
    let confirmButton: String
    let cancelButton: String
    let modal: String
}

/// Overlay modifier that presents the shared test exit-confirmation modal when
/// `viewModel.showExitConfirmation` becomes true. Consumed by AdaptiveTestView
/// and GuestTestContainerView; the only site-specific behaviour is
/// `onConfirmExit` (e.g. abandon + pop-to-root vs. callback dismiss) and the
/// identifier namespace passed in via `identifiers`.
struct TestExitConfirmationModifier: ViewModifier {
    @ObservedObject var viewModel: TestTakingViewModel
    let identifiers: TestExitConfirmationIdentifiers
    let onConfirmExit: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.appTheme) private var theme

    func body(content: Content) -> some View {
        content.overlay {
            if viewModel.showExitConfirmation {
                modal.transition(modalTransition)
            }
        }
        .animation(modalAnimation, value: viewModel.showExitConfirmation)
    }

    private var modalTransition: AnyTransition {
        guard !reduceMotion else { return .opacity }
        return .asymmetric(
            insertion: .opacity.combined(with: .scale(scale: 0.96)),
            removal: .opacity
        )
    }

    private var modalAnimation: Animation {
        reduceMotion ? .linear(duration: 0.2) : theme.animations.quick
    }

    private var message: String {
        let answered = viewModel.answeredCount
        let total = viewModel.totalQuestionCount
        if answered == 0 {
            return "You haven't answered any questions yet. You can come back and take the test anytime."
        } else if answered >= Constants.Test.abandonAnswerThreshold {
            return "You've answered \(answered) of \(total) questions. " +
                "Your answers will not be scored, and this will count as a test attempt. " +
                "You'll need to wait before you can retake the test."
        } else {
            return "You've answered \(answered) of \(total) questions. " +
                "Your answers will not be scored."
        }
    }

    private var modal: some View {
        ConfirmationModal(
            iconName: "exclamationmark.triangle",
            title: "Exit Test?",
            message: message,
            confirmLabel: "Exit",
            confirmAccessibilityLabel: "Exit test",
            confirmAccessibilityHint: "Double tap to exit the test without scoring",
            confirmAccessibilityIdentifier: identifiers.confirmButton,
            cancelAccessibilityHint: "Double tap to continue the test",
            cancelAccessibilityIdentifier: identifiers.cancelButton,
            modalAccessibilityIdentifier: identifiers.modal,
            onConfirm: {
                viewModel.cancelExit()
                onConfirmExit()
            },
            onCancel: { viewModel.cancelExit() }
        )
    }
}

extension View {
    /// Attaches the shared test exit-confirmation modal overlay.
    /// - Parameters:
    ///   - viewModel: The test's view model; the modal is shown when
    ///     `viewModel.showExitConfirmation` is true.
    ///   - identifiers: Per-site accessibility identifier namespace.
    ///   - onConfirmExit: Invoked after the user confirms exit (the modifier
    ///     calls `viewModel.cancelExit()` first). Site-specific — typically
    ///     abandons the test and navigates away.
    func testExitConfirmation(
        viewModel: TestTakingViewModel,
        identifiers: TestExitConfirmationIdentifiers,
        onConfirmExit: @escaping () -> Void
    ) -> some View {
        modifier(TestExitConfirmationModifier(
            viewModel: viewModel,
            identifiers: identifiers,
            onConfirmExit: onConfirmExit
        ))
    }
}
