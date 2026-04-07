import SwiftUI

/// A dismissible error banner that appears at the top of the screen.
///
/// When `retryAction` is provided, tapping the icon and message area triggers the retry
/// closure while the dismiss (X) button still calls `onDismiss`. This allows callers to
/// offer an in-place retry without requiring a separate retry button.
///
/// Backward compatibility: existing callers that omit `retryAction` receive the same
/// non-interactive layout as before.
public struct ErrorBanner: View {
    public let message: String
    public let onDismiss: () -> Void
    /// Optional action called when the user taps the banner's content area (icon + message).
    /// When non-nil, the content area renders as a tappable `Button` with `.plain` style.
    public var retryAction: (() -> Void)?
    /// Optional hint announced by VoiceOver on the dismiss button to guide the user.
    public var dismissHint: String?

    @Environment(\.appTheme) private var theme

    public init(
        message: String,
        onDismiss: @escaping () -> Void,
        retryAction: (() -> Void)? = nil,
        dismissHint: String? = nil
    ) {
        self.message = message
        self.onDismiss = onDismiss
        self.retryAction = retryAction
        self.dismissHint = dismissHint
    }

    public var body: some View {
        if retryAction != nil {
            // When a retry button is present, omit the container label so VoiceOver
            // does not announce the message twice.
            containerStack
        } else {
            containerStack
                .accessibilityElement(children: .contain)
                .accessibilityLabel("Error: \(message)")
        }
    }

    private var containerStack: some View {
        HStack(spacing: 12) {
            bannerContent

            Spacer()

            IconButton(
                icon: "xmark",
                action: onDismiss,
                accessibilityLabel: "Dismiss",
                foregroundColor: .white
            )
            .accessibilityIdentifier("errorBanner.dismissButton")
            .accessibilityHint(dismissHint ?? "")
        }
        .padding()
        .background(Color.red)
        .cornerRadius(theme.cornerRadius.md)
        .shadowStyle(theme.shadows.sm)
    }

    /// The icon and message area. Rendered as a tappable `Button` when `retryAction` is
    /// provided, or as plain views otherwise, keeping the layout identical in both cases.
    @ViewBuilder
    private var bannerContent: some View {
        if let retryAction {
            Button(action: retryAction) {
                iconAndMessage
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Retry: \(message)")
            .accessibilityHint("Double tap to retry")
        } else {
            iconAndMessage
        }
    }

    private var iconAndMessage: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.white)

            Text(message)
                .font(.subheadline)
                .foregroundColor(.white)
                .multilineTextAlignment(.leading)
        }
    }
}

#Preview {
    VStack(spacing: 16) {
        ErrorBanner(
            message: "Unable to connect to the server. Please check your internet connection.",
            onDismiss: {}
        )
        .padding(.horizontal)

        ErrorBanner(
            message: "Submission failed. Tap to retry.",
            onDismiss: {},
            retryAction: {}
        )
        .padding(.horizontal)

        Spacer()
    }
}
