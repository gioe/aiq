import Foundation

/// Stateless gate for determining whether the pre-test onboarding should be shown.
///
/// Extracted from the deprecated `PreTestInfoView` — the gate logic is still used
/// by `DashboardView` and `PreTestOnboardingContainerView`.
enum PreTestInfoGate {
    /// Returns `true` when the pre-test onboarding should be displayed.
    ///
    /// The flow is suppressed if the user has previously completed it
    /// (`hasSeenPreTestInfo == true`). Otherwise it shows for:
    /// - First-time users with no completed tests (`testCount == 0`), or
    /// - Users who skipped the onboarding flow (`didSkipOnboarding == true`).
    static func shouldShow(
        testCount: Int,
        didSkipOnboarding: Bool,
        hasSeenPreTestInfo: Bool
    ) -> Bool {
        !hasSeenPreTestInfo && (testCount == 0 || didSkipOnboarding)
    }
}
