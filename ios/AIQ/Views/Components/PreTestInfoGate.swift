import Foundation

/// Stateless gate for determining whether the pre-test onboarding should be shown.
///
/// Extracted from the deprecated `PreTestInfoView` — the gate logic is still used
/// by `DashboardView` and `PreTestOnboardingContainerView`.
enum PreTestInfoGate {
    /// Returns `true` when the pre-test onboarding should be displayed.
    ///
    /// Shown once per user: any user who has not yet completed the onboarding
    /// (`hasSeenPreTestInfo == false`) sees it before their first test attempt.
    static func shouldShow(hasSeenPreTestInfo: Bool) -> Bool {
        !hasSeenPreTestInfo
    }
}
