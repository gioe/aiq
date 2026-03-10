import Foundation

/// ViewModel for managing feedback form state and validation
@MainActor
class FeedbackViewModel: BaseViewModel {
    // MARK: - Dependencies

    private let apiService: OpenAPIServiceProtocol
    private let authManager: AuthManagerProtocol?

    // MARK: - Private State

    /// Task tracking the delayed form reset, allowing cancellation on rapid resubmission
    private var resetTask: Task<Void, Never>?

    // MARK: - Published Properties

    @Published var name: String = ""
    @Published var email: String = ""
    @Published var selectedCategory: FeedbackCategory?
    @Published var description: String = ""
    @Published var showSuccessMessage: Bool = false

    // MARK: - Initialization

    /// Initialize the ViewModel with dependencies
    /// - Parameters:
    ///   - apiService: API service for network requests
    ///   - authManager: Auth manager for accessing current user (optional for pre-populating email)
    init(apiService: OpenAPIServiceProtocol, authManager: AuthManagerProtocol? = nil) {
        self.apiService = apiService
        self.authManager = authManager
        super.init()

        // Pre-populate email from authenticated user if available
        if let currentUser = authManager?.currentUser {
            email = currentUser.email
        }
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

        // Safely unwrap selectedCategory - should always succeed after isFormValid check
        guard let category = selectedCategory else { return }

        setLoading(true)
        clearError()

        do {
            // Create feedback request body
            let feedback = Feedback(
                category: category,
                description: description,
                email: email,
                name: name
            )

            // Submit feedback to backend (no authentication required)
            let response = try await apiService.submitFeedback(feedback)

            setLoading(false)

            // Show success message from backend or default
            if response.success {
                showSuccessMessage = true

                // Cancel any pending reset from a previous submission
                resetTask?.cancel()

                // Schedule form reset after showing success for 2 seconds.
                // Using try? is safe here - CancellationError from Task.sleep is expected
                // when task is cancelled, and the guard below handles the exit gracefully.
                resetTask = Task {
                    try? await Task.sleep(for: .seconds(2))
                    guard !Task.isCancelled else { return }
                    resetForm()
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

    /// Reset the form to initial state, preserving pre-populated email for authenticated users
    func resetForm() {
        resetTask?.cancel()
        resetTask = nil
        name = ""
        // Preserve pre-populated email for authenticated users
        if let currentUser = authManager?.currentUser {
            email = currentUser.email
        } else {
            email = ""
        }
        selectedCategory = nil
        description = ""
        showSuccessMessage = false
        clearError()
    }
}
