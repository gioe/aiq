import AIQSharedKit
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

    @Environment(\.appTheme) private var theme

    // MARK: - Body

    var body: some View {
        HStack(alignment: .top, spacing: DesignSystem.Spacing.md) {
            // Icon
            Image(systemName: "lightbulb.fill")
                .font(.system(size: theme.iconSizes.lg))
                .foregroundStyle(
                    LinearGradient(
                        colors: [theme.colors.info, theme.colors.info.opacity(0.7)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .accessibilityHidden(true)

            // Content
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
                Text("onboarding.skipped.card.title".localized)
                    .font(theme.typography.bodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(theme.colors.textPrimary)

                Text("onboarding.skipped.card.description".localized)
                    .font(theme.typography.bodySmall)
                    .foregroundColor(theme.colors.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                // Learn More button
                Button {
                    onLearnMore()
                } label: {
                    HStack(spacing: DesignSystem.Spacing.xs) {
                        Text("onboarding.skipped.card.cta".localized)
                            .font(theme.typography.labelMedium)
                        Image(systemName: "arrow.right")
                            .font(.system(size: 12, weight: .semibold))
                    }
                    .foregroundColor(theme.colors.primary)
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
                    .foregroundColor(theme.colors.textTertiary)
                    .frame(width: 28, height: 28)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("onboarding.skipped.card.dismiss.accessibility".localized)
            .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.onboardingInfoCardDismiss)
        }
        .padding(DesignSystem.Spacing.lg)
        .background(theme.colors.info.opacity(0.08))
        .cornerRadius(DesignSystem.CornerRadius.lg)
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .strokeBorder(theme.colors.info.opacity(0.2), lineWidth: 1)
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
                    .font(DefaultTheme().typography.h1)
                Text("Track your cognitive performance over time")
                    .font(DefaultTheme().typography.bodyMedium)
                    .foregroundColor(DefaultTheme().colors.textSecondary)
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
                    .fill(DefaultTheme().colors.backgroundSecondary)
                    .frame(height: 80)

                RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                    .fill(DefaultTheme().colors.backgroundSecondary)
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
