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
    /// ## Accessibility Bridge Limitation
    ///
    /// SwiftUI accessibility modifiers applied to a view **before** calling
    /// `.screenshotPrevented()` are **silently dropped**.  Internally this modifier
    /// wraps its content in a `UIViewRepresentable`, which replaces the SwiftUI node
    /// in the accessibility tree with the underlying UIKit view.  As a result,
    /// `.accessibilityIdentifier()`, `.accessibilityLabel()`, and
    /// `.accessibilityElement()` chained outside this modifier have no effect.
    ///
    /// Always supply accessibility values as parameters to this modifier:
    /// ```swift
    /// // ✅ Correct
    /// myView
    ///     .screenshotPrevented(accessibilityIdentifier: "my-view",
    ///                          accessibilityLabel: "My view")
    ///
    /// // ❌ Silent failure — modifiers are dropped by the UIViewRepresentable bridge
    /// myView
    ///     .accessibilityIdentifier("my-view")   // dropped
    ///     .screenshotPrevented()
    /// ```
    ///
    /// - Parameter accessibilityIdentifier: XCUITest identifier set directly on the
    ///   underlying `ScreenshotContainerView`.  SwiftUI's `.accessibilityIdentifier()`
    ///   modifier does not propagate through the UIViewRepresentable bridge, so the
    ///   identifier must be injected here and applied at the UIKit level.
    /// - Parameter accessibilityLabel: VoiceOver label set directly on the underlying
    ///   `ScreenshotContainerView`.  SwiftUI's `.accessibilityLabel()` modifier does not
    ///   propagate through the UIViewRepresentable bridge, so the label must be injected
    ///   here and applied at the UIKit level.
    func screenshotPrevented(
        accessibilityIdentifier: String? = nil,
        accessibilityLabel: String? = nil
    ) -> some View {
        ScreenshotPreventedView(
            content: self,
            accessibilityIdentifier: accessibilityIdentifier,
            accessibilityLabel: accessibilityLabel
        )
    }
}

// MARK: - UIViewRepresentable wrapper

private struct ScreenshotPreventedView<Content: View>: UIViewRepresentable {
    let content: Content
    let accessibilityIdentifier: String?
    let accessibilityLabel: String?

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

        // Set XCUITest identifier and VoiceOver label directly at the UIKit level.
        // SwiftUI's .accessibilityIdentifier()/.accessibilityLabel() modifiers do not
        // propagate through the UIViewRepresentable bridge, so both must be applied here.
        container.accessibilityIdentifier = accessibilityIdentifier
        container.accessibilityLabel = accessibilityLabel

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
        uiView.accessibilityLabel = accessibilityLabel
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

    /// Returns `true` only when an `accessibilityIdentifier` is set, making XCUITest and
    /// VoiceOver treat this container as a single leaf element.  When no identifier is
    /// provided, UIKit falls back to its default traversal into subviews.  (The UITextField's
    /// private secure canvas is opaque to the accessibility tree regardless, so traversal
    /// finds nothing useful for unidentified containers — but callers that omit the identifier
    /// do not suffer a spurious empty leaf node in the tree.)
    override var isAccessibilityElement: Bool {
        get { _lockedAccessibilityId != nil }
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
