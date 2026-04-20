import AIQSharedKit
import AuthenticationServices
import GoogleSignIn
import GoogleSignInSwift
import SwiftUI

/// Welcome/Login screen with delightful animations and gamification
struct WelcomeView: View {
    @StateObject private var viewModel: LoginViewModel
    @State private var isAnimating = false
    /// Tracks an in-flight Google sign-in attempt between the button tap and `viewModel.isLoading`
    /// flipping to true inside `AuthManager.loginWithGoogle`. Closes the race window where a quick
    /// second tap would otherwise pass the `isLoading` guard and spawn a parallel sign-in sheet.
    @State private var isGoogleSignInInFlight = false

    /// Callback to start a guest test (bypasses authentication)
    var onStartGuestTest: (() -> Void)?

    /// When true, the guest test limit has been reached for this device
    var isGuestLimitReached: Bool = false

    /// Creates a WelcomeView with the specified service container
    /// - Parameters:
    ///   - onStartGuestTest: Callback invoked when the user taps "Try a Free Test"
    ///   - isGuestLimitReached: Whether the device has exhausted guest tests
    ///   - serviceContainer: Container for resolving dependencies
    init(
        onStartGuestTest: (() -> Void)? = nil,
        isGuestLimitReached: Bool = false,
        serviceContainer: ServiceContainer = .shared
    ) {
        self.onStartGuestTest = onStartGuestTest
        self.isGuestLimitReached = isGuestLimitReached
        let vm = ViewModelFactory.makeLoginViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        NavigationStack {
            ZStack {
                // Gradient Background
                theme.gradients.scoreGradient
                    .opacity(0.15)
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: DesignSystem.Spacing.xxxl) {
                        // Error Display - Positioned at top for visibility
                        if let error = viewModel.error {
                            ErrorBanner(
                                message: error.localizedDescription,
                                onDismiss: {
                                    viewModel.clearError()
                                }
                            )
                            .padding(.top, DesignSystem.Spacing.md)
                            .accessibilityIdentifier(AccessibilityIdentifiers.WelcomeView.errorBanner)
                        }

                        // Animated Hero Section
                        VStack(spacing: DesignSystem.Spacing.lg) {
                            // Animated Brain Icon
                            Image(systemName: "brain.head.profile")
                                .font(.system(size: 80))
                                .foregroundStyle(theme.gradients.scoreGradient)
                                .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                                .animation(
                                    reduceMotion
                                        ? nil
                                        : Animation.easeInOut(duration: 2.0).repeatForever(autoreverses: true),
                                    value: isAnimating
                                )
                                .accessibilityLabel("AIQ brain icon")
                                .accessibilityIdentifier(AccessibilityIdentifiers.WelcomeView.brainIcon)

                            Text("AIQ")
                                .displayMediumFont()
                                .foregroundStyle(theme.gradients.scoreGradient)
                                .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.0 : 0.95))

                            Text("AI-Generated Cognitive Assessment")
                                .font(theme.typography.bodyLarge)
                                .foregroundColor(theme.colors.textSecondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding(.top, DesignSystem.Spacing.xl)
                        .onAppear {
                            if reduceMotion {
                                isAnimating = true
                            } else {
                                withAnimation(theme.animations.bouncy) {
                                    isAnimating = true
                                }
                            }
                        }

                        // Login Form
                        VStack(spacing: DesignSystem.Spacing.xl) {
                            CustomTextField(
                                title: "Email",
                                placeholder: "your.email@example.com",
                                text: $viewModel.email,
                                keyboardType: .emailAddress,
                                autocapitalization: .never,
                                accessibilityId: AccessibilityIdentifiers.WelcomeView.emailTextField
                            )

                            if let emailError = viewModel.emailError {
                                Text(emailError)
                                    .font(theme.typography.captionMedium)
                                    .foregroundColor(theme.colors.errorText)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }

                            CustomTextField(
                                title: "Password",
                                placeholder: "Enter your password",
                                text: $viewModel.password,
                                isSecure: true,
                                accessibilityId: AccessibilityIdentifiers.WelcomeView.passwordTextField
                            )

                            if let passwordError = viewModel.passwordError {
                                Text(passwordError)
                                    .font(theme.typography.captionMedium)
                                    .foregroundColor(theme.colors.errorText)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }

                            PrimaryButton(
                                title: "Sign In",
                                action: {
                                    Task {
                                        await viewModel.login()
                                    }
                                },
                                isLoading: viewModel.isLoading,
                                isDisabled: !viewModel.isFormValid,
                                accessibilityId: AccessibilityIdentifiers.WelcomeView.signInButton
                            )
                            .padding(.top, DesignSystem.Spacing.sm)
                            .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.0 : 0.95))

                            SignInWithAppleButton(
                                onRequest: { request in
                                    request.requestedScopes = [.email]
                                },
                                onCompletion: { result in
                                    Task { await handleAppleSignIn(result: result) }
                                }
                            )
                            .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
                            .frame(height: 50)
                            .cornerRadius(DesignSystem.CornerRadius.md)
                            .disabled(viewModel.isLoading)
                            .accessibilityIdentifier(
                                AccessibilityIdentifiers.WelcomeView.signInWithAppleButton
                            )

                            GoogleSignInButton(
                                scheme: colorScheme == .dark ? .dark : .light,
                                style: .wide,
                                action: {
                                    Task { await handleGoogleSignIn() }
                                }
                            )
                            .frame(height: 50)
                            .disabled(viewModel.isLoading)
                            .accessibilityIdentifier(
                                AccessibilityIdentifiers.WelcomeView.signInWithGoogleButton
                            )
                        }
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                        .animation(
                            reduceMotion ? nil : theme.animations.smooth.delay(DesignSystem.AnimationDelay.long),
                            value: isAnimating
                        )

                        // Guest Test CTA
                        if let onStartGuestTest {
                            VStack(spacing: DesignSystem.Spacing.md) {
                                if isGuestLimitReached {
                                    // Limit reached — sign-up messaging
                                    VStack(spacing: DesignSystem.Spacing.sm) {
                                        Text("Create an account to keep testing")
                                            .font(theme.typography.bodyMedium)
                                            .foregroundColor(theme.colors.textSecondary)
                                            .multilineTextAlignment(.center)
                                    }
                                } else {
                                    Text("or")
                                        .font(theme.typography.bodyMedium)
                                        .foregroundColor(theme.colors.textTertiary)

                                    Button(action: onStartGuestTest) {
                                        HStack(spacing: DesignSystem.Spacing.sm) {
                                            Image(systemName: "play.circle.fill")
                                            Text("Try a Free Test")
                                        }
                                        .font(theme.typography.button)
                                        .foregroundColor(theme.colors.primary)
                                        .frame(minHeight: 44)
                                    }
                                    .accessibilityIdentifier(
                                        AccessibilityIdentifiers.WelcomeView.guestTestButton
                                    )
                                }
                            }
                            .opacity(isAnimating ? 1.0 : 0.0)
                            .animation(
                                reduceMotion
                                    ? nil
                                    : theme.animations.smooth
                                    .delay(DesignSystem.AnimationDelay.long),
                                value: isAnimating
                            )
                        }

                        // Registration Link
                        VStack(spacing: DesignSystem.Spacing.md) {
                            Text("Don't have an account?")
                                .font(theme.typography.bodyMedium)
                                .foregroundColor(theme.colors.textSecondary)

                            Button(
                                action: {
                                    viewModel.showRegistrationScreen()
                                },
                                label: {
                                    Text("Create Account")
                                        .font(theme.typography.button)
                                        .foregroundColor(theme.colors.primary)
                                        .frame(minHeight: 44)
                                }
                            )
                            .accessibilityIdentifier(
                                AccessibilityIdentifiers.WelcomeView.createAccountButton
                            )
                        }
                        .padding(.top, DesignSystem.Spacing.sm)
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .animation(
                            reduceMotion
                                ? nil
                                : theme.animations.smooth.delay(DesignSystem.AnimationDelay.extraLong),
                            value: isAnimating
                        )

                        Spacer()
                    }
                    .padding(.horizontal, DesignSystem.Spacing.xxl)
                }

                // Loading overlay
                if viewModel.isLoading {
                    LoadingOverlay(message: "Signing in...")
                }
            }
            .navigationDestination(isPresented: $viewModel.showRegistration) {
                RegistrationView()
            }
        }
    }

    /// Handles Sign in with Google by presenting the Google sign-in sheet and exchanging the
    /// returned ID token for AIQ tokens via the backend.
    ///
    /// Cancellation is silently absorbed (user-driven). Missing SDK configuration, a credential
    /// without an ID token, or any framework error surfaces through `viewModel.error` as a typed
    /// `APIError` so the top-of-view `ErrorBanner` renders the message and no partial session
    /// state is established.
    @MainActor
    private func handleGoogleSignIn() async {
        // Re-entry guard: the button is `.disabled(viewModel.isLoading)`, but `isLoading` only
        // flips to true once `AuthManager.loginWithGoogle` begins executing. Between the tap and
        // that flip, a second tap could pass the guard and spawn a parallel sign-in sheet — the
        // view-local flag closes that window.
        guard !viewModel.isLoading, !isGoogleSignInInFlight else { return }
        isGoogleSignInInFlight = true
        defer { isGoogleSignInInFlight = false }

        guard GIDSignIn.sharedInstance.configuration != nil else {
            viewModel.error = APIError.api(
                .unknown(message: "Google sign-in is not configured. Please try another sign-in method.")
            )
            return
        }

        guard let rootViewController = Self.rootPresentingViewController() else {
            viewModel.error = APIError.api(
                .unknown(message: "Could not present Google sign-in. Please try again.")
            )
            return
        }

        do {
            let result = try await GIDSignIn.sharedInstance.signIn(withPresenting: rootViewController)
            guard let identityToken = result.user.idToken?.tokenString else {
                viewModel.error = APIError.api(
                    .unknown(message: "Google sign-in did not return an identity token.")
                )
                return
            }
            await viewModel.loginWithGoogle(identityToken: identityToken)
        } catch {
            // Cast to the GIDSignInError type rather than matching on a raw NSError code so we
            // don't silently swallow unrelated errors that happen to share the canceled code (-5).
            if let signInError = error as? GIDSignInError, signInError.code == .canceled {
                return
            }
            viewModel.error = APIError.api(.unknown(message: error.localizedDescription))
        }
    }

    /// Returns the key window's root view controller for presenting the Google sign-in sheet.
    ///
    /// SwiftUI does not expose a presenting view controller directly, so we walk the active scene
    /// hierarchy. Returns nil only if no foreground active scene has a key window yet — a state
    /// that only occurs very early in app launch, before WelcomeView is visible.
    private static func rootPresentingViewController() -> UIViewController? {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)?
            .rootViewController
    }

    /// Handles the ASAuthorizationController result from Sign in with Apple.
    ///
    /// Cancellation is silently absorbed (user-driven, no error UX). All other failures —
    /// framework errors or a credential missing the identity token — surface through
    /// `viewModel.error` as a typed `APIError` so the top-of-view `ErrorBanner` renders the
    /// message and no partial session state is established.
    @MainActor
    private func handleAppleSignIn(result: Result<ASAuthorization, Error>) async {
        // Re-entry guard: SignInWithAppleButton is a UIKit-backed view whose taps may reach the
        // underlying control even while the SwiftUI container is `.disabled`, so drop any tap
        // that arrives during an in-flight login to avoid racing two sign-in attempts.
        guard !viewModel.isLoading else { return }

        switch result {
        case let .success(authorization):
            guard
                let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                let tokenData = credential.identityToken,
                let identityToken = String(data: tokenData, encoding: .utf8)
            else {
                viewModel.error = APIError.api(
                    .unknown(message: "Apple sign-in did not return an identity token.")
                )
                return
            }
            await viewModel.loginWithApple(identityToken: identityToken)
        case let .failure(error):
            if let authError = error as? ASAuthorizationError, authError.code == .canceled {
                return
            }
            viewModel.error = APIError.api(.unknown(message: error.localizedDescription))
        }
    }
}

#Preview {
    WelcomeView()
}
