import AIQSharedKit
import Foundation

/// Adapts CrashlyticsErrorRecorder to the SharedKit ErrorRecorder protocol
///
/// CrashlyticsErrorRecorder is an enum (not a class), so it cannot directly conform
/// to protocols requiring instance methods. This adapter wraps it to bridge
/// SharedKit's ErrorRecorder protocol to the AIQ-specific Crashlytics recorder.
///
/// Usage in ViewModels:
/// ```swift
/// class MyViewModel: BaseViewModel {
///     init() {
///         super.init(errorRecorder: CrashlyticsRecorderAdapter())
///     }
/// }
/// ```
struct CrashlyticsRecorderAdapter: ErrorRecorder {
    func recordError(_ error: Error, context: String) {
        let ctx = CrashlyticsErrorRecorder.ErrorContext(rawValue: context) ?? .unknown
        CrashlyticsErrorRecorder.recordError(error, context: ctx)
    }
}
