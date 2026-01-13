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
}
