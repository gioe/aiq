import SwiftUI

/// Settings view for user preferences and account management
struct SettingsView: View {
    @StateObject private var authManager = AuthManager.shared
    @State private var showLogoutConfirmation = false
    @State private var isLoggingOut = false

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
                    }
                } header: {
                    Text("Account")
                }

                // Notifications Section
                Section {
                    NotificationSettingsView()
                } header: {
                    Text("Notifications")
                } footer: {
                    Text("Receive reminders when it's time to take your next IQ test (every 3 months)")
                        .font(.caption)
                }

                // App Settings Section
                Section {
                    HStack {
                        Text("App Version")
                        Spacer()
                        Text(AppConfig.appVersion)
                            .foregroundColor(.secondary)
                    }
                } header: {
                    Text("App")
                }

                // Logout Section
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
                }
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

            // Loading overlay
            if isLoggingOut {
                LoadingOverlay(message: "Logging out...")
            }
        }
    }
}

#Preview {
    NavigationStack {
        SettingsView()
    }
}
