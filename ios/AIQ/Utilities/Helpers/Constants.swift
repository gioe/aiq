import Foundation

/// Centralized constants for the AIQ application.
/// Organizes magic numbers into domain-specific namespaces to improve maintainability.
enum Constants {
    // MARK: - Timing Constants

    /// Time-related constants used throughout the application
    enum Timing {
        /// Timer critical threshold in seconds (last 60 seconds of test)
        /// When timer reaches this threshold, UI shows critical state (red color)
        static let criticalThresholdSeconds: Int = 60

        /// Auto-save delay in seconds for test progress
        /// Throttles save operations to avoid excessive disk writes
        static let autoSaveDelay: TimeInterval = 1.0
    }

    // MARK: - Network Constants

    /// Network and API-related constants
    enum Network {
        /// Slow request threshold in seconds
        /// Requests exceeding this duration are logged to analytics for monitoring
        static let slowRequestThreshold: TimeInterval = 2.0
    }

    // MARK: - Test Constants

    /// Test session and progress-related constants
    enum Test {
        /// Progress validity duration in seconds (24 hours)
        /// Saved test progress is only valid if saved within this time window
        static let progressValidityDuration: TimeInterval = 24 * 60 * 60
    }
}
