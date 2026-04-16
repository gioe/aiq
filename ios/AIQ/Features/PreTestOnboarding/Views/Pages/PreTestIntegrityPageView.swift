import AIQSharedKit
import SwiftUI

/// Pre-test onboarding Page 3: Integrity
/// Explains pattern analysis and honest effort framing
struct PreTestIntegrityPageView: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "lock.shield.fill")
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
                    Text("pretest.onboarding.page3.title")
                        .displayMediumFont()
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("pretest.onboarding.page3.subtitle")
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Integrity Points
                VStack(spacing: DesignSystem.Spacing.lg) {
                    IconContentRow(
                        icon: "waveform.path.ecg",
                        iconColor: theme.colors.statBlue,
                        title: String(localized: "pretest.onboarding.page3.pattern")
                    )

                    IconContentRow(
                        icon: "hand.thumbsup.fill",
                        iconColor: theme.colors.successText,
                        title: String(localized: "pretest.onboarding.page3.honest")
                    )

                    IconContentRow(
                        icon: "chart.line.uptrend.xyaxis",
                        iconColor: theme.colors.statPurple,
                        title: String(localized: "pretest.onboarding.page3.track")
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
        .accessibilityIdentifier(AccessibilityIdentifiers.PreTestOnboardingView.page3)
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
    PreTestIntegrityPageView()
}

#Preview("Dark Mode") {
    PreTestIntegrityPageView()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    PreTestIntegrityPageView()
        .environment(\.sizeCategory, .accessibilityLarge)
}
