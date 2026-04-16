import AIQSharedKit
import SwiftUI

/// Pre-test onboarding Page 4: Notifications (conditional)
/// Integrated notification permission pitch as the final onboarding page
struct PreTestNotificationsPageView: View {
    /// Called when user taps "Enable Reminders"
    let onEnableReminders: () -> Void

    /// Called when user taps "Not Now"
    let onDeclineReminders: () -> Void

    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme
    @State private var isAnimating = false

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Header Icon
                Image(systemName: "bell.badge.fill")
                    .font(.system(size: 80))
                    .foregroundColor(theme.colors.primary)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                    .animation(
                        reduceMotion ? nil : theme.animations.bouncy.repeatForever(autoreverses: true),
                        value: isAnimating
                    )
                    .accessibilityHidden(true)

                // Headline and Body
                VStack(spacing: DesignSystem.Spacing.lg) {
                    Text("pretest.onboarding.page4.title")
                        .displayMediumFont()
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)

                    Text("pretest.onboarding.page4.subtitle")
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DesignSystem.Spacing.xl)

                // Body copy
                Text("pretest.onboarding.page4.body")
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, DesignSystem.Spacing.xxl)
                    .opacity(isAnimating ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                    .animation(
                        reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.short),
                        value: isAnimating
                    )

                Spacer()

                // Notification action buttons
                VStack(spacing: DesignSystem.Spacing.md) {
                    PrimaryButton(
                        title: String(localized: "pretest.onboarding.enable.reminders"),
                        action: onEnableReminders,
                        accessibilityId: AccessibilityIdentifiers.PreTestOnboardingView.enableRemindersButton
                    )

                    Button(action: onDeclineReminders) {
                        Text("pretest.onboarding.not.now")
                            .font(theme.typography.button)
                            .foregroundColor(theme.colors.textSecondary)
                            .frame(maxWidth: .infinity)
                            .frame(minHeight: 44)
                    }
                    .accessibilityLabel(String(localized: "pretest.onboarding.not.now"))
                    .accessibilityHint(
                        String(localized: "pretest.onboarding.not.now.hint")
                    )
                    .accessibilityIdentifier(AccessibilityIdentifiers.PreTestOnboardingView.notNowButton)
                }
                .padding(.horizontal, DesignSystem.Spacing.xxl)
                .opacity(isAnimating ? 1.0 : 0.0)
                .animation(
                    reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.medium),
                    value: isAnimating
                )
            }
            .padding(.top, DesignSystem.Spacing.xxxl)
            .padding(.bottom, DesignSystem.Spacing.xl)
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.PreTestOnboardingView.page4)
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
    PreTestNotificationsPageView(
        onEnableReminders: {},
        onDeclineReminders: {}
    )
}

#Preview("Dark Mode") {
    PreTestNotificationsPageView(
        onEnableReminders: {},
        onDeclineReminders: {}
    )
    .preferredColorScheme(.dark)
}
