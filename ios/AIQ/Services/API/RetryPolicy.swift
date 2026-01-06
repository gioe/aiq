import Foundation

/// Defines retry behavior for failed network requests
struct RetryPolicy {
    let maxAttempts: Int
    let retryableStatusCodes: Set<Int>
    let retryableErrors: Set<URLError.Code>
    let delayCalculator: (Int) -> TimeInterval

    /// Default retry policy with exponential backoff
    static let `default` = RetryPolicy(
        maxAttempts: Constants.Network.defaultMaxRetryAttempts,
        retryableStatusCodes: Constants.Network.retryableStatusCodes,
        retryableErrors: [
            .timedOut,
            .networkConnectionLost,
            .notConnectedToInternet,
            .cannotConnectToHost
        ],
        delayCalculator: { attempt in
            // Exponential backoff: 1s, 2s, 4s
            pow(2.0, Double(attempt - 1))
        }
    )

    /// No retry policy
    static let none = RetryPolicy(
        maxAttempts: 1,
        retryableStatusCodes: [],
        retryableErrors: [],
        delayCalculator: { _ in 0 }
    )

    /// Check if a status code should be retried
    func shouldRetry(statusCode: Int) -> Bool {
        retryableStatusCodes.contains(statusCode)
    }

    /// Check if an error should be retried
    func shouldRetry(error: Error) -> Bool {
        guard let urlError = error as? URLError else {
            return false
        }
        return retryableErrors.contains(urlError.code)
    }

    /// Calculate delay before retry attempt
    func delay(for attempt: Int) -> TimeInterval {
        delayCalculator(attempt)
    }
}

/// Helper for executing requests with retry logic
struct RetryExecutor {
    let policy: RetryPolicy

    /// Execute a request with retry logic
    func execute<T>(
        _ operation: () async throws -> (T, HTTPURLResponse)
    ) async throws -> T {
        var lastError: Error?
        var attempt = 1

        while attempt <= policy.maxAttempts {
            do {
                let (result, response) = try await operation()

                // Check if status code indicates we should retry
                if attempt < policy.maxAttempts && policy.shouldRetry(statusCode: response.statusCode) {
                    let delay = policy.delay(for: attempt)
                    try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    attempt += 1
                    continue
                }

                return result
            } catch {
                lastError = error

                // Check if error indicates we should retry
                if attempt < policy.maxAttempts && policy.shouldRetry(error: error) {
                    let delay = policy.delay(for: attempt)
                    try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    attempt += 1
                    continue
                }

                // Error not retryable or max attempts reached
                throw error
            }
        }

        // If we get here, we exhausted all retries
        throw lastError ?? (APIError.unknown() as Error)
    }
}
