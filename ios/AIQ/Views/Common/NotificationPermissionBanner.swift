import SwiftUI

/// An informational banner that guides users to enable notification permissions in iOS Settings
/// Appears when notification permission is denied at the system level
struct NotificationPermissionBanner: View {
    let onOpenSettings: () -> Void

    var body: some View {
        Button {
            onOpenSettings()
        } label: {
            HStack(spacing: DesignSystem.Spacing.md) {
                // Info icon
                Image(systemName: "info.circle.fill")
                    .foregroundColor(ColorPalette.info)
                    .font(.system(size: 20))
                    .accessibilityHidden(true)

                // Message
                Text("notification.permission.denied.message".localized)
                    .font(Typography.bodySmall)
                    .foregroundColor(ColorPalette.textPrimary)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)

                // Action indicator
                VStack(spacing: DesignSystem.Spacing.xs) {
                    Text("notification.permission.open.settings".localized)
                        .font(Typography.labelSmall)
                        .foregroundColor(ColorPalette.primary)

                    Image(systemName: "chevron.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(ColorPalette.primary)
                }
                .accessibilityHidden(true)
            }
            .padding(DesignSystem.Spacing.lg)
            .background(ColorPalette.info.opacity(0.1))
            .cornerRadius(DesignSystem.CornerRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                    .stroke(ColorPalette.info.opacity(0.2), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("notification.permission.banner.accessibility.label".localized)
        .accessibilityHint("notification.permission.banner.accessibility.hint".localized)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("notificationPermissionBanner")
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

                        Text("Get reminders when it's time for your next IQ test")
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
            Text("Receive reminders when it's time to take your next IQ test (every 3 months)")
                .font(.caption)
        }
    }
}
