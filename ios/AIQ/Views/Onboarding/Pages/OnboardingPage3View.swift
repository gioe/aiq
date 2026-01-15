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
                    Text("Test Every 3 Months")
                        .font(Typography.displayMedium)
                        .foregroundColor(ColorPalette.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    // swiftlint:disable:next line_length
                    Text("We recommend testing every 3 months for the most meaningful insights into your cognitive capacity.")
                        .font(Typography.bodyLarge)
                        .foregroundColor(ColorPalette.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Rationale Cards
                VStack(spacing: DesignSystem.Spacing.lg) {
                    RationaleCard(
                        icon: "brain.head.profile",
                        title: "Neuroplasticity Takes Time",
                        // swiftlint:disable:next line_length
                        description: "Your cognitive abilities don't change overnight. Testing every 3 months gives your brain time to adapt and grow.",
                        iconColor: ColorPalette.statPurple
                    )

                    RationaleCard(
                        icon: "chart.xyaxis.line",
                        title: "Meaningful Trends",
                        // swiftlint:disable:next line_length
                        description: "Spacing tests allows you to see real trends in your performance, not just daily fluctuations.",
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

                    Text("You can enable reminders in Settings to help you track your progress.")
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

#Preview {
    OnboardingPage3View()
}
