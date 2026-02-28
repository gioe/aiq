import SwiftUI

/// Welcome/Login screen with delightful animations and gamification
struct WelcomeView: View {
    @StateObject private var viewModel: LoginViewModel
    @State private var isAnimating = false

    /// Creates a WelcomeView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeLoginViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        NavigationStack {
            ZStack {
                // Gradient Background
                ColorPalette.scoreGradient
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
                                .foregroundStyle(ColorPalette.scoreGradient)
                                .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.05 : 1.0))
                                .animation(
                                    reduceMotion
                                        ? nil
                                        : Animation.easeInOut(duration: 2.0).repeatForever(autoreverses: true),
                                    value: isAnimating
                                )
                                .accessibilityIdentifier(AccessibilityIdentifiers.WelcomeView.brainIcon)

                            Text("AIQ")
                                .displayMediumFont()
                                .foregroundStyle(ColorPalette.scoreGradient)
                                .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.0 : 0.95))

                            Text("AI-Generated Cognitive Assessment")
                                .font(Typography.bodyLarge)
                                .foregroundColor(ColorPalette.textSecondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding(.top, DesignSystem.Spacing.xl)
                        .onAppear {
                            if reduceMotion {
                                isAnimating = true
                            } else {
                                withAnimation(DesignSystem.Animation.bouncy) {
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
                                    .font(Typography.captionMedium)
                                    .foregroundColor(ColorPalette.errorText)
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
                                    .font(Typography.captionMedium)
                                    .foregroundColor(ColorPalette.errorText)
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
                        }
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                        .animation(
                            reduceMotion ? nil : DesignSystem.Animation.smooth.delay(DesignSystem.AnimationDelay.long),
                            value: isAnimating
                        )

                        // Registration Link
                        VStack(spacing: DesignSystem.Spacing.md) {
                            Text("Don't have an account?")
                                .font(Typography.bodyMedium)
                                .foregroundColor(ColorPalette.textSecondary)

                            Button(
                                action: {
                                    viewModel.showRegistrationScreen()
                                },
                                label: {
                                    Text("Create Account")
                                        .font(Typography.button)
                                        .foregroundColor(ColorPalette.primary)
                                        .frame(minHeight: 44)
                                }
                            )
                            .accessibilityIdentifier(AccessibilityIdentifiers.WelcomeView.createAccountButton)
                        }
                        .padding(.top, DesignSystem.Spacing.sm)
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .animation(
                            reduceMotion
                                ? nil
                                : DesignSystem.Animation.smooth.delay(DesignSystem.AnimationDelay.extraLong),
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
}

#Preview {
    WelcomeView()
}
