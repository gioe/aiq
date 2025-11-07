import SwiftUI

/// Root view that determines whether to show auth flow or main app
struct RootView: View {
    @StateObject private var authManager = AuthManager.shared

    var body: some View {
        Group {
            if authManager.isAuthenticated {
                MainTabView()
            } else {
                WelcomeView()
            }
        }
        .task {
            // Restore session on app launch
            await authManager.restoreSession()
        }
    }
}

#Preview("Authenticated") {
    RootView()
}

#Preview("Not Authenticated") {
    RootView()
}
