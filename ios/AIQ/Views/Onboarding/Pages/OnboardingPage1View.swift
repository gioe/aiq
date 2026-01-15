import SwiftUI

/// Onboarding Page 1: Value Proposition
/// Explains what AIQ does and key benefits
struct OnboardingPage1View: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 80))
                    .foregroundStyle(ColorPalette.scoreGradient)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : DesignSystem.Animation.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("Track Your Cognitive Capacity")
                        .font(Typography.displayMedium)
                        .foregroundColor(ColorPalette.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    // swiftlint:disable:next line_length
                    Text("AIQ helps you measure and monitor your cognitive performance over time through scientifically-designed assessments.")
                        .font(Typography.bodyLarge)
                        .foregroundColor(ColorPalette.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Feature Highlights
                VStack(spacing: DesignSystem.Spacing.lg) {
                    FeatureHighlightRow(
                        icon: "chart.line.uptrend.xyaxis",
                        text: "Track your cognitive performance over time",
                        iconColor: ColorPalette.statBlue
                    )

                    FeatureHighlightRow(
                        icon: "brain.head.profile",
                        text: "Fresh questions generated daily using AI",
                        iconColor: ColorPalette.statPurple
                    )

                    FeatureHighlightRow(
                        icon: "lock.shield.fill",
                        text: "Private and secure - your data stays yours",
                        iconColor: ColorPalette.successText
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : DesignSystem.Animation.smooth.delay(DesignSystem.AnimationDelay.short),
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
                withAnimation(DesignSystem.Animation.bouncy) {
                    isAnimating = true
                }
            }
        }
    }
}

#Preview {
    OnboardingPage1View()
}
