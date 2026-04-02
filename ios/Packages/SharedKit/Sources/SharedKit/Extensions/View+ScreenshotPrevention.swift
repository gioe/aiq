import SwiftUI

public extension View {
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
    /// // Correct
    /// myView
    ///     .screenshotPrevented(accessibilityIdentifier: "my-view",
    ///                          accessibilityLabel: "My view")
    ///
    /// // Silent failure — modifiers are dropped by the UIViewRepresentable bridge
    /// myView
    ///     .accessibilityIdentifier("my-view")   // dropped
    ///     .screenshotPrevented()
    /// ```
    ///
    /// - Parameter accessibilityIdentifier: XCUITest identifier set directly on the
    ///   underlying `ScreenshotContainerView` (iOS only; no-op on other platforms).
    /// - Parameter accessibilityLabel: VoiceOver label set directly on the underlying
    ///   `ScreenshotContainerView` (iOS only; no-op on other platforms).
    func screenshotPrevented(
        accessibilityIdentifier: String? = nil,
        accessibilityLabel: String? = nil
    ) -> some View {
        #if canImport(UIKit)
            ScreenshotPreventedView(
                content: self,
                accessibilityIdentifier: accessibilityIdentifier,
                accessibilityLabel: accessibilityLabel
            )
        #else
            self
        #endif
    }
}

// MARK: - UIViewRepresentable wrapper (iOS / UIKit only)

#if canImport(UIKit)
    import UIKit

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

            container.preferredSizeProvider = { [weak hostingController] targetSize in
                hostingController?.sizeThatFits(in: targetSize) ?? targetSize
            }

            container.onEnterWindow = { [weak container, weak hostingController] in
                guard let container,
                      let hostingController,
                      hostingController.parent == nil,
                      let parentVC = container.nearestViewController else { return }
                parentVC.addChild(hostingController)
                hostingController.didMove(toParent: parentVC)
            }

            container.accessibilityIdentifier = accessibilityIdentifier
            container.accessibilityLabel = accessibilityLabel

            return container
        }

        func sizeThatFits(
            _ proposal: ProposedViewSize,
            uiView: ScreenshotContainerView,
            coordinator: Coordinator
        ) -> CGSize? {
            let width: CGFloat
            if let proposed = proposal.width {
                width = max(proposed, 1)
            } else if uiView.bounds.width > 0 {
                width = uiView.bounds.width
            } else if uiView.lastValidWidth > 0 {
                width = uiView.lastValidWidth
            } else {
                return nil // No valid width yet; SwiftUI will use intrinsicContentSize
            }
            let targetSize = CGSize(width: width, height: 10000)
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

    final class ScreenshotContainerView: UIView {
        var onEnterWindow: (() -> Void)?

        var preferredSizeProvider: ((CGSize) -> CGSize)?

        /// Cache the last real width so intrinsicContentSize doesn't fall back to
        /// width=1 during animation frames where bounds haven't been assigned yet.
        private var _lastValidWidth: CGFloat = 0

        /// The last layout width cached by `layoutSubviews`; zero if no real layout has occurred.
        var lastValidWidth: CGFloat {
            _lastValidWidth
        }

        override func layoutSubviews() {
            super.layoutSubviews()
            if bounds.width > 0 {
                _lastValidWidth = bounds.width
            }
        }

        override var intrinsicContentSize: CGSize {
            guard let provider = preferredSizeProvider else {
                return super.intrinsicContentSize
            }
            let width: CGFloat
            if bounds.width > 0 {
                width = bounds.width
            } else if _lastValidWidth > 0 {
                width = _lastValidWidth
            } else {
                // No valid width yet — let external constraints size this view.
                return CGSize(width: UIView.noIntrinsicMetric, height: UIView.noIntrinsicMetric)
            }
            return provider(CGSize(width: width, height: 10000))
        }

        override func sizeThatFits(_ size: CGSize) -> CGSize {
            guard let provider = preferredSizeProvider else {
                return super.sizeThatFits(size)
            }
            return provider(size)
        }

        override var isAccessibilityElement: Bool {
            get { _lockedAccessibilityId != nil }
            set { _ = newValue }
        }

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

        var nearestViewController: UIViewController? {
            var responder: UIResponder? = next
            while let responderNode = responder {
                if let vc = responderNode as? UIViewController { return vc }
                responder = responderNode.next
            }
            return nil
        }
    }
#endif
