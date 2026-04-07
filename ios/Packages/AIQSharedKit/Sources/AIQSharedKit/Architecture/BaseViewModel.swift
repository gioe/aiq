import Combine
import Foundation

/// Base class for ViewModels providing common functionality
open class BaseViewModel: ObservableObject {
    @Published public var isLoading: Bool = false
    /// Indicates whether a pull-to-refresh operation is in progress.
    /// Not `@Published` intentionally: publishing this change triggers a SwiftUI re-render that passes
    /// a new closure to `.refreshable`, causing `UIKitRefreshControl.configuration.didset` to call
    /// `swift_task_cancel` on the in-flight task — cancelling the very refresh it was meant to guard.
    public var isRefreshing: Bool = false
    @Published public var error: Error?
    /// Indicates whether the last failed operation can be retried
    @Published public var canRetry: Bool = false

    /// Storage for Combine subscriptions
    public var cancellables = Set<AnyCancellable>()
    private var lastFailedOperation: (() async -> Void)?

    /// Optional error recorder for reporting errors to a crash/analytics backend
    private let errorRecorder: ErrorRecorder?

    public init() {
        errorRecorder = nil
    }

    public init(errorRecorder: ErrorRecorder?) {
        self.errorRecorder = errorRecorder
    }

    /// Handle errors and set them for display.
    /// Also records non-fatal errors to the error recorder (if configured) for production monitoring.
    ///
    /// - Parameters:
    ///   - error: The error to handle
    ///   - context: A string context for categorizing the error
    ///   - retryOperation: Optional closure to retry the failed operation
    open func handleError(
        _ error: Error,
        context: String,
        retryOperation: (() async -> Void)? = nil
    ) {
        let nsError = error as NSError
        guard !(error is CancellationError)
            && !(nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorCancelled)
        else { isLoading = false; return }
        isLoading = false
        self.error = error
        lastFailedOperation = retryOperation

        // Record to error backend for production monitoring
        errorRecorder?.recordError(error, context: context)

        // Check if error is retryable
        if let retryable = error as? RetryableError {
            canRetry = retryable.isRetryable
        } else {
            canRetry = false
        }
    }

    /// Clear any existing error
    open func clearError() {
        // Guard each assignment so @Published only fires objectWillChange when the value
        // actually changes. Unconditional assignment (even to the same value) fires
        // objectWillChange, which triggers a SwiftUI re-render that passes a new closure
        // to .refreshable — causing UIKitRefreshControl.configuration.didset to call
        // swift_task_cancel on the in-flight refresh task.
        if error != nil { error = nil }
        if canRetry { canRetry = false }
        lastFailedOperation = nil
    }

    /// Set loading state
    open func setLoading(_ loading: Bool) {
        if isLoading != loading { isLoading = loading }
    }

    /// Runs `operation` guarded against concurrent calls, setting `isRefreshing` for the duration.
    ///
    /// If `isRefreshing` is already `true` when called, the function returns immediately without
    /// invoking `operation`. This prevents the retry cascade that can occur when multiple callers
    /// (e.g. `.refreshable`, `onAppear`, `NotificationCenter`) trigger a refresh simultaneously.
    ///
    /// - Parameter operation: The async work to perform during the refresh.
    @MainActor public func withRefreshing(_ operation: () async -> Void) async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        await operation()
    }

    /// Retry the last failed operation
    public func retry() async {
        guard let operation = lastFailedOperation else { return }
        // Set loading before clearing the error so the loading overlay appears
        // immediately when shouldShowLoadFailure transitions to false, preventing
        // testContentView from briefly rendering without the overlay.
        setLoading(true)
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
    public func validationError(for value: String, using validator: (String) -> ValidationResult) -> String? {
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
    public func validationError(
        for value: String,
        matching original: String,
        using validator: (String, String) -> ValidationResult
    ) -> String? {
        guard !value.isEmpty else { return nil }
        return validator(original, value).errorMessage
    }
}
