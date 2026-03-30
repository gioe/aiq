import Foundation

/// Protocol for errors that communicate retryability
public protocol RetryableError: Error {
    var isRetryable: Bool { get }
}
