import SwiftUI
import UIKit

extension View {
    /// Prevents this view from appearing in screenshots and screen recordings.
    ///
    /// Uses the `UITextField(isSecureTextEntry: true)` technique — the standard
    /// iOS banking-app pattern. iOS excludes the secure canvas layer from
    /// capture, so content embedded inside it appears blank in screenshots
    /// and screen recordings while remaining fully visible during normal use.
    ///
    /// - Parameter accessibilityIdentifier: XCUITest identifier set directly on the
    ///   underlying `ScreenshotContainerView`.  SwiftUI's `.accessibilityIdentifier()`
    ///   modifier does not propagate through the UIViewRepresentable bridge, so the
    ///   identifier must be injected here and applied at the UIKit level.
    func screenshotPrevented(accessibilityIdentifier: String? = nil) -> some View {
        ScreenshotPreventedView(content: self, accessibilityIdentifier: accessibilityIdentifier)
    }
}

// MARK: - UIViewRepresentable wrapper

private struct ScreenshotPreventedView<Content: View>: UIViewRepresentable {
    let content: Content
    let accessibilityIdentifier: String?

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

        // Provide content size back to the container so intrinsicContentSize and
        // sizeThatFits(_:) return the hosted SwiftUI view's preferred dimensions
        // rather than UITextField's fixed ~34pt intrinsic height.
        container.preferredSizeProvider = { [weak hostingController] targetSize in
            hostingController?.sizeThatFits(in: targetSize) ?? targetSize
        }

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

        // Set the XCUITest identifier directly at the UIKit level.
        // SwiftUI's .accessibilityIdentifier() modifier does not propagate through
        // the UIViewRepresentable bridge to UIView.accessibilityIdentifier, so the
        // identifier must be applied here to be discoverable by XCUITest.
        container.accessibilityIdentifier = accessibilityIdentifier

        return container
    }

    func sizeThatFits(
        _ proposal: ProposedViewSize,
        uiView: ScreenshotContainerView,
        coordinator: Coordinator
    ) -> CGSize? {
        let width = proposal.width ?? uiView.window?.bounds.width ?? uiView.bounds.width
        let targetSize = CGSize(width: width, height: UIView.layoutFittingCompressedSize.height)
        return coordinator.hostingController?.sizeThatFits(in: targetSize)
    }

    func updateUIView(_ uiView: ScreenshotContainerView, context: Context) {
        context.coordinator.hostingController?.rootView = content
        uiView.invalidateIntrinsicContentSize()
        uiView.accessibilityIdentifier = accessibilityIdentifier
    }

    final class Coordinator {
        var hostingController: UIHostingController<Content>?
    }
}

// MARK: - Container view

private final class ScreenshotContainerView: UIView {
    var onEnterWindow: (() -> Void)?

    /// Closure set by the UIViewRepresentable to ask the UIHostingController for its
    /// preferred size. Bridges the hosted SwiftUI content's preferred dimensions back
    /// into UIKit so `intrinsicContentSize` and `sizeThatFits(_:)` return the correct
    /// height rather than UITextField's fixed ~34pt intrinsic height.
    var preferredSizeProvider: ((CGSize) -> CGSize)?

    override var intrinsicContentSize: CGSize {
        guard let provider = preferredSizeProvider else {
            return super.intrinsicContentSize
        }
        let width = bounds.width > 0 ? bounds.width : window?.bounds.width ?? superview?.bounds.width ?? 0
        return provider(CGSize(width: width, height: UIView.layoutFittingCompressedSize.height))
    }

    override func sizeThatFits(_ size: CGSize) -> CGSize {
        guard let provider = preferredSizeProvider else {
            return super.sizeThatFits(size)
        }
        return provider(size)
    }

    /// UIView's default `isAccessibilityElement` is `false`, which causes UIKit to
    /// traverse into subviews.  The subviews here are a UITextField's private secure
    /// canvas — opaque to the accessibility tree — so traversal finds nothing useful.
    /// Returning `true` makes XCUITest and VoiceOver treat this container as a single
    /// accessible element whose identifier is set directly via the `accessibilityIdentifier`
    /// parameter on `.screenshotPrevented()`.
    override var isAccessibilityElement: Bool {
        get { true }
        set { _ = newValue }
    }

    /// Stores the accessibility identifier injected via the `accessibilityIdentifier`
    /// parameter on `.screenshotPrevented()`.  SwiftUI may reset `UIView.accessibilityIdentifier`
    /// after `makeUIView`/`updateUIView` via its own accessibility bridge, so we lock the value
    /// here: the getter always returns our stored id, ignoring any external clears.
    private var _lockedAccessibilityId: String?

    override var accessibilityIdentifier: String? {
        get { _lockedAccessibilityId }
        set { _lockedAccessibilityId = newValue }
    }

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
