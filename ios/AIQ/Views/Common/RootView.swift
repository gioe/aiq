import SwiftUI

/// Root view that determines whether to show consent, auth flow, or main app
struct RootView: View {
    @StateObject private var authManager = AuthManager.shared
    @StateObject private var networkMonitor = NetworkMonitor.shared
    @State private var showSplash = true
    @State private var hasAcceptedConsent: Bool
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    private let privacyConsentStorage: PrivacyConsentStorageProtocol

    init(privacyConsentStorage: PrivacyConsentStorageProtocol = PrivacyConsentStorage.shared) {
        self.privacyConsentStorage = privacyConsentStorage
        // Initialize consent state from storage
        _hasAcceptedConsent = State(initialValue: privacyConsentStorage.hasAcceptedConsent())
    }

    var body: some View {
        ZStack {
            Group {
                if !hasAcceptedConsent {
                    // Show privacy consent on first launch
                    PrivacyConsentView(hasAcceptedConsent: $hasAcceptedConsent)
                } else if authManager.isAuthenticated {
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
                if reduceMotion {
                    showSplash = false
                } else {
                    withAnimation(DesignSystem.Animation.smooth) {
                        showSplash = false
                    }
                }
            }
            .opacity(showSplash ? 0.0 : 1.0)

            // Network status banner
            VStack {
                NetworkStatusBanner(isConnected: networkMonitor.isConnected)
                Spacer()
            }
            .animation(reduceMotion ? nil : .easeInOut, value: networkMonitor.isConnected)
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
    @Environment(\.accessibilityReduceMotion) var reduceMotion

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
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.0 : 0.8))
                    .opacity(isAnimating ? 1.0 : 0.0)

                // App Name
                Text("AIQ")
                    .font(Typography.displayMedium)
                    .foregroundColor(.white)
                    .opacity(isAnimating ? 1.0 : 0.0)
            }
            .onAppear {
                if reduceMotion {
                    isAnimating = true
                } else {
                    withAnimation(DesignSystem.Animation.smooth) {
                        isAnimating = true
                    }
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
