import SwiftUI

/// Registration screen - User's first entry into the app
struct RegistrationView: View {
    @StateObject private var viewModel = RegistrationViewModel(authManager: AuthManager.shared)
    @Environment(\.dismiss) private var dismiss
    @State private var isAnimating = false

    var body: some View {
        ZStack {
            // Gradient Background
            ColorPalette.scoreGradient
                .opacity(0.12)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: DesignSystem.Spacing.xxxl) {
                    // Error Display - Positioned at top for visibility
                    if let error = viewModel.error {
                        ErrorBanner(
                            message: error.localizedDescription,
                            onDismiss: {
                                viewModel.clearForm()
                            }
                        )
                        .padding(.top, DesignSystem.Spacing.md)
                    }

                    // Animated Hero Section
                    VStack(spacing: DesignSystem.Spacing.lg) {
                        // Animated Icon - Using sparkles to represent new beginning
                        Image(systemName: "sparkles")
                            .font(.system(size: 72))
                            .foregroundStyle(ColorPalette.scoreGradient)
                            .rotationEffect(.degrees(isAnimating ? 5 : -5))
                            .animation(
                                Animation.easeInOut(duration: 1.5).repeatForever(autoreverses: true),
                                value: isAnimating
                            )

                        Text("Begin Your Journey")
                            .font(Typography.displayMedium)
                            .foregroundStyle(ColorPalette.scoreGradient)
                            .multilineTextAlignment(.center)

                        Text("Track your cognitive performance over time")
                            .font(Typography.bodyLarge)
                            .foregroundColor(ColorPalette.textSecondary)
                            .multilineTextAlignment(.center)

                        // Disclaimer
                        Text("For personal insight. Not a clinical IQ test.")
                            .font(Typography.captionMedium)
                            .foregroundColor(ColorPalette.textSecondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, DesignSystem.Spacing.xl)
                    }
                    .padding(.top, DesignSystem.Spacing.xl)
                    .onAppear {
                        withAnimation(DesignSystem.Animation.bouncy) {
                            isAnimating = true
                        }
                    }

                    // Benefits Section
                    RegistrationBenefits()
                        .opacity(isAnimating ? 1.0 : 0.0)
                        .offset(y: isAnimating ? 0 : 20)
                        .animation(
                            DesignSystem.Animation.smooth.delay(0.2),
                            value: isAnimating
                        )

                    // Registration Form
                    VStack(spacing: DesignSystem.Spacing.xl) {
                        // Name fields
                        HStack(spacing: DesignSystem.Spacing.md) {
                            VStack(spacing: DesignSystem.Spacing.xs) {
                                CustomTextField(
                                    title: "First Name",
                                    placeholder: "John",
                                    text: $viewModel.firstName,
                                    autocapitalization: .words,
                                    accessibilityId: AccessibilityIdentifiers.RegistrationView.firstNameTextField
                                )

                                if let firstNameError = viewModel.firstNameError {
                                    Text(firstNameError)
                                        .font(Typography.captionMedium)
                                        .foregroundColor(ColorPalette.errorText)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }

                            VStack(spacing: DesignSystem.Spacing.xs) {
                                CustomTextField(
                                    title: "Last Name",
                                    placeholder: "Doe",
                                    text: $viewModel.lastName,
                                    autocapitalization: .words,
                                    accessibilityId: AccessibilityIdentifiers.RegistrationView.lastNameTextField
                                )

                                if let lastNameError = viewModel.lastNameError {
                                    Text(lastNameError)
                                        .font(Typography.captionMedium)
                                        .foregroundColor(ColorPalette.errorText)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }
                        }

                        // Email field
                        VStack(spacing: DesignSystem.Spacing.xs) {
                            CustomTextField(
                                title: "Email",
                                placeholder: "your.email@example.com",
                                text: $viewModel.email,
                                keyboardType: .emailAddress,
                                autocapitalization: .never,
                                accessibilityId: AccessibilityIdentifiers.RegistrationView.emailTextField
                            )

                            if let emailError = viewModel.emailError {
                                Text(emailError)
                                    .font(Typography.captionMedium)
                                    .foregroundColor(ColorPalette.errorText)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }

                        // Password field
                        VStack(spacing: DesignSystem.Spacing.xs) {
                            CustomTextField(
                                title: "Password",
                                placeholder: "At least 8 characters",
                                text: $viewModel.password,
                                isSecure: true,
                                accessibilityId: AccessibilityIdentifiers.RegistrationView.passwordTextField
                            )

                            if let passwordError = viewModel.passwordError {
                                Text(passwordError)
                                    .font(Typography.captionMedium)
                                    .foregroundColor(ColorPalette.errorText)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }

                        // Confirm password field
                        VStack(spacing: DesignSystem.Spacing.xs) {
                            CustomTextField(
                                title: "Confirm Password",
                                placeholder: "Re-enter your password",
                                text: $viewModel.confirmPassword,
                                isSecure: true,
                                accessibilityId: AccessibilityIdentifiers.RegistrationView.confirmPasswordTextField
                            )

                            if let confirmPasswordError = viewModel.confirmPasswordError {
                                Text(confirmPasswordError)
                                    .font(Typography.captionMedium)
                                    .foregroundColor(ColorPalette.errorText)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                    }
                    .opacity(isAnimating ? 1.0 : 0.0)
                    .offset(y: isAnimating ? 0 : 20)
                    .animation(
                        DesignSystem.Animation.smooth.delay(0.4),
                        value: isAnimating
                    )

                    // Demographic Data Section (Optional)
                    VStack(spacing: DesignSystem.Spacing.lg) {
                        // Section Header
                        VStack(spacing: DesignSystem.Spacing.xs) {
                            Text("Help Improve Our Research")
                                .font(Typography.h4)
                                .foregroundColor(ColorPalette.textPrimary)
                                .frame(maxWidth: .infinity, alignment: .leading)

                            Text("This optional information helps us validate test accuracy. All data remains private.")
                                .font(Typography.captionMedium)
                                .foregroundColor(ColorPalette.textSecondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        // Birth Year field
                        CustomTextField(
                            title: "Birth Year (Optional)",
                            placeholder: "e.g., 1990",
                            text: $viewModel.birthYear,
                            keyboardType: .numberPad
                        )

                        // Education Level picker
                        VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
                            Text("Education Level (Optional)")
                                .font(Typography.captionLarge)
                                .foregroundColor(ColorPalette.textSecondary)

                            Menu {
                                Button("None selected") {
                                    viewModel.selectedEducationLevel = nil
                                }

                                ForEach(EducationLevel.allCases, id: \.self) { level in
                                    Button(level.displayName) {
                                        viewModel.selectedEducationLevel = level
                                    }
                                }
                            } label: {
                                HStack {
                                    Text(viewModel.selectedEducationLevel?.displayName ?? "Select education level")
                                        .font(Typography.bodyMedium)
                                        .foregroundColor(
                                            viewModel.selectedEducationLevel == nil
                                                ? ColorPalette.textSecondary
                                                : ColorPalette.textPrimary
                                        )

                                    Spacer()

                                    Image(systemName: "chevron.down")
                                        .font(.system(size: DesignSystem.IconSize.sm))
                                        .foregroundColor(ColorPalette.textSecondary)
                                }
                                .padding(DesignSystem.Spacing.md)
                                .background(ColorPalette.backgroundSecondary)
                                .cornerRadius(DesignSystem.CornerRadius.md)
                            }
                            .accessibilityLabel(
                                "Education Level, optional, " +
                                    "\(viewModel.selectedEducationLevel?.displayName ?? "not selected")"
                            )
                            .accessibilityHint("Double tap to open menu and select your education level")
                        }

                        // Country field
                        CustomTextField(
                            title: "Country (Optional)",
                            placeholder: "e.g., United States",
                            text: $viewModel.country,
                            autocapitalization: .words
                        )

                        // Region field
                        CustomTextField(
                            title: "State/Region (Optional)",
                            placeholder: "e.g., California",
                            text: $viewModel.region,
                            autocapitalization: .words
                        )
                    }
                    .opacity(isAnimating ? 1.0 : 0.0)
                    .offset(y: isAnimating ? 0 : 20)
                    .animation(
                        DesignSystem.Animation.smooth.delay(0.5),
                        value: isAnimating
                    )

                    // Register button
                    VStack(spacing: DesignSystem.Spacing.xl) {
                        PrimaryButton(
                            title: "Create Account",
                            action: {
                                Task {
                                    await viewModel.register()
                                }
                            },
                            isLoading: viewModel.isLoading,
                            isDisabled: !viewModel.isFormValid,
                            accessibilityId: AccessibilityIdentifiers.RegistrationView.createAccountButton
                        )
                        .padding(.top, DesignSystem.Spacing.sm)
                    }
                    .opacity(isAnimating ? 1.0 : 0.0)
                    .offset(y: isAnimating ? 0 : 20)
                    .animation(
                        DesignSystem.Animation.smooth.delay(0.6),
                        value: isAnimating
                    )

                    // Login Link
                    VStack(spacing: DesignSystem.Spacing.md) {
                        Text("Already have an account?")
                            .font(Typography.bodyMedium)
                            .foregroundColor(ColorPalette.textSecondary)

                        Button(
                            action: {
                                dismiss()
                            },
                            label: {
                                Text("Sign In")
                                    .font(Typography.button)
                                    .foregroundColor(ColorPalette.primary)
                            }
                        )
                        .accessibilityIdentifier(AccessibilityIdentifiers.RegistrationView.signInLink)
                    }
                    .padding(.top, DesignSystem.Spacing.sm)
                    .opacity(isAnimating ? 1.0 : 0.0)
                    .animation(
                        DesignSystem.Animation.smooth.delay(0.8),
                        value: isAnimating
                    )

                    Spacer()
                }
                .padding(.horizontal, DesignSystem.Spacing.xxl)
            }

            // Loading overlay
            if viewModel.isLoading {
                LoadingOverlay(message: "Creating account...")
            }
        }
        .navigationTitle("Register")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Registration Benefits Component

/// Displays key benefits of creating an account
struct RegistrationBenefits: View {
    var body: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            RegistrationBenefitCard(
                icon: "person.fill.badge.plus",
                title: "Personalized Tracking",
                description: "Your progress, your insights, your journey",
                color: ColorPalette.statBlue
            )

            RegistrationBenefitCard(
                icon: "lock.shield.fill",
                title: "Secure & Private",
                description: "Your data is encrypted and never shared",
                color: ColorPalette.statGreen
            )

            RegistrationBenefitCard(
                icon: "chart.xyaxis.line",
                title: "Visual Analytics",
                description: "Beautiful charts tracking your cognitive growth",
                color: ColorPalette.statOrange
            )
        }
        .padding(.horizontal, DesignSystem.Spacing.xl)
    }
}

/// Individual benefit card with icon, title, and description
struct RegistrationBenefitCard: View {
    let icon: String
    let title: String
    let description: String
    let color: Color

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            // Icon
            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.lg))
                .foregroundColor(color)
                .frame(width: 50, height: 50)
                .accessibilityHidden(true)

            // Text Content
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
                Text(title)
                    .font(Typography.bodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(ColorPalette.textPrimary)

                Text(description)
                    .font(Typography.bodySmall)
                    .foregroundColor(ColorPalette.textSecondary)
            }

            Spacer()
        }
        .padding(DesignSystem.Spacing.md)
        .background(ColorPalette.backgroundSecondary)
        .cornerRadius(DesignSystem.CornerRadius.md)
        .shadow(
            color: DesignSystem.Shadow.sm.color,
            radius: DesignSystem.Shadow.sm.radius,
            x: DesignSystem.Shadow.sm.x,
            y: DesignSystem.Shadow.sm.y
        )
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    NavigationStack {
        RegistrationView()
    }
}
