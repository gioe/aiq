import SwiftUI

/// Welcome/Login screen
struct WelcomeView: View {
    @StateObject private var viewModel = LoginViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 32) {
                    // Header
                    VStack(spacing: 12) {
                        Text("IQ Tracker")
                            .font(.system(size: 42, weight: .bold))
                            .foregroundColor(.accentColor)

                        Text("Track your cognitive performance over time")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 60)

                    // Login Form
                    VStack(spacing: 20) {
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

                        CustomTextField(
                            title: "Password",
                            placeholder: "Enter your password",
                            text: $viewModel.password,
                            isSecure: true
                        )

                        if let passwordError = viewModel.passwordError {
                            Text(passwordError)
                                .font(.caption)
                                .foregroundColor(.red)
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
                            isDisabled: !viewModel.isFormValid
                        )
                        .padding(.top, 8)
                    }

                    // Error Display
                    if let error = viewModel.error {
                        ErrorView(error: error)
                            .onTapGesture {
                                viewModel.clearError()
                            }
                    }

                    // Registration Link
                    VStack(spacing: 12) {
                        Text("Don't have an account?")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        Button(
                            action: {
                                viewModel.showRegistrationScreen()
                            },
                            label: {
                                Text("Create Account")
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
            .navigationDestination(isPresented: $viewModel.showRegistration) {
                RegistrationView()
            }
        }
    }
}

#Preview {
    WelcomeView()
}
