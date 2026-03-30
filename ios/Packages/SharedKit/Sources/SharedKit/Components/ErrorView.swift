import SwiftUI

/// A reusable error display view
public struct ErrorView: View {
    public let error: Error
    public let retryAction: (() -> Void)?

    public init(error: Error, retryAction: (() -> Void)? = nil) {
        self.error = error
        self.retryAction = retryAction
    }

    public var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundColor(.orange)
                .accessibilityHidden(true) // Decorative icon

            Text("Something Went Wrong")
                .font(.headline)

            Text(error.localizedDescription)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            if let retryAction {
                Button(action: retryAction) {
                    Label("Try Again", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.borderedProminent)
                .accessibilityLabel("Try Again")
                .accessibilityHint("Double tap to retry")
                .accessibilityIdentifier("common.retryButton")
            }
        }
        .padding()
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Error: \(error.localizedDescription)")
        .accessibilityIdentifier("common.errorView")
    }
}

#Preview {
    ErrorView(
        error: NSError(domain: "SharedKitPreview", code: -1, userInfo: [
            NSLocalizedDescriptionKey: "A network error occurred. Please try again."
        ]),
        retryAction: { print("Retry tapped") }
    )
}
