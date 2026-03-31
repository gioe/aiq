import SwiftUI

/// Action button for the Dashboard — starts a new test or resumes an in-progress one.
struct DashboardActionButton: View {
    let hasActiveTest: Bool
    let onTap: () -> Void
    let label: String?

    @Environment(\.appTheme) private var theme

    init(hasActiveTest: Bool, onTap: @escaping () -> Void, label: String? = nil) {
        self.hasActiveTest = hasActiveTest
        self.onTap = onTap
        self.label = label
    }

    private var resolvedLabel: String {
        label ?? (hasActiveTest ? "Resume Test in Progress" : "Take Another Test")
    }

    private var resolvedHint: String {
        if hasActiveTest {
            return "Continue your in-progress cognitive performance test"
        }
        return label != nil
            ? "Start your first cognitive performance test"
            : "Start a new cognitive performance test"
    }

    var body: some View {
        Button {
            onTap()
        } label: {
            HStack(spacing: DesignSystem.Spacing.sm) {
                Image(systemName: hasActiveTest ? "play.circle.fill" : "brain.head.profile")
                    .font(.system(size: theme.iconSizes.md, weight: .semibold))

                Text(resolvedLabel)
                    .font(theme.typography.button)

                Spacer()

                Image(systemName: "arrow.right.circle.fill")
                    .font(.system(size: theme.iconSizes.md))
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(DesignSystem.Spacing.lg)
            .background(
                LinearGradient(
                    colors: [theme.colors.primary, theme.colors.primary.opacity(0.8)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg))
            .shadow(
                color: theme.colors.primary.opacity(0.3),
                radius: 8,
                x: 0,
                y: 4
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel(resolvedLabel)
        .accessibilityHint(resolvedHint)
        .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.actionButton)
    }
}

#Preview("Default") {
    DashboardActionButton(hasActiveTest: false, onTap: {}).padding()
}

#Preview("Active Test") {
    DashboardActionButton(hasActiveTest: true, onTap: {}).padding()
}

#Preview("Custom Label") {
    DashboardActionButton(hasActiveTest: false, onTap: {}, label: "Start Your First Test").padding()
}
