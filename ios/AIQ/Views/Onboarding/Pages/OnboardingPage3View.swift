import SwiftUI

/// Onboarding Page 3: Testing Frequency
/// Explains the 3-month testing recommendation
struct OnboardingPage3View: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "calendar.badge.clock")
                    .font(.system(size: 80))
                    .foregroundColor(ColorPalette.statPurple)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : DesignSystem.Animation.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("onboarding.page3.title")
                        .displayMediumFont()
                        .foregroundColor(ColorPalette.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("onboarding.page3.subtitle")
                        .font(Typography.bodyLarge)
                        .foregroundColor(ColorPalette.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Rationale Cards
                VStack(spacing: DesignSystem.Spacing.lg) {
                    RationaleCard(
                        icon: "brain.head.profile",
                        title: String(localized: "onboarding.page3.rationale.neuroplasticity.title"),
                        description: String(localized: "onboarding.page3.rationale.neuroplasticity.description"),
                        iconColor: ColorPalette.statPurple
                    )

                    RationaleCard(
                        icon: "chart.xyaxis.line",
                        title: String(localized: "onboarding.page3.rationale.trends.title"),
                        description: String(localized: "onboarding.page3.rationale.trends.description"),
                        iconColor: ColorPalette.statBlue
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : DesignSystem.Animation.smooth.delay(DesignSystem.AnimationDelay.short),
                    value: isAnimating
                )

                // Reminder Note
                HStack(spacing: DesignSystem.Spacing.md) {
                    Image(systemName: "bell.fill")
                        .foregroundColor(ColorPalette.info)
                        .accessibilityHidden(true)

                    Text("onboarding.page3.reminder.note")
                        .font(Typography.bodyMedium)
                        .foregroundColor(ColorPalette.textSecondary)
                        .multilineTextAlignment(.leading)

                    Spacer()
                }
                .padding(DesignSystem.Spacing.md)
                .background(ColorPalette.backgroundSecondary)
                .cornerRadius(DesignSystem.CornerRadius.md)
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .animation(
                    reduceMotion ? nil : DesignSystem.Animation.smooth.delay(DesignSystem.AnimationDelay.medium),
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
                withAnimation(DesignSystem.Animation.bouncy) {
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
