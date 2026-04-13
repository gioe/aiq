import AIQSharedKit
import SwiftUI

/// A dismissible warning banner shown when test time is running low
struct TimeWarningBanner: View {
    let remainingTime: String
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 20))
                .foregroundColor(.orange)

            VStack(alignment: .leading, spacing: 2) {
                Text("test.timer.time.running.low".localized)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)

                Text("test.timer.time.remaining".localized(with: remainingTime))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            IconButton(
                icon: "xmark.circle.fill",
                action: onDismiss,
                accessibilityLabel: "Dismiss time warning",
                foregroundColor: .secondary
            )
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.orange.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.orange.opacity(0.3), lineWidth: 1)
                )
        )
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.timeWarningBanner)
        .onAppear {
            ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.warning)
        }
    }
}

// MARK: - Preview

#Preview {
    VStack {
        TimeWarningBanner(remainingTime: "5:00") {}
        Spacer()
    }
    .padding(.top, 20)
}
