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
                    Text("onboarding.page2.title")
                        .font(Typography.displayMedium)
                        .foregroundColor(ColorPalette.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("onboarding.page2.subtitle")
                        .font(Typography.bodyLarge)
                        .foregroundColor(ColorPalette.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Process Steps
                VStack(spacing: DesignSystem.Spacing.lg) {
                    ProcessStepRow(
                        number: 1,
                        text: String(localized: "onboarding.page2.step1")
                    )

                    ProcessStepRow(
                        number: 2,
                        text: String(localized: "onboarding.page2.step2")
                    )

                    ProcessStepRow(
                        number: 3,
                        text: String(localized: "onboarding.page2.step3")
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

                    Text("onboarding.page2.info.note")
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
