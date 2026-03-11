import Foundation
import SharedKit

// Declare conformance of AIQ error types to SharedKit's RetryableError protocol.
// Both APIError and ContextualError already have isRetryable: Bool, so no
// implementation body is needed — the protocol requirement is already satisfied.
extension APIError: RetryableError {}
extension ContextualError: RetryableError {}
