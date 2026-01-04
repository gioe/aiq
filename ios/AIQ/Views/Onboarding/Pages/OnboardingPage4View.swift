import SwiftUI

/// Onboarding Page 4: Privacy & Security
/// Explains privacy features and provides link to privacy policy
struct OnboardingPage4View: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "lock.shield.fill")
                    .font(.system(size: 80))
                    .foregroundColor(ColorPalette.successText)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : DesignSystem.Animation.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("Your Data is Secure")
                        .font(Typography.displayMedium)
                        .foregroundColor(ColorPalette.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    // swiftlint:disable:next line_length
                    Text("We take your privacy seriously. Your cognitive data is protected with industry-leading security.")
                        .font(Typography.bodyLarge)
                        .foregroundColor(ColorPalette.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Privacy Features
                VStack(spacing: DesignSystem.Spacing.lg) {
                    PrivacyFeatureRow(text: "End-to-end encryption for all test data")
                    PrivacyFeatureRow(text: "No sale of personal information to third parties")
                    PrivacyFeatureRow(text: "GDPR and CCPA compliant data handling")
                    PrivacyFeatureRow(text: "Your results are private and only visible to you")
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                .animation(
                    reduceMotion ? nil : DesignSystem.Animation.smooth.delay(0.2),
                    value: isAnimating
                )

                // Privacy Policy Link
                VStack(spacing: DesignSystem.Spacing.sm) {
                    Text("For more details, read our")
                        .font(Typography.bodyMedium)
                        .foregroundColor(ColorPalette.textSecondary)

                    Link("Privacy Policy", destination: privacyPolicyURL)
                        .font(Typography.labelLarge)
                        .foregroundColor(ColorPalette.primary)
                        .frame(minHeight: 44)
                        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.privacyPolicyLink)
                        .accessibilityHint("Opens privacy policy in Safari")
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .animation(
                    reduceMotion ? nil : DesignSystem.Animation.smooth.delay(0.4),
                    value: isAnimating
                )

                Spacer()
            }
            .padding(.top, DesignSystem.Spacing.xxxl)
            .padding(.bottom, DesignSystem.Spacing.xl)
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.page4)
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

    // MARK: - Computed Properties

    /// URL to the privacy policy document
    /// This is a hardcoded, valid URL that is unlikely to change
    private var privacyPolicyURL: URL {
        // swiftlint:disable:next force_unwrapping
        URL(string: "https://aiq.app/privacy-policy")!
    }
}

#Preview {
    OnboardingPage4View()
}
