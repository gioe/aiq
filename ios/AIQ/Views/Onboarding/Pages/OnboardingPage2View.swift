import SwiftUI

/// Onboarding Page 2: How Tests Work
/// Explains the test-taking process
struct OnboardingPage2View: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
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
                        reduceMotion ? nil : DesignSystem.Animation.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("How AIQ Tests Work")
                        .font(Typography.displayMedium)
                        .foregroundColor(ColorPalette.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    // swiftlint:disable:next line_length
                    Text("Each test is designed to comprehensively assess your cognitive abilities across multiple domains.")
                        .font(Typography.bodyLarge)
                        .foregroundColor(ColorPalette.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Process Steps
                VStack(spacing: DesignSystem.Spacing.lg) {
                    ProcessStepRow(
                        number: 1,
                        text: "Answer 20 unique questions across different cognitive domains"
                    )

                    ProcessStepRow(
                        number: 2,
                        text: "Complete the test in one sitting (approximately 15-20 minutes)"
                    )

                    ProcessStepRow(
                        number: 3,
                        text: "Receive your IQ score and detailed performance breakdown"
                    )
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : DesignSystem.Animation.smooth.delay(DesignSystem.AnimationDelay.short),
                    value: isAnimating
                )

                // Info Note
                HStack(spacing: DesignSystem.Spacing.md) {
                    Image(systemName: "info.circle.fill")
                        .foregroundColor(ColorPalette.info)
                        .accessibilityHidden(true)

                    Text("Questions are refreshed daily, so every test is unique.")
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
        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.page2)
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
    OnboardingPage2View()
}
