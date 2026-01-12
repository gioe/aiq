import Foundation

/// ViewModel for managing feedback form state and validation
@MainActor
class FeedbackViewModel: BaseViewModel {
    // MARK: - Dependencies

    private let apiClient: APIClientProtocol

    // MARK: - Published Properties

    @Published var name: String = ""
    @Published var email: String = ""
    @Published var selectedCategory: FeedbackCategory?
    @Published var description: String = ""
    @Published var showSuccessMessage: Bool = false

    // MARK: - Initialization

    /// Initialize the ViewModel with dependencies
    /// - Parameter apiClient: API client for network requests
    init(apiClient: APIClientProtocol) {
        self.apiClient = apiClient
        super.init()
    }

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
    func submitFeedback() async {
        // Validate form first
        guard isFormValid else { return }

        setLoading(true)
        clearError()

        do {
            // Create feedback request body
            let feedback = Feedback(
                name: name,
                email: email,
                category: selectedCategory!, // Safe unwrap - validated by isFormValid
                description: description
            )

            // Submit feedback to backend (no authentication required)
            let response: FeedbackSubmitResponse = try await apiClient.request(
                endpoint: .submitFeedback,
                method: .post,
                body: feedback,
                requiresAuth: false
            )

            setLoading(false)

            // Show success message from backend or default
            if response.success {
                showSuccessMessage = true

                // Reset form after showing success for 2 seconds
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                    self?.resetForm()
                }
            } else {
                // Backend returned success=false - treat as error
                error = NSError(
                    domain: "FeedbackViewModel",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: response.message]
                )
            }
        } catch let apiError {
            setLoading(false)
            handleError(apiError, context: .submitFeedback) { [weak self] in
                await self?.submitFeedback()
            }
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
