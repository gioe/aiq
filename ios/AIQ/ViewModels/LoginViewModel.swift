import Combine
import Foundation

/// ViewModel for handling login logic and state
@MainActor
class LoginViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var email: String = ""
    @Published var password: String = ""
    @Published var showRegistration: Bool = false

    // MARK: - Private Properties

    private let authManager: any AuthManagerProtocol

    // MARK: - Initialization

    init(authManager: any AuthManagerProtocol) {
        self.authManager = authManager
        super.init()

        // Observe auth manager state
        authManager.isLoadingPublisher
            .assign(to: &$isLoading)

        authManager.authErrorPublisher
            .assign(to: &$error)
    }

    // MARK: - Validation

    var isFormValid: Bool {
        isEmailValid && isPasswordValid
    }

    var isEmailValid: Bool {
        !email.isEmpty && email.contains("@") && email.contains(".")
    }

    var isPasswordValid: Bool {
        password.count >= 8
    }

    var emailError: String? {
        guard !email.isEmpty else { return nil }
        return isEmailValid ? nil : "validation.email.invalid".localized
    }

    var passwordError: String? {
        guard !password.isEmpty else { return nil }
        return isPasswordValid ? nil : "validation.password.too.short".localized
    }

    // MARK: - Actions

    func login() async {
        guard isFormValid else {
            error = NSError(
                domain: "LoginViewModel",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "validation.login.invalid".localized]
            )
            return
        }

        do {
            try await authManager.login(email: email, password: password)
            // Clear sensitive data on success
            clearForm()
        } catch {
            // Error is already set via authManager.$authError binding
            // Record to Crashlytics for production monitoring
            CrashlyticsErrorRecorder.recordError(error, context: .login)
        }
    }

    func showRegistrationScreen() {
        showRegistration = true
    }

    func clearForm() {
        email = ""
        password = ""
        error = nil
        authManager.clearError()
    }
}
