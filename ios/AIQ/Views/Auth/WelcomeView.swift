import SwiftUI

/// Welcome/Login screen with delightful animations and gamification
struct WelcomeView: View {
    @StateObject private var viewModel = LoginViewModel(authManager: AuthManager.shared)
    @State private var isAnimating = false
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
                                .font(Typography.displayMedium)
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

//                        // Stats Teaser
//                        StatsTeaser()
//                            .opacity(isAnimating ? 1.0 : 0.0)
//                            .offset(y: isAnimating ? 0 : 20)
//                            .animation(
//                                DesignSystem.Animation.smooth.delay(0.2),
//                                value: isAnimating
//                            )

                        // Feature Highlights
                        FeatureHighlights()
                            .opacity(isAnimating ? 1.0 : 0.0)
                            .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
                            .animation(
                                reduceMotion ? nil : DesignSystem.Animation.smooth.delay(0.4),
                                value: isAnimating
                            )

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
                            reduceMotion ? nil : DesignSystem.Animation.smooth.delay(0.6),
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
                            reduceMotion ? nil : DesignSystem.Animation.smooth.delay(0.8),
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

// MARK: - Stats Teaser Component

/// Displays engaging statistics to attract users
struct StatsTeaser: View {
    var body: some View {
        HStack(spacing: DesignSystem.Spacing.lg) {
            StatItem(icon: "person.3.fill", value: "10K+", label: "Users")
            StatItem(icon: "brain.fill", value: "2M+", label: "Questions")
            StatItem(icon: "chart.line.uptrend.xyaxis", value: "95%", label: "Improved")
        }
        .padding(.horizontal, DesignSystem.Spacing.xl)
    }
}

/// Individual stat item with icon, value, and label
struct StatItem: View {
    let icon: String
    let value: String
    let label: String

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.xs) {
            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.md))
                .foregroundColor(ColorPalette.primary)

            Text(value)
                .font(Typography.h4)
                .foregroundColor(ColorPalette.textPrimary)

            Text(label)
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Feature Highlights Component

/// Displays key features with icons and descriptions
struct FeatureHighlights: View {
    var body: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            InfoCard(
                icon: "puzzlepiece.extension.fill",
                title: "Fresh AI Challenges",
                description: "New questions every test",
                color: ColorPalette.statBlue
            )

            InfoCard(
                icon: "chart.line.uptrend.xyaxis",
                title: "Track Your Progress",
                description: "Watch your IQ improve over time",
                color: ColorPalette.statGreen
            )

//            InfoCard(
//                icon: "trophy.fill",
//                title: "Unlock Achievements",
//                description: "Earn rewards for consistency",
//                color: ColorPalette.statOrange
//            )
        }
        .padding(.horizontal, DesignSystem.Spacing.xl)
    }
}

#Preview {
    WelcomeView()
}
