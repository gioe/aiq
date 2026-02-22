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
/// │ Biometric Lock Check    │◄── Re-locks on every foreground transition (if enabled)
/// └─────────────────────────┘
///     │
///     ▼ (authenticated or disabled)
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
/// **Biometric Lock Behaviour:**
/// - The lock is applied only when the user is authenticated AND has enabled biometric
///   lock in Settings (`BiometricPreferenceStorage.isBiometricEnabled == true`).
/// - It is triggered once on initial launch (after the splash screen fades out) and
///   again on every `.active` scene-phase transition.
/// - The `BiometricLockView` overlay sits at `zIndex(1000)` — above the splash screen
///   (zIndex 999) — so it is never obscured.
///
/// - SeeAlso: `PrivacyConsentView` - First screen for new users
/// - SeeAlso: `OnboardingContainerView` - Zero analytics tracking
/// - SeeAlso: `AnalyticsService` - Privacy-compliant event tracking
/// - SeeAlso: `BiometricLockView` - Full-screen biometric authentication overlay
struct RootView: View {
    /// Auth state observer that works with any AuthManagerProtocol from the DI container
    @StateObject private var authState: AuthStateObserver
    /// Network monitor resolved from DI container, wrapped in StateObject to observe connectivity changes
    @StateObject private var networkMonitor: NetworkMonitorObserver
    /// Toast manager resolved from DI container, wrapped in StateObject to observe toast changes
    @StateObject private var toastObserver: ToastManagerObserver
    @State private var showSplash = true
    @State private var isBiometricLocked = false
    @State private var hasAcceptedConsent: Bool
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding: Bool = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.scenePhase) private var scenePhase

    private let privacyConsentStorage: PrivacyConsentStorageProtocol
    /// Resolved from the DI container during `init`. Optional because the app may run in
    /// environments (e.g. UI test configurations) where the service is not registered.
    private let biometricAuthManager: BiometricAuthManagerProtocol?
    /// Resolved from the DI container during `init`. Optional for the same reason as above.
    private let biometricPreferenceStorage: BiometricPreferenceStorageProtocol?

    init(
        privacyConsentStorage: PrivacyConsentStorageProtocol = PrivacyConsentStorage.shared,
        serviceContainer: ServiceContainer = .shared
    ) {
        self.privacyConsentStorage = privacyConsentStorage
        // Initialize consent state from storage
        _hasAcceptedConsent = State(initialValue: privacyConsentStorage.hasAcceptedConsent())
        // Initialize auth state observer from the container
        _authState = StateObject(wrappedValue: AuthStateObserver(container: serviceContainer))
        // Initialize network monitor observer from the container
        _networkMonitor = StateObject(wrappedValue: NetworkMonitorObserver(container: serviceContainer))
        // Initialize toast manager observer from the container
        _toastObserver = StateObject(wrappedValue: ToastManagerObserver(container: serviceContainer))
        // Resolve biometric services — optional so the app degrades gracefully if absent
        biometricAuthManager = serviceContainer.resolve(BiometricAuthManagerProtocol.self)
        biometricPreferenceStorage = serviceContainer.resolve(BiometricPreferenceStorageProtocol.self)
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

                // Apply biometric lock immediately after splash if the user is
                // authenticated and has the feature enabled in Settings.
                if authState.isAuthenticated,
                   let storage = biometricPreferenceStorage,
                   storage.isBiometricEnabled {
                    isBiometricLocked = true
                }
            }
            .onChange(of: scenePhase) { newPhase in
                // Re-lock whenever the app returns to the foreground (e.g. after the user
                // switches away and comes back). We only lock if the splash has already been
                // dismissed so we don't interrupt the initial startup sequence.
                if newPhase == .active,
                   !showSplash,
                   authState.isAuthenticated,
                   let storage = biometricPreferenceStorage,
                   storage.isBiometricEnabled {
                    isBiometricLocked = true
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
                if let toast = toastObserver.currentToast {
                    ToastView(
                        message: toast.message,
                        type: toast.type,
                        onDismiss: {
                            toastObserver.dismiss()
                        }
                    )
                    .transition(reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(reduceMotion ? nil : DesignSystem.Animation.standard, value: toastObserver.currentToast)
            .opacity(showSplash ? 0.0 : 1.0)

            // Splash Screen
            if showSplash {
                SplashView()
                    .transition(.opacity)
                    .zIndex(999)
            }

            // Biometric Lock Overlay
            // Positioned at zIndex(1000) so it sits above the splash screen (999)
            // and all other content. The caller animates it in/out with .opacity.
            if isBiometricLocked, let manager = biometricAuthManager {
                BiometricLockView(
                    biometricType: manager.biometricType,
                    biometricAuthManager: manager,
                    onAuthenticated: {
                        withAnimation(reduceMotion ? nil : DesignSystem.Animation.smooth) {
                            isBiometricLocked = false
                        }
                    },
                    onSignOut: {
                        isBiometricLocked = false
                        Task {
                            await authState.logout()
                        }
                    }
                )
                .transition(.opacity)
                .zIndex(1000)
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
