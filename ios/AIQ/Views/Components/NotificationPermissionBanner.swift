import SwiftUI

/// An informational banner that guides users to enable notification permissions in iOS Settings
/// Appears when notification permission is denied at the system level
struct NotificationPermissionBanner: View {
    let onOpenSettings: () -> Void

    @Environment(\.appTheme) private var theme

    var body: some View {
        Button {
            onOpenSettings()
        } label: {
            HStack(spacing: theme.spacing.md) {
                // Info icon
                Image(systemName: "info.circle.fill")
                    .foregroundColor(theme.colors.info)
                    .font(.system(size: 20))
                    .accessibilityHidden(true)

                // Message
                Text("notification.permission.denied.message".localized)
                    .font(theme.typography.bodySmall)
                    .foregroundColor(theme.colors.textPrimary)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)

                // Action indicator
                VStack(spacing: theme.spacing.xs) {
                    Text("notification.permission.open.settings".localized)
                        .font(theme.typography.labelSmall)
                        .foregroundColor(theme.colors.primary)

                    Image(systemName: "chevron.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(theme.colors.primary)
                }
                .accessibilityHidden(true)
            }
            .padding(theme.spacing.lg)
            .background(theme.colors.info.opacity(0.1))
            .cornerRadius(theme.cornerRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: theme.cornerRadius.md)
                    .stroke(theme.colors.info.opacity(0.2), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("notification.permission.banner.accessibility.label".localized)
        .accessibilityHint("notification.permission.banner.accessibility.hint".localized)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier(AccessibilityIdentifiers.NotificationPermissionBanner.banner)
    }
}

#Preview("Permission Banner") {
    VStack(spacing: 20) {
        NotificationPermissionBanner {
            print("Open Settings tapped")
        }
        .padding()

        Spacer()
    }
}

#Preview("In Settings Context") {
    List {
        Section {
            VStack(spacing: 0) {
                // Notification Permission Banner
                NotificationPermissionBanner {
                    print("Open Settings tapped")
                }
                .padding(.bottom, DesignSystem.Spacing.md)

                // Notification Toggle
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Push Notifications")
                            .font(.body)

                        Text("Get reminders when it's time for your next AIQ test")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    Toggle("", isOn: .constant(false))
                        .disabled(true)
                        .labelsHidden()
                }
                .padding(.vertical, 8)
            }
        } header: {
            Text("Notifications")
        } footer: {
            Text("Receive reminders when it's time to take your next AIQ test (every 3 months)")
                .font(.caption)
        }
    }
}
