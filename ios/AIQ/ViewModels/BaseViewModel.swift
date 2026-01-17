import Combine
import Foundation

/// Base class for ViewModels providing common functionality
class BaseViewModel: ObservableObject {
    @Published var isLoading: Bool = false
    @Published var error: Error?
    /// Indicates whether the last failed operation can be retried
    @Published var canRetry: Bool = false

    /// Storage for Combine subscriptions
    var cancellables = Set<AnyCancellable>()
    private var lastFailedOperation: (() async -> Void)?

    init() {}

    /// Handle errors and set them for display.
    /// Also records non-fatal errors to Crashlytics for production monitoring.
    ///
    /// - Parameters:
    ///   - error: The error to handle
    ///   - context: The Crashlytics context for categorizing the error
    ///   - retryOperation: Optional closure to retry the failed operation
    func handleError(
        _ error: Error,
        context: CrashlyticsErrorRecorder.ErrorContext,
        retryOperation: (() async -> Void)? = nil
    ) {
        isLoading = false
        self.error = error
        lastFailedOperation = retryOperation

        // Record to Crashlytics for production monitoring
        CrashlyticsErrorRecorder.recordError(error, context: context)

        // Check if error is retryable
        if let apiError = error as? APIError {
            canRetry = apiError.isRetryable
        } else if let contextualError = error as? ContextualError {
            canRetry = contextualError.isRetryable
        } else {
            canRetry = false
        }
    }

    /// Clear any existing error
    func clearError() {
        error = nil
        canRetry = false
        lastFailedOperation = nil
    }

    /// Set loading state
    func setLoading(_ loading: Bool) {
        isLoading = loading
    }

    /// Retry the last failed operation
    func retry() async {
        guard let operation = lastFailedOperation else { return }
        clearError()
        await operation()
    }

    // MARK: - Validation Helpers

    /// Returns the validation error message for a field, or nil if the field is empty or valid.
    ///
    /// This helper eliminates boilerplate for computed error properties. Use it when you want to:
    /// - Show no error for empty fields (before user interaction)
    /// - Show the validation error message only after user has entered something
    ///
    /// Example:
    /// ```swift
    /// var emailError: String? {
    ///     validationError(for: email, using: Validators.validateEmail)
    /// }
    /// ```
    ///
    /// - Parameters:
    ///   - value: The string value to validate
    ///   - validator: A closure that validates the value and returns a ValidationResult
    /// - Returns: The error message if the field is non-empty and invalid, nil otherwise
    func validationError(for value: String, using validator: (String) -> ValidationResult) -> String? {
        guard !value.isEmpty else { return nil }
        return validator(value).errorMessage
    }

    /// Returns the validation error message for a password confirmation field.
    ///
    /// This variant handles the common password confirmation pattern where two values must match.
    ///
    /// Example:
    /// ```swift
    /// var confirmPasswordError: String? {
    ///     validationError(for: confirmPassword, matching: password, using: Validators.validatePasswordConfirmation)
    /// }
    /// ```
    ///
    /// - Parameters:
    ///   - value: The confirmation value to validate (shown to user)
    ///   - original: The original value that must be matched
    ///   - validator: A closure that takes (original, confirmation) and returns a ValidationResult
    /// - Returns: The error message if the confirmation field is non-empty and invalid, nil otherwise
    func validationError(
        for value: String,
        matching original: String,
        using validator: (String, String) -> ValidationResult
    ) -> String? {
        guard !value.isEmpty else { return nil }
        return validator(original, value).errorMessage
    }
}
