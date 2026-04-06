import SwiftUI

/// A full-screen biometric authentication overlay with retry flow.
///
/// Presents a lock screen that automatically triggers biometric authentication on appear.
/// If authentication fails, an error pill is shown and the user can retry manually.
/// A sign-out option is provided for users who cannot authenticate.
///
/// The branding section is consumer-provided via `@ViewBuilder`, allowing each app
/// to display its own logo and title without modifying this component.
///
/// ## Usage
///
/// ```swift
/// BiometricLockView(
///     biometricType: manager.biometricType,
///     biometricAuthManager: manager,
///     authReason: "Verify your identity to access MyApp",
///     onAuthenticated: { isLocked = false },
///     onSignOut: { /* sign out */ }
/// ) {
///     VStack(spacing: 12) {
///         Image(systemName: "star.fill")
///             .font(.system(size: 80))
///             .foregroundStyle(.white)
///         Text("MyApp")
///             .font(.largeTitle.bold())
///             .foregroundColor(.white)
///     }
/// }
/// ```
public struct BiometricLockView<Branding: View>: View {
    // MARK: - Dependencies

    /// The type of biometric available on the device.
    public let biometricType: BiometricType

    /// The manager used to perform authentication.
    public let biometricAuthManager: any BiometricAuthManagerProtocol

    /// The localized reason string shown in the system biometric prompt.
    public let authReason: String

    // MARK: - Callbacks

    /// Called when authentication succeeds. The caller is responsible for dismissing this view.
    public let onAuthenticated: () -> Void

    /// Called when the user chooses to sign out rather than authenticate.
    public let onSignOut: () -> Void

    // MARK: - Branding

    private let branding: Branding

    // MARK: - Private State

    @State private var isAuthenticating = false
    @State private var authError: BiometricAuthError?

    @Environment(\.appTheme) private var theme

    // MARK: - Init

    /// Creates a biometric lock view.
    /// - Parameters:
    ///   - biometricType: The biometric type available on this device.
    ///   - biometricAuthManager: The manager that performs authentication.
    ///   - authReason: The reason displayed in the system biometric prompt.
    ///   - onAuthenticated: Called when authentication succeeds.
    ///   - onSignOut: Called when the user taps sign out.
    ///   - branding: A view builder providing app-specific branding (logo, title, etc.).
    public init(
        biometricType: BiometricType,
        biometricAuthManager: any BiometricAuthManagerProtocol,
        authReason: String = "Verify your identity to continue",
        onAuthenticated: @escaping () -> Void,
        onSignOut: @escaping () -> Void,
        @ViewBuilder branding: () -> Branding
    ) {
        self.biometricType = biometricType
        self.biometricAuthManager = biometricAuthManager
        self.authReason = authReason
        self.onAuthenticated = onAuthenticated
        self.onSignOut = onSignOut
        self.branding = branding()
    }

    // MARK: - Body

    public var body: some View {
        ZStack {
            theme.gradients.scoreGradient
                .ignoresSafeArea()

            VStack(spacing: theme.spacing.xxl) {
                Spacer()

                branding

                Spacer()

                lockSection

                if let error = authError {
                    errorPill(message: error.errorDescription ?? "Authentication failed.")
                }

                Spacer()

                actionButtons
            }
            .padding(.horizontal, theme.spacing.xl)
            .padding(.bottom, theme.spacing.huge)
        }
        .task {
            await triggerAuthentication()
        }
    }

    // MARK: - Subviews

    /// Lock icon and subtitle.
    private var lockSection: some View {
        VStack(spacing: theme.spacing.md) {
            Image(systemName: "lock.fill")
                .font(.system(size: 48))
                .foregroundStyle(.white)
                .accessibilityIdentifier("biometricLockView.lockIcon")

            Text("Verify your identity to continue")
                .font(theme.typography.bodyLarge)
                .foregroundColor(.white.opacity(0.9))
                .multilineTextAlignment(.center)
        }
    }

    /// Semi-transparent error pill displayed when authentication fails.
    private func errorPill(message: String) -> some View {
        Text(message)
            .font(theme.typography.bodyMedium)
            .foregroundColor(theme.colors.textPrimary)
            .multilineTextAlignment(.center)
            .padding(.horizontal, theme.spacing.lg)
            .padding(.vertical, theme.spacing.md)
            .background(.white.opacity(0.85))
            .cornerRadius(theme.cornerRadius.full)
            .padding(.horizontal, theme.spacing.xl)
            .accessibilityIdentifier("biometricLockView.errorMessage")
    }

    /// Primary unlock button and secondary sign-out button.
    private var actionButtons: some View {
        VStack(spacing: theme.spacing.lg) {
            Button {
                Task {
                    await triggerAuthentication()
                }
            } label: {
                HStack(spacing: theme.spacing.sm) {
                    if isAuthenticating {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: theme.colors.textPrimary))
                            .scaleEffect(0.85)
                            .accessibilityHidden(true)
                    } else {
                        Image(systemName: unlockIconName)
                    }
                    Text(unlockButtonTitle)
                        .font(theme.typography.button)
                }
                .frame(maxWidth: .infinity)
                .padding(theme.spacing.lg)
                .background(.white)
                .foregroundColor(theme.colors.textPrimary)
                .cornerRadius(theme.cornerRadius.md)
            }
            .disabled(isAuthenticating)
            .accessibilityLabel(unlockButtonTitle)
            .accessibilityHint(isAuthenticating ? "Loading, please wait" : "Double tap to authenticate")
            .accessibilityIdentifier("biometricLockView.unlockButton")

            Button {
                onSignOut()
            } label: {
                Text("Sign Out")
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(.white)
                    .underline()
            }
            .accessibilityLabel("Sign Out")
            .accessibilityHint("Double tap to sign out of your account")
            .accessibilityIdentifier("biometricLockView.signOutButton")
        }
    }

    // MARK: - Helpers

    /// SF Symbol name for the current biometric type.
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

    /// Unlock button title reflecting the current biometric type.
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
    private func triggerAuthentication() async {
        guard !isAuthenticating else { return }

        isAuthenticating = true
        authError = nil

        do {
            try await biometricAuthManager.authenticateWithPasscodeFallback(
                reason: authReason
            )
            isAuthenticating = false
            onAuthenticated()
        } catch let error as BiometricAuthError {
            isAuthenticating = false
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
