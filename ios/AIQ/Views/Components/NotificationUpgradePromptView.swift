import AIQSharedKit
import SwiftUI

/// A prompt view shown to provisional notification users when they tap a notification
///
/// This view encourages users who have engaged with a provisional (silent) notification
/// to upgrade to full notification permissions. Since the user has already demonstrated
/// interest by tapping the notification, they are a high-value target for full authorization.
///
/// Usage:
/// ```swift
/// .sheet(isPresented: $showUpgradePrompt) {
///     NotificationUpgradePromptView(
///         onEnableNotifications: {
///             // Request full system permission
///             let granted = await notificationManager.requestAuthorization()
///             if granted {
///                 analyticsService.trackNotificationFullPermissionGranted()
///             } else {
///                 analyticsService.trackNotificationFullPermissionDenied()
///             }
///         },
///         onDismiss: {
///             // User declined - dismiss without requesting
///             analyticsService.trackNotificationUpgradePromptDismissed()
///         }
///     )
/// }
/// ```
struct NotificationUpgradePromptView: View {
    // MARK: - Callbacks

    /// Called when user taps "Enable Notifications" button
    let onEnableNotifications: () -> Void

    /// Called when user taps "Not Now" button or dismisses via swipe
    let onDismiss: () -> Void

    // MARK: - Environment

    @Environment(\.dismiss) private var dismiss
    @Environment(\.appTheme) private var theme

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            // Close button
            HStack {
                Spacer()

                IconButton(
                    icon: "xmark",
                    action: handleDismiss,
                    accessibilityLabel: "Close notification prompt",
                    foregroundColor: theme.colors.textSecondary
                )
            }
            .padding(.horizontal, theme.spacing.lg)
            .padding(.top, theme.spacing.lg)

            Spacer()

            // Icon - using filled bell to emphasize the upgrade
            Image(systemName: "bell.badge.fill")
                .font(.system(size: theme.iconSizes.huge))
                .foregroundColor(theme.colors.primary)
                .accessibilityHidden(true) // Decorative - message conveyed by text
                .padding(.bottom, theme.spacing.xxl)

            // Title
            Text("Stay in the Loop")
                .font(theme.typography.h1)
                .foregroundColor(theme.colors.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.bottom, theme.spacing.md)
                .accessibilityAddTraits(.isHeader)

            // Body copy - acknowledges their engagement and explains benefit
            Text("You're tracking your cognitive trends. Enable full notifications so you never miss a test reminder.")
                .font(theme.typography.bodyLarge)
                .foregroundColor(theme.colors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, theme.spacing.xxxl)
                .padding(.bottom, theme.spacing.xxxl)

            Spacer()

            // Action buttons
            VStack(spacing: theme.spacing.md) {
                // Primary action
                PrimaryButton(
                    title: "Enable Notifications",
                    action: handleEnableNotifications,
                    accessibilityId: "enableNotificationsButton"
                )

                // Secondary action
                Button(action: handleDismiss) {
                    Text("Not Now")
                        .font(theme.typography.button)
                        .foregroundColor(theme.colors.textSecondary)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 44) // Ensure minimum touch target
                }
                .accessibilityLabel("Not now")
                .accessibilityHint("Double tap to dismiss without enabling notifications")
                .accessibilityIdentifier(AccessibilityIdentifiers.NotificationSoftPrompt.notNowButton)
            }
            .padding(.horizontal, theme.spacing.xxl)
            .padding(.bottom, theme.spacing.xxxl)
        }
        .background(theme.colors.background)
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }

    // MARK: - Private Methods

    /// Handle enable notifications action
    private func handleEnableNotifications() {
        dismiss()
        onEnableNotifications()
    }

    /// Handle dismiss action
    private func handleDismiss() {
        dismiss()
        onDismiss()
    }
}

// MARK: - Previews

#Preview("Default") {
    NotificationUpgradePromptView(
        onEnableNotifications: {
            print("Enable notifications tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
}

#Preview("iPhone SE") {
    NotificationUpgradePromptView(
        onEnableNotifications: {
            print("Enable notifications tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
    .previewDevice(PreviewDevice(rawValue: "iPhone SE (3rd generation)"))
}

#Preview("Dark Mode") {
    NotificationUpgradePromptView(
        onEnableNotifications: {
            print("Enable notifications tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
    .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    NotificationUpgradePromptView(
        onEnableNotifications: {
            print("Enable notifications tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
    .environment(\.sizeCategory, .accessibilityExtraExtraExtraLarge)
}
