import SwiftUI

/// Settings view for user preferences and account management
struct SettingsView: View {
    @StateObject private var authManager = AuthManager.shared
    @State private var showLogoutConfirmation = false

    var body: some View {
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

            // App Settings Section
            Section {
                HStack {
                    Text("Notifications")
                    Spacer()
                    Text("Coming soon")
                        .foregroundColor(.secondary)
                        .font(.caption)
                }

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
                    await authManager.logout()
                }
            }
            Button("Cancel", role: .cancel) {}
        }
    }
}

#Preview {
    NavigationStack {
        SettingsView()
    }
}
