import SwiftUI
import UIKit

/// Disables the `UINavigationController.interactivePopGestureRecognizer` (left-edge
/// swipe-back) while the host view is in the hierarchy, restoring the prior state
/// when the view is removed.
///
/// `.navigationBarBackButtonHidden(true)` only hides the back button — iOS still
/// honors the edge-swipe gesture, which can dismiss a pushed view without running
/// any confirmation flow. This modifier closes that gap for flows like active
/// tests that must intercept exits through a modal.
private struct SwipeBackGestureBlocker: UIViewControllerRepresentable {
    let isDisabled: Bool

    final class Coordinator {
        weak var navigationController: UINavigationController?
        var originalIsEnabled: Bool?

        deinit {
            if let original = originalIsEnabled {
                navigationController?.interactivePopGestureRecognizer?.isEnabled = original
            }
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIViewController(context _: Context) -> UIViewController {
        let controller = UIViewController()
        controller.view.isUserInteractionEnabled = false
        controller.view.backgroundColor = .clear
        return controller
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {
        let coordinator = context.coordinator
        let desiredIsDisabled = isDisabled
        DispatchQueue.main.async {
            guard let navigationController = uiViewController.navigationController else { return }
            if coordinator.navigationController !== navigationController {
                coordinator.navigationController = navigationController
                coordinator.originalIsEnabled =
                    navigationController.interactivePopGestureRecognizer?.isEnabled ?? true
            }
            let targetEnabled = desiredIsDisabled
                ? false
                : (coordinator.originalIsEnabled ?? true)
            navigationController.interactivePopGestureRecognizer?.isEnabled = targetEnabled
        }
    }
}

extension View {
    /// Disables the NavigationStack swipe-back gesture while `isDisabled` is true.
    ///
    /// Apply this anywhere inside a `NavigationStack` to prevent the iOS left-edge
    /// swipe from popping the current view. The gesture's prior state is restored
    /// when this view leaves the hierarchy or when `isDisabled` becomes false.
    func swipeBackDisabled(_ isDisabled: Bool = true) -> some View {
        background(SwipeBackGestureBlocker(isDisabled: isDisabled))
    }
}
