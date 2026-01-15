import SwiftUI

/// View for managing notification preferences
struct NotificationSettingsView: View {
    @StateObject private var viewModel: NotificationSettingsViewModel

    /// Creates a NotificationSettingsView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeNotificationSettingsViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Error Display - Positioned at top for visibility
            if let error = viewModel.error {
                ErrorBanner(
                    message: error.localizedDescription,
                    onDismiss: {
                        viewModel.clearError()
                    }
                )
                .padding(.bottom, DesignSystem.Spacing.md)
            }

            // Permission Recovery Banner - Shows when permission is denied at OS level
            if viewModel.showPermissionRecoveryBanner {
                NotificationPermissionBanner {
                    viewModel.openSystemSettings()
                }
                .padding(.bottom, DesignSystem.Spacing.md)
            }

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

                Toggle("", isOn: Binding(
                    get: { viewModel.notificationEnabled },
                    set: { _ in
                        Task {
                            await viewModel.toggleNotifications()
                        }
                    }
                ))
                .disabled(!viewModel.canToggle)
                .labelsHidden()
            }
            .padding(.vertical, 8)

            // Permission Warning (legacy - kept for backward compatibility)
            if viewModel.showPermissionWarning && !viewModel.showPermissionRecoveryBanner {
                Button {
                    viewModel.openSystemSettings()
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.orange)
                            .font(.caption)

                        Text(viewModel.statusMessage ?? "")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.leading)

                        Spacer()

                        Image(systemName: "chevron.right")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 8)
                    .padding(.horizontal, 12)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
                .padding(.top, 8)
            }
        }
        .task {
            // Load preferences when view appears
            await viewModel.loadNotificationPreferences()
        }
        .alert(
            "notification.settings.redirect.alert.title".localized,
            isPresented: $viewModel.showSettingsRedirectAlert
        ) {
            Button("action.cancel".localized, role: .cancel) {
                viewModel.dismissSettingsRedirectAlert()
            }
            Button("notification.settings.redirect.alert.go.to.settings".localized) {
                viewModel.confirmOpenSystemSettings()
            }
        } message: {
            Text("notification.settings.redirect.alert.message".localized)
        }
    }
}

#Preview {
    List {
        Section {
            NotificationSettingsView()
        } header: {
            Text("Notifications")
        }
    }
}
