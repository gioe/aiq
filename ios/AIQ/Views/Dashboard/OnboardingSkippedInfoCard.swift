import SwiftUI

/// Info card displayed on the dashboard for users who skipped onboarding
///
/// This card provides a non-intrusive way to encourage users to learn about AIQ.
/// It shows an informational message with a CTA to view onboarding and can be dismissed.
/// Dismissal state is persisted to UserDefaults so it doesn't reappear.
struct OnboardingSkippedInfoCard: View {
    // MARK: - Properties

    /// Called when user taps "Learn More" to view onboarding
    let onLearnMore: () -> Void

    /// Called when user dismisses the card
    let onDismiss: () -> Void

    // MARK: - Body

    var body: some View {
        HStack(alignment: .top, spacing: DesignSystem.Spacing.md) {
            // Icon
            Image(systemName: "lightbulb.fill")
                .font(.system(size: DesignSystem.IconSize.lg))
                .foregroundStyle(
                    LinearGradient(
                        colors: [ColorPalette.info, ColorPalette.info.opacity(0.7)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .accessibilityHidden(true)

            // Content
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
                Text("onboarding.skipped.card.title".localized)
                    .font(Typography.bodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(ColorPalette.textPrimary)

                Text("onboarding.skipped.card.description".localized)
                    .font(Typography.bodySmall)
                    .foregroundColor(ColorPalette.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                // Learn More button
                Button {
                    onLearnMore()
                } label: {
                    HStack(spacing: DesignSystem.Spacing.xs) {
                        Text("onboarding.skipped.card.cta".localized)
                            .font(Typography.labelMedium)
                        Image(systemName: "arrow.right")
                            .font(.system(size: 12, weight: .semibold))
                    }
                    .foregroundColor(ColorPalette.primary)
                }
                .buttonStyle(.plain)
                .padding(.top, DesignSystem.Spacing.xs)
                .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.onboardingInfoCardCTA)
            }

            Spacer()

            // Dismiss button
            Button {
                onDismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(ColorPalette.textTertiary)
                    .frame(width: 28, height: 28)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("onboarding.skipped.card.dismiss.accessibility".localized)
            .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.onboardingInfoCardDismiss)
        }
        .padding(DesignSystem.Spacing.lg)
        .background(ColorPalette.info.opacity(0.08))
        .cornerRadius(DesignSystem.CornerRadius.lg)
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .strokeBorder(ColorPalette.info.opacity(0.2), lineWidth: 1)
        )
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.onboardingInfoCard)
    }
}

// MARK: - Previews

#Preview("Default") {
    OnboardingSkippedInfoCard(
        onLearnMore: { print("Learn More tapped") },
        onDismiss: { print("Dismiss tapped") }
    )
    .padding()
}

#Preview("In Dashboard Context") {
    ScrollView {
        VStack(spacing: DesignSystem.Spacing.xxl) {
            // Simulated welcome header
            VStack(spacing: DesignSystem.Spacing.md) {
                Text("Good morning!")
                    .font(Typography.h1)
                Text("Track your cognitive performance over time")
                    .font(Typography.bodyMedium)
                    .foregroundColor(ColorPalette.textSecondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, DesignSystem.Spacing.lg)

            // Info card
            OnboardingSkippedInfoCard(
                onLearnMore: { print("Learn More tapped") },
                onDismiss: { print("Dismiss tapped") }
            )

            // Simulated stats grid
            HStack(spacing: DesignSystem.Spacing.lg) {
                RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                    .fill(ColorPalette.backgroundSecondary)
                    .frame(height: 80)

                RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                    .fill(ColorPalette.backgroundSecondary)
                    .frame(height: 80)
            }

            Spacer()
        }
        .padding(DesignSystem.Spacing.lg)
    }
}

#Preview("Dark Mode") {
    OnboardingSkippedInfoCard(
        onLearnMore: { print("Learn More tapped") },
        onDismiss: { print("Dismiss tapped") }
    )
    .padding()
    .preferredColorScheme(.dark)
}

#Preview("Large Dynamic Type") {
    OnboardingSkippedInfoCard(
        onLearnMore: { print("Learn More tapped") },
        onDismiss: { print("Dismiss tapped") }
    )
    .padding()
    .environment(\.dynamicTypeSize, .accessibility3)
}
