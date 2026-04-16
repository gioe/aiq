import AIQSharedKit
import SwiftUI

/// Pre-test onboarding Page 2: Testing Rules
/// Shows allowed and prohibited aids for accurate results
struct PreTestRulesPageView: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "checkmark.shield.fill")
                    .font(.system(size: 80))
                    .foregroundColor(theme.colors.statBlue)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : theme.animations.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("pretest.onboarding.page2.title")
                        .displayMediumFont()
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("pretest.onboarding.page2.subtitle")
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Allowed Aids
                VStack(alignment: .leading, spacing: DesignSystem.Spacing.md) {
                    Text("pretest.onboarding.page2.allowed.header")
                        .font(theme.typography.labelLarge)
                        .foregroundColor(theme.colors.successText)
                        .padding(.leading, DesignSystem.Spacing.xs)

                    IconContentRow(
                        icon: "pencil.and.outline",
                        iconColor: theme.colors.successText,
                        title: String(localized: "pretest.onboarding.page2.allowed.pencil")
                    )

                    IconContentRow(
                        icon: "speaker.slash.fill",
                        iconColor: theme.colors.successText,
                        title: String(localized: "pretest.onboarding.page2.allowed.quiet")
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.short),
                    value: isAnimating
                )

                // Prohibited Aids
                VStack(alignment: .leading, spacing: DesignSystem.Spacing.md) {
                    Text("pretest.onboarding.page2.prohibited.header")
                        .font(theme.typography.labelLarge)
                        .foregroundColor(theme.colors.error)
                        .padding(.leading, DesignSystem.Spacing.xs)

                    IconContentRow(
                        icon: "function",
                        iconColor: theme.colors.error,
                        title: String(localized: "pretest.onboarding.page2.prohibited.calculator")
                    )

                    IconContentRow(
                        icon: "iphone.slash",
                        iconColor: theme.colors.error,
                        title: String(localized: "pretest.onboarding.page2.prohibited.phone")
                    )

                    IconContentRow(
                        icon: "person.2.slash.fill",
                        iconColor: theme.colors.error,
                        title: String(localized: "pretest.onboarding.page2.prohibited.help")
                    )

                    IconContentRow(
                        icon: "book.closed.fill",
                        iconColor: theme.colors.error,
                        title: String(localized: "pretest.onboarding.page2.prohibited.reference")
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.medium),
                    value: isAnimating
                )

                Spacer()
            }
            .padding(.top, DesignSystem.Spacing.xxxl)
            .padding(.bottom, DesignSystem.Spacing.xl)
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.PreTestOnboardingView.page2)
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
    PreTestRulesPageView()
}

#Preview("Dark Mode") {
    PreTestRulesPageView()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    PreTestRulesPageView()
        .environment(\.sizeCategory, .accessibilityLarge)
}
