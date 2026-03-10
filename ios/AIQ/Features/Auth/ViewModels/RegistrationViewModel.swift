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
            isFirstNameValid && isLastNameValid && isBirthYearValid
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

    var isBirthYearValid: Bool {
        Validators.validateBirthYear(birthYear).isValid
    }

    var emailError: String? {
        validationError(for: email, using: Validators.validateEmail)
    }

    var passwordError: String? {
        validationError(for: password, using: Validators.validatePassword)
    }

    var confirmPasswordError: String? {
        validationError(for: confirmPassword, matching: password, using: Validators.validatePasswordConfirmation)
    }

    var firstNameError: String? {
        validationError(for: firstName, using: { Validators.validateName($0, fieldName: "First name") })
    }

    var lastNameError: String? {
        validationError(for: lastName, using: { Validators.validateName($0, fieldName: "Last name") })
    }

    var birthYearError: String? {
        validationError(for: birthYear, using: Validators.validateBirthYear)
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
