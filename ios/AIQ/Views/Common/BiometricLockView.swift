import SwiftUI

/// Full-screen lock overlay shown when biometric authentication is required
///
/// This view is presented over the full app content whenever the app enters the foreground
/// and the user has enabled biometric lock in Settings. It blocks all underlying UI
/// until the user successfully authenticates or signs out.
///
/// ## Authentication Flow
///
/// 1. The view automatically triggers authentication via `.task` on appear
/// 2. If the system prompt is dismissed (user cancelled), the error pill is shown
///    and the "Unlock" button allows the user to try again manually
/// 3. If authentication succeeds, `onAuthenticated` is called and the caller dismisses
///    this view (with an animation)
/// 4. The "Sign Out" button calls `onSignOut` for users who cannot authenticate
///
/// ## Usage
///
/// ```swift
/// BiometricLockView(
///     biometricType: manager.biometricType,
///     biometricAuthManager: manager,
///     onAuthenticated: { isBiometricLocked = false },
///     onSignOut: { /* sign out and clear lock */ }
/// )
/// ```
struct BiometricLockView: View {
    // MARK: - Dependencies

    let biometricType: BiometricType
    let biometricAuthManager: BiometricAuthManagerProtocol

    // MARK: - Callbacks

    /// Called when authentication succeeds. The caller is responsible for dismissing this view.
    let onAuthenticated: () -> Void

    /// Called when the user chooses to sign out rather than authenticate.
    let onSignOut: () -> Void

    // MARK: - Private State

    @State private var isAuthenticating = false
    @State private var authError: BiometricAuthError?

    // MARK: - Body

    var body: some View {
        ZStack {
            // Gradient background matching SplashView / WelcomeView branding
            ColorPalette.scoreGradient
                .ignoresSafeArea()

            VStack(spacing: DesignSystem.Spacing.xxl) {
                Spacer()

                brandingSection

                Spacer()

                lockSection

                if let error = authError {
                    errorPill(message: error.errorDescription ?? "Authentication failed.")
                }

                Spacer()

                actionButtons
            }
            .padding(.horizontal, DesignSystem.Spacing.xl)
            .padding(.bottom, DesignSystem.Spacing.huge)
        }
        .task {
            await triggerAuthentication()
        }
    }

    // MARK: - Subviews

    /// Brain icon + "AIQ" title — mirrors SplashView branding
    private var brandingSection: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 80))
                .foregroundStyle(.white)

            Text("AIQ")
                .font(Typography.displayMedium)
                .foregroundColor(.white)
        }
    }

    /// Lock icon + subtitle
    private var lockSection: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            Image(systemName: "lock.fill")
                .font(.system(size: 48))
                .foregroundStyle(.white)
                .accessibilityIdentifier(AccessibilityIdentifiers.BiometricLockView.lockIcon)

            Text("Verify your identity to continue")
                .font(Typography.bodyLarge)
                .foregroundColor(.white.opacity(0.9))
                .multilineTextAlignment(.center)
        }
    }

    /// Semi-transparent error pill displayed when authentication fails
    private func errorPill(message: String) -> some View {
        Text(message)
            .font(Typography.bodyMedium)
            .foregroundColor(ColorPalette.textPrimary)
            .multilineTextAlignment(.center)
            .padding(.horizontal, DesignSystem.Spacing.lg)
            .padding(.vertical, DesignSystem.Spacing.md)
            .background(.white.opacity(0.85))
            .cornerRadius(DesignSystem.CornerRadius.full)
            .padding(.horizontal, DesignSystem.Spacing.xl)
            .accessibilityIdentifier(AccessibilityIdentifiers.BiometricLockView.errorMessage)
    }

    /// Primary unlock button and secondary sign-out button
    private var actionButtons: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            // Primary: Unlock button (white background, primary text color)
            Button {
                Task {
                    await triggerAuthentication()
                }
            } label: {
                HStack(spacing: DesignSystem.Spacing.sm) {
                    if isAuthenticating {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: ColorPalette.textPrimary))
                            .scaleEffect(0.85)
                            .accessibilityHidden(true)
                    } else {
                        Image(systemName: unlockIconName)
                    }
                    Text(unlockButtonTitle)
                        .font(Typography.button)
                }
                .frame(maxWidth: .infinity)
                .padding(DesignSystem.Spacing.lg)
                .background(.white)
                .foregroundColor(ColorPalette.textPrimary)
                .cornerRadius(DesignSystem.CornerRadius.md)
            }
            .disabled(isAuthenticating)
            .accessibilityLabel(unlockButtonTitle)
            .accessibilityHint(isAuthenticating ? "Loading, please wait" : "Double tap to authenticate")
            .accessibilityIdentifier(AccessibilityIdentifiers.BiometricLockView.unlockButton)

            // Secondary: Sign Out (white underlined text)
            Button {
                onSignOut()
            } label: {
                Text("Sign Out")
                    .font(Typography.bodyMedium)
                    .foregroundColor(.white)
                    .underline()
            }
            .accessibilityLabel("Sign Out")
            .accessibilityHint("Double tap to sign out of your account")
            .accessibilityIdentifier(AccessibilityIdentifiers.BiometricLockView.signOutButton)
        }
    }

    // MARK: - Helpers

    /// SF Symbol name for the current biometric type
    private var unlockIconName: String {
        switch biometricType {
        case .faceID:
            "faceid"
        case .touchID:
            "touchid"
        case .none:
            "lock.open.fill"
        }
    }

    /// Unlock button title reflecting the current biometric type
    private var unlockButtonTitle: String {
        switch biometricType {
        case .faceID:
            "Unlock with Face ID"
        case .touchID:
            "Unlock with Touch ID"
        case .none:
            "Unlock"
        }
    }

    // MARK: - Authentication

    /// Triggers biometric authentication with passcode fallback.
    ///
    /// Clears any previous error, marks the button as in-flight, then awaits the
    /// manager call. On success, fires `onAuthenticated`. On failure, stores the
    /// `BiometricAuthError` so the error pill is shown. The button is re-enabled
    /// in either outcome.
    private func triggerAuthentication() async {
        guard !isAuthenticating else { return }

        isAuthenticating = true
        authError = nil

        do {
            try await biometricAuthManager.authenticateWithPasscodeFallback(
                reason: "Verify your identity to access AIQ"
            )
            isAuthenticating = false
            onAuthenticated()
        } catch let error as BiometricAuthError {
            isAuthenticating = false
            // Do not show an error for user-cancelled or system-cancelled events —
            // these are intentional dismissals and showing an error would be noisy.
            switch error {
            case .userCancelled, .systemCancelled:
                break
            default:
                authError = error
            }
        } catch {
            isAuthenticating = false
            authError = .unknown(error.localizedDescription)
        }
    }
}

// MARK: - Preview

#Preview("Face ID") {
    BiometricLockView(
        biometricType: .faceID,
        biometricAuthManager: PreviewBiometricAuthManager(),
        onAuthenticated: {},
        onSignOut: {}
    )
}

#Preview("Touch ID") {
    BiometricLockView(
        biometricType: .touchID,
        biometricAuthManager: PreviewBiometricAuthManager(),
        onAuthenticated: {},
        onSignOut: {}
    )
}

#Preview("Auth Error") {
    BiometricLockView(
        biometricType: .faceID,
        biometricAuthManager: PreviewBiometricAuthManager(shouldFail: true),
        onAuthenticated: {},
        onSignOut: {}
    )
}

// MARK: - Preview Helpers

/// Lightweight preview-only implementation of `BiometricAuthManagerProtocol`
///
/// This is intentionally scoped to the preview block and is not used in production code.
/// For unit tests, use `MockBiometricAuthManager` from `AIQTests/Mocks/`.
@MainActor
private final class PreviewBiometricAuthManager: BiometricAuthManagerProtocol {
    @Published private(set) var isBiometricAvailable: Bool = true
    @Published private(set) var biometricType: BiometricType = .faceID

    var isBiometricAvailablePublisher: Published<Bool>.Publisher {
        $isBiometricAvailable
    }

    var biometricTypePublisher: Published<BiometricType>.Publisher {
        $biometricType
    }

    private let shouldFail: Bool

    init(shouldFail: Bool = false) {
        self.shouldFail = shouldFail
    }

    func authenticate(reason _: String) async throws {
        if shouldFail { throw BiometricAuthError.authenticationFailed }
    }

    func authenticateWithPasscodeFallback(reason _: String) async throws {
        if shouldFail { throw BiometricAuthError.authenticationFailed }
    }

    func refreshBiometricStatus() {}
}
