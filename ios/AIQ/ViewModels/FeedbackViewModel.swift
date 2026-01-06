import Foundation

/// ViewModel for managing feedback form state and validation
@MainActor
class FeedbackViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var name: String = ""
    @Published var email: String = ""
    @Published var selectedCategory: FeedbackCategory?
    @Published var description: String = ""
    @Published var showSuccessMessage: Bool = false

    // MARK: - Validation

    /// Validate the name field
    var nameValidation: ValidationResult {
        Validators.validateName(name, fieldName: "Name")
    }

    /// Validate the email field
    var emailValidation: ValidationResult {
        Validators.validateEmail(email)
    }

    /// Validate the category field
    var categoryValidation: ValidationResult {
        guard selectedCategory != nil else {
            return .invalid("Please select a category")
        }
        return .valid
    }

    /// Validate the description field
    var descriptionValidation: ValidationResult {
        Validators.validateFeedbackDescription(description)
    }

    /// Check if the entire form is valid
    var isFormValid: Bool {
        nameValidation.isValid &&
            emailValidation.isValid &&
            categoryValidation.isValid &&
            descriptionValidation.isValid
    }

    // MARK: - Actions

    /// Submit the feedback form
    /// - Note: This is a UI-only implementation since the backend endpoint doesn't exist yet
    func submitFeedback() async {
        // Validate form first
        guard isFormValid else { return }

        setLoading(true)

        // Simulate API call delay
        try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 second

        // In a real implementation, this would call the backend:
        // let feedback = Feedback(
        //     name: name,
        //     email: email,
        //     category: selectedCategory!,
        //     description: description
        // )
        // try await apiClient.request(
        //     endpoint: .submitFeedback,
        //     method: .post,
        //     body: feedback,
        //     requiresAuth: true
        // )

        setLoading(false)
        showSuccessMessage = true

        // Reset form after showing success
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            self?.resetForm()
        }
    }

    /// Reset the form to initial state
    func resetForm() {
        name = ""
        email = ""
        selectedCategory = nil
        description = ""
        showSuccessMessage = false
        clearError()
    }
}
