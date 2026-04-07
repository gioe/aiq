import Foundation

/// Protocol for recording errors to a crash/analytics backend
public protocol ErrorRecorder {
    /// Record an error with the given context description
    func recordError(_ error: Error, context: String)
}
