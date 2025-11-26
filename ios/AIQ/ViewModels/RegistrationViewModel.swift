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
        !email.isEmpty && email.contains("@") && email.contains(".")
    }

    var isPasswordValid: Bool {
        password.count >= 8
    }

    var isConfirmPasswordValid: Bool {
        !confirmPassword.isEmpty && password == confirmPassword
    }

    var isFirstNameValid: Bool {
        !firstName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    var isLastNameValid: Bool {
        !lastName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    var emailError: String? {
        guard !email.isEmpty else { return nil }
        return isEmailValid ? nil : "Please enter a valid email address"
    }

    var passwordError: String? {
        guard !password.isEmpty else { return nil }
        return isPasswordValid ? nil : "Password must be at least 8 characters"
    }

    var confirmPasswordError: String? {
        guard !confirmPassword.isEmpty else { return nil }
        return isConfirmPasswordValid ? nil : "Passwords do not match"
    }

    var firstNameError: String? {
        guard !firstName.isEmpty else { return nil }
        return isFirstNameValid ? nil : "First name is required"
    }

    var lastNameError: String? {
        guard !lastName.isEmpty else { return nil }
        return isLastNameValid ? nil : "Last name is required"
    }

    // MARK: - Actions

    func register() async {
        guard isFormValid else {
            error = NSError(
                domain: "RegistrationViewModel",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Please fill in all fields correctly"]
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
                country: country.trimmingCharacters(in: .whitespaces).isEmpty ? nil : country.trimmingCharacters(in: .whitespaces),
                region: region.trimmingCharacters(in: .whitespaces).isEmpty ? nil : region.trimmingCharacters(in: .whitespaces)
            )
            // Clear sensitive data on success
            clearForm()
        } catch {
            // Error is already set via authManager.$authError binding
            // Just log for debugging
            print("Registration error: \(error.localizedDescription)")
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
