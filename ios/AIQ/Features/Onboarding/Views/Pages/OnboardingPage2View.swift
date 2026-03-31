import SwiftUI

/// Onboarding Page 2: How Tests Work
/// Explains the test-taking process
struct OnboardingPage2View: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "puzzlepiece.extension.fill")
                    .font(.system(size: 80))
                    .foregroundColor(ColorPalette.statBlue)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : theme.animations.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("onboarding.page2.title")
                        .displayMediumFont()
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("onboarding.page2.subtitle")
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Process Steps
                VStack(spacing: DesignSystem.Spacing.lg) {
                    IconContentRow(
                        icon: "1.circle.fill",
                        iconColor: theme.colors.primary,
                        title: String(localized: "onboarding.page2.step1")
                    )

                    IconContentRow(
                        icon: "2.circle.fill",
                        iconColor: theme.colors.primary,
                        title: String(localized: "onboarding.page2.step2")
                    )

                    IconContentRow(
                        icon: "3.circle.fill",
                        iconColor: theme.colors.primary,
                        title: String(localized: "onboarding.page2.step3")
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.short),
                    value: isAnimating
                )

                // Info Note
                HStack(spacing: DesignSystem.Spacing.md) {
                    Image(systemName: "info.circle.fill")
                        .foregroundColor(theme.colors.info)
                        .accessibilityHidden(true)

                    Text("onboarding.page2.info.note")
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
        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.page2)
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
    OnboardingPage2View()
}

#Preview("Dark Mode") {
    OnboardingPage2View()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    OnboardingPage2View()
        .environment(\.sizeCategory, .accessibilityLarge)
}
