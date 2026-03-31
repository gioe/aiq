import SwiftUI

/// A reusable centered confirmation modal with a dimmed backdrop, icon, title, message, and confirm/cancel buttons.
///
/// Use `ConfirmationModal` wherever a destructive or high-stakes action needs explicit user confirmation.
/// The modal reproduces the full-screen ZStack pattern: a semi-transparent black backdrop that dismisses
/// on tap, and a floating card that contains an icon, title, message, and two action buttons.
public struct ConfirmationModal: View {
    /// The SF Symbol name rendered as the modal's decorative icon.
    public let iconName: String
    /// The bold heading displayed below the icon.
    public let title: String
    /// The descriptive body text explaining the action.
    public let message: String
    /// The label shown on the destructive confirm button.
    public let confirmLabel: String
    /// The VoiceOver accessibility label for the confirm button.
    public let confirmAccessibilityLabel: String
    /// The VoiceOver accessibility hint for the confirm button.
    public let confirmAccessibilityHint: String
    /// The accessibility identifier for the confirm button.
    public let confirmAccessibilityIdentifier: String
    /// The VoiceOver accessibility hint for the cancel button.
    public let cancelAccessibilityHint: String
    /// The accessibility identifier for the cancel button.
    public let cancelAccessibilityIdentifier: String
    /// The accessibility identifier for the modal container.
    public let modalAccessibilityIdentifier: String
    /// Called when the user taps the confirm button.
    public let onConfirm: () -> Void
    /// Called when the user taps the cancel button or the backdrop.
    public let onCancel: () -> Void

    @Environment(\.appTheme) private var theme

    /// Creates a `ConfirmationModal` with the provided configuration.
    public init(
        iconName: String,
        title: String,
        message: String,
        confirmLabel: String,
        confirmAccessibilityLabel: String,
        confirmAccessibilityHint: String,
        confirmAccessibilityIdentifier: String,
        cancelAccessibilityHint: String,
        cancelAccessibilityIdentifier: String,
        modalAccessibilityIdentifier: String,
        onConfirm: @escaping () -> Void,
        onCancel: @escaping () -> Void
    ) {
        self.iconName = iconName
        self.title = title
        self.message = message
        self.confirmLabel = confirmLabel
        self.confirmAccessibilityLabel = confirmAccessibilityLabel
        self.confirmAccessibilityHint = confirmAccessibilityHint
        self.confirmAccessibilityIdentifier = confirmAccessibilityIdentifier
        self.cancelAccessibilityHint = cancelAccessibilityHint
        self.cancelAccessibilityIdentifier = cancelAccessibilityIdentifier
        self.modalAccessibilityIdentifier = modalAccessibilityIdentifier
        self.onConfirm = onConfirm
        self.onCancel = onCancel
    }

    public var body: some View {
        ZStack {
            Color.black.opacity(0.4)
                .ignoresSafeArea()
                .onTapGesture { onCancel() }

            VStack(spacing: theme.spacing.lg) {
                Image(systemName: iconName)
                    .font(.system(size: 32))
                    .foregroundColor(theme.colors.error)
                    .accessibilityHidden(true)

                Text(title)
                    .font(theme.typography.h3)
                    .foregroundColor(theme.colors.textPrimary)

                Text(message)
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .multilineTextAlignment(.center)

                VStack(spacing: theme.spacing.sm) {
                    Button {
                        onConfirm()
                    } label: {
                        Text(confirmLabel)
                            .font(theme.typography.button)
                            .frame(maxWidth: .infinity)
                            .padding(theme.spacing.lg)
                            .background(theme.colors.error)
                            .foregroundColor(.white)
                            .cornerRadius(theme.cornerRadius.md)
                    }
                    .accessibilityLabel(confirmAccessibilityLabel)
                    .accessibilityHint(confirmAccessibilityHint)
                    .accessibilityIdentifier(confirmAccessibilityIdentifier)

                    Button {
                        onCancel()
                    } label: {
                        Text("Cancel")
                            .font(theme.typography.button)
                            .frame(maxWidth: .infinity)
                            .padding(theme.spacing.lg)
                            .background(theme.colors.backgroundSecondary)
                            .foregroundColor(theme.colors.textPrimary)
                            .cornerRadius(theme.cornerRadius.md)
                    }
                    .accessibilityLabel("Cancel")
                    .accessibilityHint(cancelAccessibilityHint)
                    .accessibilityIdentifier(cancelAccessibilityIdentifier)
                }
            }
            .padding(theme.spacing.xxl)
            .background(
                RoundedRectangle(cornerRadius: theme.cornerRadius.xl)
                    .fill(theme.colors.background)
                    .shadowStyle(theme.shadows.lg)
            )
            .padding(theme.spacing.xl)
        }
        .accessibilityElement(children: .contain)
        .accessibilityAddTraits(.isModal)
        .accessibilityIdentifier(modalAccessibilityIdentifier)
    }
}

#Preview("Logout") {
    ZStack {
        ColorPalette.background.ignoresSafeArea()
        ConfirmationModal(
            iconName: "rectangle.portrait.and.arrow.right",
            title: "Logout",
            message: "Are you sure you want to logout?",
            confirmLabel: "Logout",
            confirmAccessibilityLabel: "Logout",
            confirmAccessibilityHint: "Double tap to confirm logout",
            confirmAccessibilityIdentifier: "settingsView.logoutConfirmButton",
            cancelAccessibilityHint: "Double tap to cancel logout",
            cancelAccessibilityIdentifier: "settingsView.logoutCancelButton",
            modalAccessibilityIdentifier: "settingsView.logoutConfirmationModal",
            onConfirm: {},
            onCancel: {}
        )
    }
}

#Preview("Delete Account") {
    ZStack {
        ColorPalette.background.ignoresSafeArea()
        ConfirmationModal(
            iconName: "trash.circle",
            title: "Delete Account",
            message: "This action is irreversible. All your data will be permanently deleted and cannot be recovered.",
            confirmLabel: "Delete Account",
            confirmAccessibilityLabel: "Delete Account",
            confirmAccessibilityHint: "Double tap to permanently delete your account",
            confirmAccessibilityIdentifier: "settingsView.deleteAccountConfirmButton",
            cancelAccessibilityHint: "Double tap to cancel account deletion",
            cancelAccessibilityIdentifier: "settingsView.deleteAccountCancelButton",
            modalAccessibilityIdentifier: "settingsView.deleteAccountConfirmationModal",
            onConfirm: {},
            onCancel: {}
        )
    }
}
