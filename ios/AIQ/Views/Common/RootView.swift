import SwiftUI

/// Root view that determines whether to show auth flow or main app
struct RootView: View {
    @StateObject private var authManager = AuthManager.shared
    @StateObject private var networkMonitor = NetworkMonitor.shared
    @State private var showSplash = true

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

                // Keep splash screen visible for minimum duration for smooth transition
                try? await Task.sleep(nanoseconds: 800_000_000) // 0.8 seconds

                // Fade out splash screen
                withAnimation(DesignSystem.Animation.smooth) {
                    showSplash = false
                }
            }
            .opacity(showSplash ? 0.0 : 1.0)

            // Network status banner
            VStack {
                NetworkStatusBanner(isConnected: networkMonitor.isConnected)
                Spacer()
            }
            .animation(.easeInOut, value: networkMonitor.isConnected)
            .opacity(showSplash ? 0.0 : 1.0)

            // Splash Screen
            if showSplash {
                SplashView()
                    .transition(.opacity)
                    .zIndex(999)
            }
        }
    }
}

// MARK: - Splash Screen Component

/// Splash screen shown during app initialization
/// Provides a smooth transition from launch screen to main app
struct SplashView: View {
    @State private var isAnimating = false

    var body: some View {
        ZStack {
            // Gradient Background matching WelcomeView
            ColorPalette.scoreGradient
                .ignoresSafeArea()

            VStack(spacing: DesignSystem.Spacing.lg) {
                // Animated Brain Icon
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 100))
                    .foregroundStyle(.white)
                    .scaleEffect(isAnimating ? 1.0 : 0.8)
                    .opacity(isAnimating ? 1.0 : 0.0)

                // App Name
                Text("AIQ")
                    .font(Typography.displayMedium)
                    .foregroundColor(.white)
                    .opacity(isAnimating ? 1.0 : 0.0)
            }
            .onAppear {
                withAnimation(DesignSystem.Animation.smooth) {
                    isAnimating = true
                }
            }
        }
    }
}

#Preview("Authenticated") {
    RootView()
}

#Preview("Not Authenticated") {
    RootView()
}

#Preview("Splash") {
    SplashView()
}
