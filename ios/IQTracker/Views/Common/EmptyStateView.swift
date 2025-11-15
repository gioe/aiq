import SwiftUI

/// A reusable empty state view for displaying when no data is available
struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    let actionTitle: String?
    let action: (() -> Void)?

    init(
        icon: String = "tray",
        title: String,
        message: String,
        actionTitle: String? = nil,
        action: (() -> Void)? = nil
    ) {
        self.icon = icon
        self.title = title
        self.message = message
        self.actionTitle = actionTitle
        self.action = action
    }

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: icon)
                .font(.system(size: 64))
                .foregroundColor(.accentColor.opacity(0.6))
                .accessibilityHidden(true) // Decorative icon

            VStack(spacing: 12) {
                Text(title)
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)

                Text(message)
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(title). \(message)")

            if let actionTitle, let action {
                Button(action: action) {
                    Text(actionTitle)
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accentColor)
                        .cornerRadius(12)
                }
                .padding(.horizontal, 40)
                .padding(.top, 8)
                .accessibilityLabel(actionTitle)
                .accessibilityHint("Activate to \(actionTitle.lowercased())")
            }

            Spacer()
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

#Preview("No History") {
    EmptyStateView(
        icon: "chart.xyaxis.line",
        title: "No Test History Yet",
        message: "Take your first IQ test to start tracking your cognitive performance over time.",
        actionTitle: "Get Started",
        action: { print("Get started tapped") }
    )
}

#Preview("No Action") {
    EmptyStateView(
        icon: "magnifyingglass",
        title: "No Results Found",
        message: "Try adjusting your filters or search criteria."
    )
}
