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

    func makeUIView(context: Context) -> UIView {
        let container = UIView()
        container.backgroundColor = .clear

        // A UITextField with isSecureTextEntry = true creates an internal
        // canvas whose CALayer iOS marks as non-capturable. Content embedded
        // inside this canvas is excluded from screenshots and screen recordings.
        let textField = UITextField()
        textField.isSecureTextEntry = true
        textField.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(textField)

        NSLayoutConstraint.activate([
            textField.topAnchor.constraint(equalTo: container.topAnchor),
            textField.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            textField.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            textField.bottomAnchor.constraint(equalTo: container.bottomAnchor)
        ])

        // The first subview of the secure text field is the private secure
        // canvas. Fall back to the text field itself if the internal structure
        // ever changes in a future iOS release.
        let secureCanvas = textField.subviews.first ?? textField

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
        return container
    }

    func updateUIView(_: UIView, context: Context) {
        context.coordinator.hostingController?.rootView = content
    }

    final class Coordinator {
        var hostingController: UIHostingController<Content>?
    }
}
