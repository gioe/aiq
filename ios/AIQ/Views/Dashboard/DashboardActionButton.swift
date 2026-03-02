import SwiftUI

/// Action button for the Dashboard — starts a new test or resumes an in-progress one.
struct DashboardActionButton: View {
    let hasActiveTest: Bool
    let onTap: () -> Void

    var body: some View {
        Button {
            onTap()
        } label: {
            HStack(spacing: DesignSystem.Spacing.sm) {
                Image(systemName: hasActiveTest ? "play.circle.fill" : "brain.head.profile")
                    .font(.system(size: DesignSystem.IconSize.md, weight: .semibold))

                Text(hasActiveTest ? "Resume Test in Progress" : "Take Another Test")
                    .font(Typography.button)

                Spacer()

                Image(systemName: "arrow.right.circle.fill")
                    .font(.system(size: DesignSystem.IconSize.md))
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(DesignSystem.Spacing.lg)
            .background(
                LinearGradient(
                    colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.8)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .cornerRadius(DesignSystem.CornerRadius.lg)
            .shadow(
                color: ColorPalette.primary.opacity(0.3),
                radius: 8,
                x: 0,
                y: 4
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel(hasActiveTest ? "Resume Test in Progress" : "Take Another Test")
        .accessibilityHint(
            hasActiveTest
                ? "Continue your in-progress cognitive performance test"
                : "Start a new cognitive performance test"
        )
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.actionButton)
    }
}

#Preview {
    VStack(spacing: DesignSystem.Spacing.lg) {
        DashboardActionButton(hasActiveTest: false, onTap: {})
        DashboardActionButton(hasActiveTest: true, onTap: {})
    }
    .padding()
}
