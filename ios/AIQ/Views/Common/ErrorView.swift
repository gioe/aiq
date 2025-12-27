import SwiftUI

/// A reusable error display view
struct ErrorView: View {
    let error: Error
    let retryAction: (() -> Void)?

    init(error: Error, retryAction: (() -> Void)? = nil) {
        self.error = error
        self.retryAction = retryAction
    }

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundColor(.orange)
                .accessibilityHidden(true) // Decorative icon

            Text("error.default.title".localized)
                .font(.headline)

            Text(error.localizedDescription)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            if let retryAction {
                Button(action: retryAction) {
                    Label("error.try.again".localized, systemImage: "arrow.clockwise")
                }
                .buttonStyle(.borderedProminent)
                .accessibilityLabel("error.try.again".localized)
                .accessibilityHint("accessibility.retry.hint".localized)
                .accessibilityIdentifier(AccessibilityIdentifiers.Common.retryButton)
            }
        }
        .padding()
        .accessibilityElement(children: .contain)
        .accessibilityLabel("accessibility.error.view".localized(with: error.localizedDescription))
        .accessibilityIdentifier(AccessibilityIdentifiers.Common.errorView)
    }
}

#Preview {
    ErrorView(
        error: APIError.networkError(NSError(domain: "test", code: -1)),
        retryAction: { print("Retry tapped") }
    )
}
