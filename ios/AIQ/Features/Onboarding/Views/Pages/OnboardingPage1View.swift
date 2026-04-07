import AIQSharedKit
import SwiftUI

/// Onboarding Page 1: Value Proposition
/// Explains what AIQ does and key benefits
struct OnboardingPage1View: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 80))
                    .foregroundStyle(theme.gradients.scoreGradient)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : theme.animations.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("onboarding.page1.title")
                        .displayMediumFont()
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("onboarding.page1.subtitle")
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Feature Highlights
                VStack(spacing: DesignSystem.Spacing.lg) {
                    IconContentRow(
                        icon: "chart.line.uptrend.xyaxis",
                        iconColor: theme.colors.statBlue,
                        title: String(localized: "onboarding.page1.feature.tracking")
                    )

                    IconContentRow(
                        icon: "brain.head.profile",
                        iconColor: theme.colors.statPurple,
                        title: String(localized: "onboarding.page1.feature.ai")
                    )

                    IconContentRow(
                        icon: "lock.shield.fill",
                        iconColor: theme.colors.successText,
                        title: String(localized: "onboarding.page1.feature.privacy")
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.short),
                    value: isAnimating
                )

                Spacer()
            }
            .padding(.top, DesignSystem.Spacing.xxxl)
            .padding(.bottom, DesignSystem.Spacing.xl)
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.page1)
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
    OnboardingPage1View()
}

#Preview("Dark Mode") {
    OnboardingPage1View()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    OnboardingPage1View()
        .environment(\.sizeCategory, .accessibilityLarge)
}
