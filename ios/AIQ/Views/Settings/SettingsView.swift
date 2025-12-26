import SwiftUI

/// Settings view for user preferences and account management
struct SettingsView: View {
    @Environment(\.appRouter) private var router
    @StateObject private var authManager = AuthManager.shared
    @State private var showLogoutConfirmation = false
    @State private var isLoggingOut = false
    @State private var showDeleteAccountConfirmation = false
    @State private var isDeletingAccount = false
    @State private var deleteAccountError: Error?
    @State private var showCrashConfirmation = false

    var body: some View {
        ZStack {
            List {
                // User Info Section
                Section {
                    if let user = authManager.currentUser {
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
                    .accessibilityIdentifier(AccessibilityIdentifiers.SettingsView.helpButton)
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
                            showLogoutConfirmation = true
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
                            showDeleteAccountConfirmation = true
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
                isPresented: $showLogoutConfirmation,
                titleVisibility: .visible
            ) {
                Button("Logout", role: .destructive) {
                    Task {
                        isLoggingOut = true
                        await authManager.logout()
                        isLoggingOut = false
                    }
                }
                Button("Cancel", role: .cancel) {}
            }
            .confirmationDialog(
                "Delete Account",
                isPresented: $showDeleteAccountConfirmation,
                titleVisibility: .visible
            ) {
                Button("Delete Account", role: .destructive) {
                    Task {
                        isDeletingAccount = true
                        deleteAccountError = nil
                        do {
                            try await authManager.deleteAccount()
                            isDeletingAccount = false
                            // Navigation to welcome screen is handled automatically by auth state change
                        } catch {
                            deleteAccountError = error
                            isDeletingAccount = false
                        }
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This action is irreversible. All your data will be permanently deleted and cannot be recovered.")
            }
            .alert("Delete Account Failed", isPresented: .constant(deleteAccountError != nil)) {
                Button("OK") {
                    deleteAccountError = nil
                }
            } message: {
                if let error = deleteAccountError {
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

            // Loading overlay
            if isLoggingOut {
                LoadingOverlay(message: "Logging out...")
            } else if isDeletingAccount {
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
