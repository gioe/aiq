import Foundation

/// Detects whether the app is running in UI test mock mode
///
/// This utility checks for launch arguments and environment variables that indicate
/// the app should use mock services instead of real backend connections.
///
/// ## Usage
///
/// UI tests should launch the app with the `-UITestMockMode` argument:
/// ```swift
/// app.launchArguments = ["-UITestMockMode"]
/// app.launchEnvironment = ["MOCK_SCENARIO": "loggedInWithHistory"]
/// app.launch()
/// ```
///
/// The app checks this in `AIQApp.init()` to configure mock services:
/// ```swift
/// if MockModeDetector.isMockMode {
///     MockServiceConfiguration.configureServices(container: container)
/// } else {
///     ServiceConfiguration.configureServices(container: container)
/// }
/// ```
///
/// ## Security
///
/// Mock mode is only available in DEBUG builds to prevent accidental
/// activation in production.
enum MockModeDetector {
    /// The launch argument that enables mock mode
    static let mockModeArgument = "-UITestMockMode"

    /// Environment variable key for mock scenario selection
    static let scenarioEnvironmentKey = "MOCK_SCENARIO"

    /// Returns true if the app was launched with mock mode enabled
    ///
    /// This checks for the `-UITestMockMode` launch argument.
    /// Only available in DEBUG builds.
    static var isMockMode: Bool {
        #if DEBUG
            return CommandLine.arguments.contains(mockModeArgument)
        #else
            return false
        #endif
    }

    /// Returns the mock scenario specified via environment variable
    ///
    /// UI tests can set specific scenarios via launch environment:
    /// ```swift
    /// app.launchEnvironment = ["MOCK_SCENARIO": "loggedOut"]
    /// ```
    ///
    /// - Returns: The MockScenario if specified and valid, otherwise `.default`
    static var currentScenario: MockScenario {
        #if DEBUG
            guard isMockMode else { return .default }

            if let scenarioName = ProcessInfo.processInfo.environment[scenarioEnvironmentKey],
               let scenario = MockScenario(rawValue: scenarioName) {
                return scenario
            }
            return .default
        #else
            return .default
        #endif
    }

    /// Logs mock mode status for debugging
    ///
    /// Call this early in app initialization to verify mock mode detection.
    static func logStatus() {
        #if DEBUG
            if isMockMode {
                print("=== UI TEST MOCK MODE ENABLED ===")
                print("Scenario: \(currentScenario.rawValue)")
                print("Launch arguments: \(CommandLine.arguments)")
                print("================================")
            }
        #endif
    }
}

// MARK: - Mock Scenarios

/// Predefined test scenarios for UI tests
///
/// Each scenario configures the mock services with specific initial states,
/// allowing tests to start from known conditions.
///
/// ## Available Scenarios
///
/// - `default`: Logged out state, clean slate
/// - `loggedOut`: User not authenticated, shows WelcomeView
/// - `loggedInNoHistory`: Authenticated user with no test history
/// - `loggedInWithHistory`: Authenticated user with sample test results
/// - `testInProgress`: User has an active test session
/// - `loginFailure`: Login attempts will fail (for error testing)
/// - `networkError`: API calls will fail with network errors
///
/// ## Usage
///
/// ```swift
/// // In UI test
/// app.launchEnvironment = ["MOCK_SCENARIO": MockScenario.loggedInWithHistory.rawValue]
/// ```
enum MockScenario: String, CaseIterable {
    /// Default scenario: logged out, clean state
    case `default`

    /// User is not authenticated, shows WelcomeView
    case loggedOut

    /// User is authenticated but has no test history
    case loggedInNoHistory

    /// User is authenticated with sample test history
    case loggedInWithHistory

    /// User has an active test session in progress
    case testInProgress

    /// Login attempts will fail (for error handling tests)
    case loginFailure

    /// API calls will fail with network errors
    case networkError

    /// Registration will fail with network timeout
    case registrationTimeout

    /// Registration will fail with server error (500)
    case registrationServerError
}
