import SwiftUI

/// Root view that determines whether to show consent, auth flow, onboarding, or main app
///
/// ## App Store Privacy Compliance - Navigation Flow
///
/// This view enforces a consent-first navigation hierarchy:
///
/// ```
/// App Launch
///     │
///     ▼
/// ┌─────────────────────────┐
/// │ Privacy Consent Check   │◄── First checkpoint: hasAcceptedConsent
/// └─────────────────────────┘
///     │
///     ▼ (consent accepted)
/// ┌─────────────────────────┐
/// │ Authentication Check    │◄── User must login/register (triggers first analytics)
/// └─────────────────────────┘
///     │
///     ▼ (authenticated)
/// ┌─────────────────────────┐
/// │ Onboarding Check        │◄── No analytics during onboarding
/// └─────────────────────────┘
///     │
///     ▼ (completed)
/// ┌─────────────────────────┐
/// │ Main App                │
/// └─────────────────────────┘
/// ```
///
/// **Key Privacy Guarantee:**
/// No analytics events can fire until the user has:
/// 1. Accepted the privacy policy in `PrivacyConsentView`
/// 2. Completed authentication (first `userRegistered` or `userLogin` event)
///
/// - SeeAlso: `PrivacyConsentView` - First screen for new users
/// - SeeAlso: `OnboardingContainerView` - Zero analytics tracking
/// - SeeAlso: `AnalyticsService` - Privacy-compliant event tracking
struct RootView: View {
    /// Auth state observer that works with any AuthManagerProtocol from the DI container
    @StateObject private var authState: AuthStateObserver
    @ObservedObject private var networkMonitor = NetworkMonitor.shared
    @ObservedObject private var toastManager = ToastManager.shared
    @State private var showSplash = true
    @State private var hasAcceptedConsent: Bool
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding: Bool = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    private let privacyConsentStorage: PrivacyConsentStorageProtocol

    init(
        privacyConsentStorage: PrivacyConsentStorageProtocol = PrivacyConsentStorage.shared,
        serviceContainer: ServiceContainer = .shared
    ) {
        self.privacyConsentStorage = privacyConsentStorage
        // Initialize consent state from storage
        _hasAcceptedConsent = State(initialValue: privacyConsentStorage.hasAcceptedConsent())
        // Initialize auth state observer from the container
        _authState = StateObject(wrappedValue: AuthStateObserver(container: serviceContainer))
    }

    var body: some View {
        ZStack {
            Group {
                if !hasAcceptedConsent {
                    // Show privacy consent on first launch
                    PrivacyConsentView(hasAcceptedConsent: $hasAcceptedConsent)
                } else if authState.isAuthenticated {
                    // Show onboarding for authenticated users who haven't completed it
                    if !hasCompletedOnboarding {
                        OnboardingContainerView()
                    } else {
                        MainTabView()
                    }
                } else {
                    WelcomeView()
                }
            }
            .task {
                // Restore session on app launch
                await authState.restoreSession()

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

            // Toast overlay
            VStack {
                Spacer()
                if let toast = toastManager.currentToast {
                    ToastView(
                        message: toast.message,
                        type: toast.type,
                        onDismiss: {
                            toastManager.dismiss()
                        }
                    )
                    .transition(reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(reduceMotion ? nil : DesignSystem.Animation.standard, value: toastManager.currentToast)
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
