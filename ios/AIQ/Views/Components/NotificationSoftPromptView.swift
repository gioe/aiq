import SwiftUI

/// A soft prompt view that educates users about notification value before requesting system permission
///
/// This view follows iOS best practices for "permission priming" - explaining why notifications are
/// valuable before triggering the system permission dialog. This approach improves permission acceptance rates.
///
/// Usage:
/// ```swift
/// .sheet(isPresented: $showSoftPrompt) {
///     NotificationSoftPromptView(
///         onEnableReminders: {
///             // Request system permission
///             await notificationManager.requestAuthorization()
///         },
///         onDismiss: {
///             // User declined - dismiss without requesting
///             showSoftPrompt = false
///         }
///     )
/// }
/// ```
struct NotificationSoftPromptView: View {
    // MARK: - Callbacks

    /// Called when user taps "Enable Reminders" button
    let onEnableReminders: () -> Void

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

            // Icon
            Image(systemName: "bell.badge.fill")
                .font(.system(size: DesignSystem.IconSize.huge))
                .foregroundColor(theme.colors.primary)
                .accessibilityHidden(true) // Decorative - message conveyed by text
                .padding(.bottom, theme.spacing.xxl)

            // Title
            Text("Don't Miss Your Next Test")
                .font(theme.typography.h1)
                .foregroundColor(theme.colors.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.bottom, theme.spacing.md)
                .accessibilityAddTraits(.isHeader)

            // Body copy
            Text("You'll test again in 3 months. Get a reminder so you can track your cognitive trends.")
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
                    title: "Enable Reminders",
                    action: handleEnableReminders,
                    accessibilityId: "enableRemindersButton"
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
                .accessibilityHint("Double tap to dismiss without enabling reminders")
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

    /// Handle enable reminders action
    private func handleEnableReminders() {
        dismiss()
        onEnableReminders()
    }

    /// Handle dismiss action
    private func handleDismiss() {
        dismiss()
        onDismiss()
    }
}

// MARK: - Previews

#Preview("Default") {
    NotificationSoftPromptView(
        onEnableReminders: {
            print("Enable reminders tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
}

#Preview("iPhone SE") {
    NotificationSoftPromptView(
        onEnableReminders: {
            print("Enable reminders tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
    .previewDevice(PreviewDevice(rawValue: "iPhone SE (3rd generation)"))
}

#Preview("iPhone 15 Pro Max") {
    NotificationSoftPromptView(
        onEnableReminders: {
            print("Enable reminders tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
    .previewDevice(PreviewDevice(rawValue: "iPhone 15 Pro Max"))
}

#Preview("Large Text") {
    NotificationSoftPromptView(
        onEnableReminders: {
            print("Enable reminders tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
    .environment(\.sizeCategory, .accessibilityExtraExtraExtraLarge)
}

#Preview("Dark Mode") {
    NotificationSoftPromptView(
        onEnableReminders: {
            print("Enable reminders tapped")
        },
        onDismiss: {
            print("Dismissed")
        }
    )
    .preferredColorScheme(.dark)
}
