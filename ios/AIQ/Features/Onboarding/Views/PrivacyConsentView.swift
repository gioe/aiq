import AIQSharedKit
import SwiftUI

/// Privacy consent screen shown on first app launch
/// Users must accept privacy policy and terms of service to continue
struct PrivacyConsentView: View {
    @Binding var hasAcceptedConsent: Bool
    @State private var isAnimating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    private let privacyConsentStorage: PrivacyConsentStorageProtocol

    init(
        hasAcceptedConsent: Binding<Bool>,
        privacyConsentStorage: PrivacyConsentStorageProtocol = PrivacyConsentStorage.shared
    ) {
        _hasAcceptedConsent = hasAcceptedConsent
        self.privacyConsentStorage = privacyConsentStorage
    }

    var body: some View {
        NavigationStack {
            ZStack {
                // Gradient Background
                theme.gradients.scoreGradient
                    .opacity(0.15)
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: DesignSystem.Spacing.xxxl) {
                        // Header
                        VStack(spacing: DesignSystem.Spacing.lg) {
                            Image(systemName: "hand.raised.fill")
                                .font(.system(size: 80))
                                .foregroundStyle(theme.gradients.scoreGradient)
                                .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                                .animation(
                                    reduceMotion
                                        ? nil
                                        : Animation.easeInOut(duration: 2.0).repeatForever(autoreverses: true),
                                    value: isAnimating
                                )
                                .accessibilityIdentifier(AccessibilityIdentifiers.PrivacyConsentView.privacyIcon)

                            Text("Privacy & Terms")
                                .displayMediumFont()
                                .foregroundStyle(theme.gradients.scoreGradient)
                                .multilineTextAlignment(.center)

                            Text("Your privacy matters to us")
                                .font(theme.typography.bodyLarge)
                                .foregroundColor(theme.colors.textSecondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding(.top, DesignSystem.Spacing.xl)
                        .onAppear {
                            if reduceMotion {
                                isAnimating = true
                            } else {
                                withAnimation(theme.animations.bouncy) {
                                    isAnimating = true
                                }
                            }
                        }

                        // Privacy Summary
                        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
                            privacyPointCard(
                                icon: "shield.checkered",
                                title: "Your Data is Protected",
                                description: "We use industry-standard encryption to keep your information secure.",
                                color: theme.colors.statGreen
                            )

                            privacyPointCard(
                                icon: "eye.slash.fill",
                                title: "No Sale of Data",
                                description: "We never sell your personal information to third parties.",
                                color: theme.colors.statBlue
                            )

                            privacyPointCard(
                                icon: "brain.head.profile",
                                title: "Your Results",
                                description: "Test results are stored securely and only accessible to you.",
                                color: theme.colors.statPurple
                            )

                            privacyPointCard(
                                icon: "chart.line.uptrend.xyaxis",
                                title: "Analytics",
                                description: "We collect anonymous usage data to improve the app experience.",
                                color: theme.colors.statOrange
                            )
                        }
                        .padding(.horizontal, DesignSystem.Spacing.xl)
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                        .animation(
                            reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.short),
                            value: isAnimating
                        )

                        // Legal Links
                        VStack(spacing: DesignSystem.Spacing.md) {
                            Text("By continuing, you agree to our:")
                                .font(theme.typography.bodyMedium)
                                .foregroundColor(theme.colors.textSecondary)
                                .multilineTextAlignment(.center)

                            HStack(spacing: DesignSystem.Spacing.lg) {
                                Link("Privacy Policy", destination: privacyPolicyURL)
                                    .font(theme.typography.labelMedium)
                                    .foregroundColor(theme.colors.primary)
                                    .accessibilityIdentifier(
                                        AccessibilityIdentifiers.PrivacyConsentView.privacyPolicyLink
                                    )

                                Text("•")
                                    .foregroundColor(theme.colors.textSecondary)

                                Link("Terms of Service", destination: termsOfServiceURL)
                                    .font(theme.typography.labelMedium)
                                    .foregroundColor(theme.colors.primary)
                                    .accessibilityIdentifier(
                                        AccessibilityIdentifiers.PrivacyConsentView.termsOfServiceLink
                                    )
                            }
                        }
                        .padding(.horizontal, DesignSystem.Spacing.xl)
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .animation(
                            reduceMotion
                                ? nil
                                : theme.animations.smooth.delay(DesignSystem.AnimationDelay.medium),
                            value: isAnimating
                        )

                        // Accept Button
                        PrimaryButton(
                            title: "I Agree & Continue",
                            action: acceptConsent,
                            accessibilityId: AccessibilityIdentifiers.PrivacyConsentView.acceptButton
                        )
                        .padding(.horizontal, DesignSystem.Spacing.xxl)
                        .padding(.top, DesignSystem.Spacing.xl)
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .animation(
                            reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.long),
                            value: isAnimating
                        )

                        Spacer()
                    }
                    .padding(.horizontal, DesignSystem.Spacing.xl)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .interactiveDismissDisabled(true) // Prevent dismissal without accepting
        }
    }

    // MARK: - Subviews

    /// Individual privacy point card with icon, title, and description
    private func privacyPointCard(
        icon: String,
        title: String,
        description: String,
        color: Color
    ) -> some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            // Icon
            Image(systemName: icon)
                .font(.system(size: theme.iconSizes.lg))
                .foregroundColor(color)
                .frame(width: 50, height: 50)
                .accessibilityHidden(true)

            // Text Content
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
                Text(title)
                    .font(theme.typography.bodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(theme.colors.textPrimary)

                Text(description)
                    .font(theme.typography.bodySmall)
                    .foregroundColor(theme.colors.textSecondary)
            }

            Spacer()
        }
        .padding(DesignSystem.Spacing.md)
        .background(theme.colors.backgroundSecondary)
        .cornerRadius(DesignSystem.CornerRadius.md)
        .shadowStyle(DesignSystem.Shadow.sm)
        .accessibilityLabel("\(title). \(description)")
    }

    // MARK: - Actions

    /// Save consent and dismiss the view
    private func acceptConsent() {
        privacyConsentStorage.saveConsent()

        withAnimation(theme.animations.smooth) {
            hasAcceptedConsent = true
        }
    }

    // MARK: - Computed Properties

    /// URL to the privacy policy document
    private var privacyPolicyURL: URL {
        // In production, this would be a web URL
        // For now, we'll use a placeholder that can be updated
        URL(string: "https://aiq.app/privacy-policy")!
    }

    /// URL to the terms of service document
    private var termsOfServiceURL: URL {
        // In production, this would be a web URL
        // For now, we'll use a placeholder that can be updated
        URL(string: "https://aiq.app/terms-of-service")!
    }
}

#Preview {
    PrivacyConsentView(hasAcceptedConsent: .constant(false))
}
