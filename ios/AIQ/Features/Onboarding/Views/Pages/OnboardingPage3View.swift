import SwiftUI

/// Onboarding Page 3: Testing Frequency
/// Explains the 3-month testing recommendation
struct OnboardingPage3View: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "calendar.badge.clock")
                    .font(.system(size: 80))
                    .foregroundColor(theme.colors.statPurple)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : theme.animations.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("onboarding.page3.title")
                        .displayMediumFont()
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("onboarding.page3.subtitle")
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Rationale Cards
                VStack(spacing: DesignSystem.Spacing.lg) {
                    IconContentCard(
                        icon: "brain.head.profile",
                        iconColor: theme.colors.statPurple,
                        title: String(localized: "onboarding.page3.rationale.neuroplasticity.title"),
                        description: String(localized: "onboarding.page3.rationale.neuroplasticity.description")
                    )

                    IconContentCard(
                        icon: "chart.xyaxis.line",
                        iconColor: theme.colors.statBlue,
                        title: String(localized: "onboarding.page3.rationale.trends.title"),
                        description: String(localized: "onboarding.page3.rationale.trends.description")
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.short),
                    value: isAnimating
                )

                // Reminder Note
                HStack(spacing: DesignSystem.Spacing.md) {
                    Image(systemName: "bell.fill")
                        .foregroundColor(theme.colors.info)
                        .accessibilityHidden(true)

                    Text("onboarding.page3.reminder.note")
                        .font(theme.typography.bodyMedium)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.leading)

                    Spacer()
                }
                .padding(DesignSystem.Spacing.md)
                .background(theme.colors.backgroundSecondary)
                .cornerRadius(DesignSystem.CornerRadius.md)
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .animation(
                    reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.medium),
                    value: isAnimating
                )
                .accessibilityElement(children: .combine)

                Spacer()
            }
            .padding(.top, DesignSystem.Spacing.xxxl)
            .padding(.bottom, DesignSystem.Spacing.xl)
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.page3)
        .onAppear {
            if reduceMotion {
                isAnimating = true
            } else {
                withAnimation(theme.animations.bouncy) {
                    isAnimating = true
                }
            }
        }
    }
}

// MARK: - Previews

#Preview("Light Mode") {
    OnboardingPage3View()
}

#Preview("Dark Mode") {
    OnboardingPage3View()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    OnboardingPage3View()
        .environment(\.sizeCategory, .accessibilityLarge)
}
