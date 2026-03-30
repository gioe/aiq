import Foundation

/// Protocol for recording errors to a crash/analytics backend
public protocol ErrorRecorder {
    func recordError(_ error: Error, context: String)
}
