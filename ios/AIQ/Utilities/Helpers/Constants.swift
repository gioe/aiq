import Foundation

/// Centralized constants for the AIQ application.
/// Organizes magic numbers into domain-specific namespaces to improve maintainability.
enum Constants {
    // MARK: - Timing Constants

    /// Time-related constants used throughout the application
    enum Timing {
        /// Total test time limit in seconds (35 minutes)
        /// Based on psychometric testing standards for cognitive assessments
        /// Scaled from 30 to 35 minutes to maintain ~84 sec/question with 25 questions
        static let totalTestTimeSeconds: Int = 2100

        /// Timer warning threshold in seconds (5 minutes remaining)
        /// When timer reaches this threshold, UI shows warning state (orange color)
        static let warningThresholdSeconds: Int = 300

        /// Timer critical threshold in seconds (last 60 seconds of test)
        /// When timer reaches this threshold, UI shows critical state (red color)
        static let criticalThresholdSeconds: Int = 60

        /// Timer update interval in seconds (0.25s)
        /// Faster interval provides more responsive UI updates for countdown display
        static let timerUpdateInterval: TimeInterval = 0.25

        /// Auto-save delay in seconds for test progress
        /// Throttles save operations to avoid excessive disk writes
        static let autoSaveDelay: TimeInterval = 1.0
    }

    // MARK: - Network Constants

    /// Network and API-related constants
    enum Network {
        /// Default request timeout in seconds for API calls
        /// Balances responsiveness with network reliability
        static let requestTimeout: TimeInterval = 30.0

        /// Maximum number of token refresh retry attempts
        /// Limited to 1 retry to avoid excessive auth loops
        static let maxTokenRefreshRetries: Int = 1

        /// Default maximum retry attempts for retryable requests
        /// Applied to network errors and specific HTTP status codes
        static let defaultMaxRetryAttempts: Int = 3

        /// HTTP status codes that should trigger automatic retry
        /// Includes timeout (408), rate limit (429), and server errors (5xx)
        /// Kept as Set for O(1) lookup performance
        static let retryableStatusCodes: Set<Int> = [408, 429, 500, 502, 503, 504]

        /// Slow request threshold in seconds
        /// Requests exceeding this duration are logged to analytics for monitoring
        static let slowRequestThreshold: TimeInterval = 2.0
    }

    // MARK: - Test Constants

    /// Test session and progress-related constants
    enum Test {
        /// Default number of questions per test session
        /// Calibrated for statistical reliability while minimizing test fatigue
        static let defaultQuestionCount: Int = 25

        /// Progress validity duration in seconds (24 hours)
        /// Saved test progress is only valid if saved within this time window
        static let progressValidityDuration: TimeInterval = 24 * 60 * 60
    }

    // MARK: - Analytics Constants

    /// Analytics and event tracking configuration
    enum Analytics {
        /// Maximum number of events to batch together in a single submission
        /// Balances network efficiency with memory usage
        static let maxBatchSize: Int = 50

        /// Maximum number of events to queue before dropping oldest events
        /// Prevents unbounded memory growth if submissions fail
        static let maxQueueSize: Int = 500

        /// Maximum retry attempts for failed analytics submissions
        /// Prevents excessive retry loops while ensuring delivery reliability
        static let maxRetries: Int = 3

        /// Interval between automatic batch submissions in seconds
        /// Ensures timely delivery while batching for efficiency
        static let batchInterval: TimeInterval = 30.0

        /// Request timeout for analytics API calls in seconds
        /// Longer timeout allows for batch processing on backend
        static let requestTimeout: TimeInterval = 30.0
    }

    // MARK: - Cache Constants

    /// Data caching configuration
    enum Cache {
        /// Default cache expiration duration in seconds (5 minutes)
        /// Applied when no specific expiration is provided
        static let defaultExpiration: TimeInterval = 300

        /// Dashboard data cache duration in seconds (2 minutes)
        /// Shorter duration ensures dashboard data stays relatively fresh
        static let dashboardCacheDuration: TimeInterval = 120
    }

    // MARK: - Validation Constants

    /// User input validation rules
    enum Validation {
        /// Minimum password length in characters
        /// Balances security with usability
        static let minPasswordLength: Int = 8

        /// Minimum name length in characters
        /// Ensures meaningful user identification
        static let minNameLength: Int = 2

        /// Minimum birth year allowed for user registration
        /// Set to 1900 to support oldest living users
        static let minBirthYear: Int = 1900
    }

    // MARK: - Pagination Constants

    /// Pagination and data loading configuration
    enum Pagination {
        /// Number of history records to load per page
        /// Balances initial load time with scrolling performance
        static let historyPageSize: Int = 50
    }

    // MARK: - Onboarding Constants

    /// Onboarding flow configuration
    enum Onboarding {
        /// Total number of onboarding pages
        /// Update when adding or removing onboarding screens
        static let totalPages: Int = 4
    }

    // MARK: - Security Constants

    /// Security and certificate pinning configuration
    enum Security {
        /// Minimum number of certificate pins required per domain
        /// Per TrustKit best practices: always pin at least 2 certificates
        /// (primary + backup) to avoid lockouts during certificate rotation
        /// See: ios/docs/security/CERTIFICATE-PINNING.md
        static let minRequiredPins: Int = 2
    }

    // MARK: - Feature Flags

    /// Feature flags for gating unreleased functionality
    enum Features {
        /// Adaptive (CAT) test delivery
        /// When false, the app always uses the fixed-form test flow.
        /// When true, the app calls /v1/test/start?adaptive=true and uses
        /// question-by-question delivery via /v1/test/next.
        /// The backend independently gates this via the `adaptive` query parameter.
        static var adaptiveTesting: Bool = false
    }

    // MARK: - Background Refresh Constants

    /// Background refresh task configuration
    enum BackgroundRefresh {
        /// Background task identifier (must match Info.plist entry)
        static let taskIdentifier: String = "com.aiq.refresh"

        /// Minimum interval between refresh attempts in seconds (4 hours)
        /// iOS will optimize actual timing based on app usage patterns
        static let minimumInterval: TimeInterval = 4 * 60 * 60

        /// Test cadence in days (90 days between tests)
        /// User is notified when this many days have passed since last test
        static let testCadenceDays: Int = 90

        /// Maximum execution time for background refresh in seconds
        /// iOS gives 30s max, we aim for 20s to have safety margin
        static let maxExecutionTime: TimeInterval = 20.0
    }
}
