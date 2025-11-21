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

    /// Handle errors and set them for display
    func handleError(_ error: Error, retryOperation: (() async -> Void)? = nil) {
        isLoading = false
        self.error = error
        lastFailedOperation = retryOperation

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
