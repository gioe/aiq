import SwiftUI

/// A reusable empty state view for displaying when no data is available
struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    let actionTitle: String?
    let action: (() -> Void)?

    @Environment(\.appTheme) private var theme

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
        VStack(spacing: theme.spacing.xxl) {
            Spacer()

            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.huge))
                .foregroundColor(theme.colors.primary.opacity(0.6))
                .accessibilityHidden(true) // Decorative icon

            VStack(spacing: theme.spacing.md) {
                Text(title)
                    .font(theme.typography.h2)
                    .foregroundColor(theme.colors.textPrimary)

                Text(message)
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, theme.spacing.huge)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(title). \(message)")

            if let actionTitle, let action {
                Button(action: action) {
                    Text(actionTitle)
                        .font(theme.typography.button)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(theme.spacing.lg)
                        .background(theme.colors.primary)
                        .cornerRadius(theme.cornerRadius.md)
                }
                .padding(.horizontal, theme.spacing.huge)
                .padding(.top, theme.spacing.sm)
                .accessibilityIdentifier(AccessibilityIdentifiers.EmptyStateView.actionButton)
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
