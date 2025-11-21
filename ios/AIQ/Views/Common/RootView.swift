import SwiftUI

/// Root view that determines whether to show auth flow or main app
struct RootView: View {
    @StateObject private var authManager = AuthManager.shared
    @StateObject private var networkMonitor = NetworkMonitor.shared

    var body: some View {
        ZStack {
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

            // Network status banner
            VStack {
                NetworkStatusBanner(isConnected: networkMonitor.isConnected)
                Spacer()
            }
            .animation(.easeInOut, value: networkMonitor.isConnected)
        }
    }
}

#Preview("Authenticated") {
    RootView()
}

#Preview("Not Authenticated") {
    RootView()
}
