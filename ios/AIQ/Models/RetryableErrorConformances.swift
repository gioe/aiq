import AIQSharedKit
import Foundation

// Declare conformance of AIQ error types to SharedKit's RetryableError protocol.
// AppError already has isRetryable: Bool, so no implementation body is needed —
// the protocol requirement is already satisfied.
extension AppError: RetryableError {}
extension ContextualError: RetryableError {}
