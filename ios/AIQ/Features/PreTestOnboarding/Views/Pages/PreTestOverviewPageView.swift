import AIQSharedKit
import SwiftUI

/// Pre-test onboarding Page 1: Test Overview
/// Explains question count, time limit, and baseline scoring
struct PreTestOverviewPageView: View {
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
                    Text("pretest.onboarding.page1.title")
                        .displayMediumFont()
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("pretest.onboarding.page1.subtitle")
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Test Details
                VStack(spacing: DesignSystem.Spacing.lg) {
                    IconContentRow(
                        icon: "list.bullet.clipboard.fill",
                        iconColor: theme.colors.statBlue,
                        title: String(localized: "pretest.onboarding.page1.questions")
                    )

                    IconContentRow(
                        icon: "clock.fill",
                        iconColor: theme.colors.statPurple,
                        title: String(localized: "pretest.onboarding.page1.time")
                    )

                    IconContentRow(
                        icon: "chart.bar.fill",
                        iconColor: theme.colors.successText,
                        title: String(localized: "pretest.onboarding.page1.baseline")
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
        .accessibilityIdentifier(AccessibilityIdentifiers.PreTestOnboardingView.page1)
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
    PreTestOverviewPageView()
}

#Preview("Dark Mode") {
    PreTestOverviewPageView()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    PreTestOverviewPageView()
        .environment(\.sizeCategory, .accessibilityLarge)
}
