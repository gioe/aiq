import SwiftUI

/// A dismissible error banner that appears at the top of the screen.
///
/// When `retryAction` is provided, tapping the icon and message area triggers the retry
/// closure while the dismiss (X) button still calls `onDismiss`. This allows callers to
/// offer an in-place retry without requiring a separate retry button.
///
/// Backward compatibility: existing callers that omit `retryAction` receive the same
/// non-interactive layout as before.
struct ErrorBanner: View {
    let message: String
    let onDismiss: () -> Void
    /// Optional action called when the user taps the banner's content area (icon + message).
    /// When non-nil, the content area renders as a tappable `Button` with `.plain` style.
    var retryAction: (() -> Void)?

    var body: some View {
        HStack(spacing: 12) {
            bannerContent

            Spacer()

            IconButton(
                icon: "xmark",
                action: onDismiss,
                accessibilityLabel: "error.banner.dismiss".localized,
                foregroundColor: .white
            )
            .accessibilityIdentifier(AccessibilityIdentifiers.ErrorBanner.dismissButton)
        }
        .padding()
        .background(Color.red)
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.1), radius: 4, x: 0, y: 2)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Error: \(message)")
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
