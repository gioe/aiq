import SwiftUI

/// Registration screen
struct RegistrationView: View {
    @StateObject private var viewModel = RegistrationViewModel(authManager: AuthManager.shared)
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 12) {
                        Text("Create Account")
                            .font(.system(size: 34, weight: .bold))
                            .foregroundColor(.accentColor)

                        Text("Join IQ Tracker to start tracking your cognitive performance")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    .padding(.top, 40)

                    // Registration Form
                    VStack(spacing: 20) {
                        // Name fields
                        HStack(spacing: 12) {
                            VStack(spacing: 8) {
                                CustomTextField(
                                    title: "First Name",
                                    placeholder: "John",
                                    text: $viewModel.firstName,
                                    autocapitalization: .words
                                )

                                if let firstNameError = viewModel.firstNameError {
                                    Text(firstNameError)
                                        .font(.caption)
                                        .foregroundColor(.red)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }

                            VStack(spacing: 8) {
                                CustomTextField(
                                    title: "Last Name",
                                    placeholder: "Doe",
                                    text: $viewModel.lastName,
                                    autocapitalization: .words
                                )

                                if let lastNameError = viewModel.lastNameError {
                                    Text(lastNameError)
                                        .font(.caption)
                                        .foregroundColor(.red)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }
                        }

                        // Email field
                        CustomTextField(
                            title: "Email",
                            placeholder: "your.email@example.com",
                            text: $viewModel.email,
                            keyboardType: .emailAddress,
                            autocapitalization: .never
                        )

                        if let emailError = viewModel.emailError {
                            Text(emailError)
                                .font(.caption)
                                .foregroundColor(.red)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        // Password field
                        CustomTextField(
                            title: "Password",
                            placeholder: "At least 8 characters",
                            text: $viewModel.password,
                            isSecure: true
                        )

                        if let passwordError = viewModel.passwordError {
                            Text(passwordError)
                                .font(.caption)
                                .foregroundColor(.red)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        // Confirm password field
                        CustomTextField(
                            title: "Confirm Password",
                            placeholder: "Re-enter your password",
                            text: $viewModel.confirmPassword,
                            isSecure: true
                        )

                        if let confirmPasswordError = viewModel.confirmPasswordError {
                            Text(confirmPasswordError)
                                .font(.caption)
                                .foregroundColor(.red)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        // Register button
                        PrimaryButton(
                            title: "Create Account",
                            action: {
                                Task {
                                    await viewModel.register()
                                }
                            },
                            isLoading: viewModel.isLoading,
                            isDisabled: !viewModel.isFormValid
                        )
                        .padding(.top, 8)
                    }

                    // Error Display
                    if let error = viewModel.error {
                        ErrorBanner(
                            message: error.localizedDescription,
                            onDismiss: {
                                viewModel.clearForm()
                            }
                        )
                    }

                    // Login Link
                    VStack(spacing: 12) {
                        Text("Already have an account?")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        Button(
                            action: {
                                dismiss()
                            },
                            label: {
                                Text("Sign In")
                                    .font(.headline)
                                    .foregroundColor(.accentColor)
                            }
                        )
                    }
                    .padding(.top, 8)

                    Spacer()
                }
                .padding(.horizontal, 24)
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

#Preview {
    NavigationStack {
        RegistrationView()
    }
}
