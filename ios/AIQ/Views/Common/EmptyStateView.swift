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
        VStack(spacing: DesignSystem.Spacing.xxl) {
            Spacer()

            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.huge))
                .foregroundColor(ColorPalette.primary.opacity(0.6))
                .accessibilityHidden(true) // Decorative icon

            VStack(spacing: DesignSystem.Spacing.md) {
                Text(title)
                    .font(Typography.h2)
                    .foregroundColor(ColorPalette.textPrimary)

                Text(message)
                    .font(Typography.bodyMedium)
                    .foregroundColor(ColorPalette.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, DesignSystem.Spacing.huge)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(title). \(message)")

            if let actionTitle, let action {
                Button(action: action) {
                    Text(actionTitle)
                        .font(Typography.button)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(DesignSystem.Spacing.lg)
                        .background(ColorPalette.primary)
                        .cornerRadius(DesignSystem.CornerRadius.md)
                }
                .padding(.horizontal, DesignSystem.Spacing.huge)
                .padding(.top, DesignSystem.Spacing.sm)
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
