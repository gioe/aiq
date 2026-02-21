import SwiftUI

/// Settings view for user preferences and account management
struct SettingsView: View {
    @Environment(\.appRouter) private var router
    @StateObject private var viewModel: SettingsViewModel
    @State private var showCrashConfirmation = false

    /// Creates a SettingsView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        _viewModel = StateObject(wrappedValue: ViewModelFactory.makeSettingsViewModel(container: serviceContainer))
    }

    private var biometricIconName: String {
        switch viewModel.biometricType {
        case .faceID: "faceid"
        case .touchID: "touchid"
        case .none: "lock.shield"
        }
    }

    private var biometricToggleLabel: String {
        switch viewModel.biometricType {
        case .faceID: "Sign in with Face ID"
        case .touchID: "Sign in with Touch ID"
        case .none: "Biometric Login"
        }
    }

    private var biometricFooterText: String {
        guard viewModel.isBiometricAvailable else {
            return "Biometric authentication is not available on this device."
        }
        return "Use \(viewModel.biometricType == .faceID ? "Face ID" : "Touch ID") to sign in quickly and securely."
    }

    var body: some View {
        ZStack {
            List {
                // User Info Section
                Section {
                    if let user = viewModel.currentUser {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(user.fullName)
                                .font(.headline)
                            Text(user.email)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        .padding(.vertical, 8)
                        .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.accountSection)
                    }
                } header: {
                    Text("Account")
                }

                // Notifications Section
                Section {
                    NotificationSettingsView()
                        .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.notificationsSection)
                } header: {
                    Text("Notifications")
                } footer: {
                    Text("Receive reminders when it's time to take your next IQ test (every 3 months)")
                        .font(.caption)
                }

                // Security Section
                Section {
                    HStack {
                        Image(systemName: biometricIconName)
                            .foregroundColor(.accentColor)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(biometricToggleLabel)
                            if !viewModel.isBiometricAvailable {
                                Text("Not available on this device")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        Spacer()
                        Toggle("", isOn: Binding(
                            get: { viewModel.isBiometricEnabled },
                            set: { _ in viewModel.toggleBiometric() }
                        ))
                        .disabled(!viewModel.isBiometricAvailable)
                        .labelsHidden()
                        .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.biometricToggle)
                        .accessibilityLabel(biometricToggleLabel)
                        .accessibilityHint(
                            "Double tap to \(viewModel.isBiometricEnabled ? "disable" : "enable") biometric login"
                        )
                    }
                } header: {
                    Text("Security")
                } footer: {
                    Text(biometricFooterText)
                        .font(.caption)
                }
                .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.securitySection)

                // Help Section
                Section {
                    Button {
                        router.push(.help)
                    } label: {
                        HStack {
                            Image(systemName: "questionmark.circle")
                                .foregroundColor(.accentColor)
                            Text("Help & FAQ")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)
                    .accessibilityLabel("Help & FAQ")
                    .accessibilityHint("Opens help documentation")
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.helpButton)

                    Button {
                        router.push(.feedback)
                    } label: {
                        HStack {
                            Image(systemName: "envelope")
                                .foregroundColor(.accentColor)
                            Text("Send Feedback")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)
                    .accessibilityLabel("Send Feedback")
                    .accessibilityHint("Opens feedback form")
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.feedbackButton)

                    Button {
                        viewModel.showOnboardingFlow()
                    } label: {
                        HStack {
                            Image(systemName: "arrow.clockwise.circle")
                                .foregroundColor(.accentColor)
                            Text("View Onboarding Again")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)
                    .accessibilityLabel("View Onboarding Again")
                    .accessibilityHint("Opens onboarding tutorial")
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.viewOnboardingButton)
                } header: {
                    Text("Support")
                }

                // App Settings Section
                Section {
                    HStack {
                        Text("App Version")
                        Spacer()
                        Text(AppConfig.appVersion)
                            .foregroundColor(.secondary)
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.appVersionLabel)
                } header: {
                    Text("App")
                }

                // Account Actions Section
                Section {
                    Button(
                        role: .destructive,
                        action: {
                            viewModel.showLogoutDialog()
                        },
                        label: {
                            HStack {
                                Spacer()
                                Text("Logout")
                                Spacer()
                            }
                        }
                    )
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.logoutButton)

                    Button(
                        role: .destructive,
                        action: {
                            viewModel.showDeleteAccountDialog()
                        },
                        label: {
                            HStack {
                                Spacer()
                                Text("Delete Account")
                                Spacer()
                            }
                        }
                    )
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.deleteAccountButton)
                } footer: {
                    Text("""
                    Deleting your account is permanent and cannot be undone. \
                    All your data will be permanently deleted.
                    """)
                    .font(.caption)
                }

                #if DEBUG
                    // Debug Section - Only visible in DEBUG builds
                    Section {
                        Button(
                            role: .destructive,
                            action: {
                                showCrashConfirmation = true
                            },
                            label: {
                                HStack {
                                    Image(systemName: "exclamationmark.triangle")
                                        .foregroundColor(.orange)
                                    Text("Test Crash")
                                }
                            }
                        )
                        .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.testCrashButton)
                    } header: {
                        Text("Debug")
                    } footer: {
                        Text("Force a crash to test Crashlytics. Reported on next app launch.")
                            .font(.caption)
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.debugSection)
                #endif
            }
            .navigationTitle("Settings")
            .confirmationDialog(
                "Are you sure you want to logout?",
                isPresented: $viewModel.showLogoutConfirmation,
                titleVisibility: .visible
            ) {
                Button("Logout", role: .destructive) {
                    Task {
                        await viewModel.logout()
                    }
                }
                Button("Cancel", role: .cancel) {}
            }
            .confirmationDialog(
                "Delete Account",
                isPresented: $viewModel.showDeleteAccountConfirmation,
                titleVisibility: .visible
            ) {
                Button("Delete Account", role: .destructive) {
                    Task {
                        await viewModel.deleteAccount()
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This action is irreversible. All your data will be permanently deleted and cannot be recovered.")
            }
            .alert("Delete Account Failed", isPresented: Binding(
                get: { viewModel.deleteAccountError != nil },
                set: { if !$0 { viewModel.clearDeleteAccountError() } }
            )) {
                Button("OK") {}
            } message: {
                if let error = viewModel.deleteAccountError {
                    Text(error.localizedDescription)
                }
            }
            #if DEBUG
            .confirmationDialog(
                    "This will crash the app to test Crashlytics",
                    isPresented: $showCrashConfirmation,
                    titleVisibility: .visible
                ) {
                    Button("Crash App", role: .destructive) {
                        // Force a crash for testing Crashlytics
                        fatalError("Test crash for Crashlytics")
                    }
                    Button("Cancel", role: .cancel) {}
                }
            #endif
                .fullScreenCover(isPresented: $viewModel.showOnboarding) {
                    OnboardingContainerView()
                }

            // Loading overlay
            if viewModel.isLoggingOut {
                LoadingOverlay(message: "Logging out...")
            } else if viewModel.isDeletingAccount {
                LoadingOverlay(message: "Deleting account...")
            }
        }
    }
}

#Preview {
    NavigationStack {
        SettingsView()
    }
}
