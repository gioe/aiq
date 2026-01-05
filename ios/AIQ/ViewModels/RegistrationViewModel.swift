import Combine
import Foundation

/// ViewModel for handling registration logic and state
@MainActor
class RegistrationViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var email: String = ""
    @Published var password: String = ""
    @Published var confirmPassword: String = ""
    @Published var firstName: String = ""
    @Published var lastName: String = ""

    // Optional demographic data for norming study (P13-001)
    @Published var birthYear: String = ""
    @Published var selectedEducationLevel: EducationLevel?
    @Published var country: String = ""
    @Published var region: String = ""

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
        isEmailValid && isPasswordValid && isConfirmPasswordValid &&
            isFirstNameValid && isLastNameValid
    }

    var isEmailValid: Bool {
        Validators.validateEmail(email).isValid
    }

    var isPasswordValid: Bool {
        Validators.validatePassword(password).isValid
    }

    var isConfirmPasswordValid: Bool {
        guard !confirmPassword.isEmpty else { return false }
        return Validators.validatePasswordConfirmation(password, confirmPassword).isValid
    }

    var isFirstNameValid: Bool {
        Validators.validateName(firstName, fieldName: "First name").isValid
    }

    var isLastNameValid: Bool {
        Validators.validateName(lastName, fieldName: "Last name").isValid
    }

    var emailError: String? {
        guard !email.isEmpty else { return nil }
        let result = Validators.validateEmail(email)
        return result.errorMessage
    }

    var passwordError: String? {
        guard !password.isEmpty else { return nil }
        let result = Validators.validatePassword(password)
        return result.errorMessage
    }

    var confirmPasswordError: String? {
        guard !confirmPassword.isEmpty else { return nil }
        let result = Validators.validatePasswordConfirmation(password, confirmPassword)
        return result.errorMessage
    }

    var firstNameError: String? {
        guard !firstName.isEmpty else { return nil }
        let result = Validators.validateName(firstName, fieldName: "First name")
        return result.errorMessage
    }

    var lastNameError: String? {
        guard !lastName.isEmpty else { return nil }
        let result = Validators.validateName(lastName, fieldName: "Last name")
        return result.errorMessage
    }

    // MARK: - Actions

    func register() async {
        guard isFormValid else {
            error = NSError(
                domain: "RegistrationViewModel",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "validation.form.incomplete".localized]
            )
            return
        }

        // Convert birthYear string to Int if valid
        let birthYearInt: Int? = {
            let trimmed = birthYear.trimmingCharacters(in: .whitespaces)
            return trimmed.isEmpty ? nil : Int(trimmed)
        }()

        do {
            try await authManager.register(
                email: email.trimmingCharacters(in: .whitespaces),
                password: password,
                firstName: firstName.trimmingCharacters(in: .whitespaces),
                lastName: lastName.trimmingCharacters(in: .whitespaces),
                birthYear: birthYearInt,
                educationLevel: selectedEducationLevel,
                country: country.trimmingCharacters(in: .whitespaces).isEmpty
                    ? nil : country.trimmingCharacters(in: .whitespaces),
                region: region.trimmingCharacters(in: .whitespaces).isEmpty
                    ? nil : region.trimmingCharacters(in: .whitespaces)
            )
            // Clear sensitive data on success
            clearForm()
        } catch {
            // Error is already set via authManager.$authError binding
            // Record to Crashlytics for production monitoring
            CrashlyticsErrorRecorder.recordError(error, context: .registration)
        }
    }

    func clearForm() {
        email = ""
        password = ""
        confirmPassword = ""
        firstName = ""
        lastName = ""
        birthYear = ""
        selectedEducationLevel = nil
        country = ""
        region = ""
        error = nil
        authManager.clearError()
    }
}
