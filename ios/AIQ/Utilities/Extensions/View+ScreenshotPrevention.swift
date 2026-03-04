import SwiftUI
import UIKit

extension View {
    /// Prevents this view from appearing in screenshots and screen recordings.
    ///
    /// Uses the `UITextField(isSecureTextEntry: true)` technique — the standard
    /// iOS banking-app pattern. iOS excludes the secure canvas layer from
    /// capture, so content embedded inside it appears blank in screenshots
    /// and screen recordings while remaining fully visible during normal use.
    func screenshotPrevented() -> some View {
        ScreenshotPreventedView(content: self)
    }
}

// MARK: - UIViewRepresentable wrapper

private struct ScreenshotPreventedView<Content: View>: UIViewRepresentable {
    let content: Content

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> ScreenshotContainerView {
        let container = ScreenshotContainerView()

        // A UITextField with isSecureTextEntry = true creates an internal
        // canvas whose CALayer iOS marks as non-capturable. Content embedded
        // inside this canvas is excluded from screenshots and screen recordings.
        let textField = UITextField()
        textField.isSecureTextEntry = true
        // Prevent the hidden text field from appearing in VoiceOver or
        // intercepting touches / becoming first responder.
        textField.isUserInteractionEnabled = false
        textField.isAccessibilityElement = false
        textField.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(textField)

        NSLayoutConstraint.activate([
            textField.topAnchor.constraint(equalTo: container.topAnchor),
            textField.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            textField.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            textField.bottomAnchor.constraint(equalTo: container.bottomAnchor)
        ])

        // The first subview of the secure text field is the private secure canvas.
        // Assert in debug builds so breakage from future UIKit restructuring is
        // immediately visible; fall back to the text field itself in production.
        let secureCanvas: UIView
        if let canvas = textField.subviews.first {
            secureCanvas = canvas
        } else {
            // swiftlint:disable:next line_length
            assertionFailure("UITextField secure canvas not found — screenshot prevention is disabled. Check UIKit internals for this iOS version.")
            secureCanvas = textField
        }

        let hostingController = UIHostingController(rootView: content)
        hostingController.view.translatesAutoresizingMaskIntoConstraints = false
        hostingController.view.backgroundColor = .clear
        secureCanvas.addSubview(hostingController.view)

        NSLayoutConstraint.activate([
            hostingController.view.topAnchor.constraint(equalTo: secureCanvas.topAnchor),
            hostingController.view.leadingAnchor.constraint(equalTo: secureCanvas.leadingAnchor),
            hostingController.view.trailingAnchor.constraint(equalTo: secureCanvas.trailingAnchor),
            hostingController.view.bottomAnchor.constraint(equalTo: secureCanvas.bottomAnchor)
        ])

        context.coordinator.hostingController = hostingController

        // Add the hosting controller as a child VC once the view enters the window
        // hierarchy. This ensures SwiftUI environment values (colorScheme,
        // dynamicTypeSize, accessibilityReduceMotion, etc.) flow correctly into
        // the hosted content.
        container.onEnterWindow = { [weak container, weak hostingController] in
            guard let container,
                  let hostingController,
                  hostingController.parent == nil,
                  let parentVC = container.nearestViewController else { return }
            parentVC.addChild(hostingController)
            hostingController.didMove(toParent: parentVC)
        }

        return container
    }

    func updateUIView(_: ScreenshotContainerView, context: Context) {
        context.coordinator.hostingController?.rootView = content
    }

    final class Coordinator {
        var hostingController: UIHostingController<Content>?
    }
}

// MARK: - Container view

private final class ScreenshotContainerView: UIView {
    var onEnterWindow: (() -> Void)?

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window != nil {
            onEnterWindow?()
        }
    }

    /// Traverses the responder chain to find the nearest parent UIViewController.
    var nearestViewController: UIViewController? {
        var responder: UIResponder? = next
        while let responderNode = responder {
            if let vc = responderNode as? UIViewController { return vc }
            responder = responderNode.next
        }
        return nil
    }
}
