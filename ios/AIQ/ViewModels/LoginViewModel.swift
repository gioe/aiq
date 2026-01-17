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
        Validators.validateEmail(email).isValid
    }

    var isPasswordValid: Bool {
        Validators.validatePassword(password).isValid
    }

    var emailError: String? {
        validationError(for: email, using: Validators.validateEmail)
    }

    var passwordError: String? {
        validationError(for: password, using: Validators.validatePassword)
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
