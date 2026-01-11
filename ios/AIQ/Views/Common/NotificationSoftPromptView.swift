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
                    foregroundColor: ColorPalette.textSecondary
                )
            }
            .padding(.horizontal, DesignSystem.Spacing.lg)
            .padding(.top, DesignSystem.Spacing.lg)

            Spacer()

            // Icon
            Image(systemName: "bell.badge.fill")
                .font(.system(size: DesignSystem.IconSize.huge))
                .foregroundColor(ColorPalette.primary)
                .accessibilityHidden(true) // Decorative - message conveyed by text
                .padding(.bottom, DesignSystem.Spacing.xxl)

            // Title
            Text("Don't Miss Your Next Test")
                .font(Typography.h1)
                .foregroundColor(ColorPalette.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.bottom, DesignSystem.Spacing.md)
                .accessibilityAddTraits(.isHeader)

            // Body copy
            Text("You'll test again in 3 months. Get a reminder so you can track your cognitive trends.")
                .font(Typography.bodyLarge)
                .foregroundColor(ColorPalette.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignSystem.Spacing.xxxl)
                .padding(.bottom, DesignSystem.Spacing.xxxl)

            Spacer()

            // Action buttons
            VStack(spacing: DesignSystem.Spacing.md) {
                // Primary action
                PrimaryButton(
                    title: "Enable Reminders",
                    action: handleEnableReminders,
                    accessibilityId: "enableRemindersButton"
                )

                // Secondary action
                Button(action: handleDismiss) {
                    Text("Not Now")
                        .font(Typography.button)
                        .foregroundColor(ColorPalette.textSecondary)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 44) // Ensure minimum touch target
                }
                .accessibilityLabel("Not now")
                .accessibilityHint("Double tap to dismiss without enabling reminders")
                .accessibilityIdentifier("notNowButton")
            }
            .padding(.horizontal, DesignSystem.Spacing.xxl)
            .padding(.bottom, DesignSystem.Spacing.xxxl)
        }
        .background(ColorPalette.background)
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
