import SwiftUI

/// Encapsulates the three timer-lifecycle .onChange handlers shared by
/// TestTakingView and AdaptiveTestView:
///   1. timerManager.showWarning  → raise the warning banner
///   2. isTestCompleted           → stop the timer
///   3. timerManager.hasExpired   → call onExpire
struct TestTimerModifier: ViewModifier {
    @ObservedObject var timerManager: TestTimerManager
    let isTestCompleted: Bool
    @Binding var showTimeWarningBanner: Bool
    @Binding var warningBannerDismissed: Bool
    let onExpire: () -> Void

    func body(content: Content) -> some View {
        content
            .onChange(of: timerManager.showWarning) { showWarning in
                // Show warning banner when timer hits 5 minutes (unless already dismissed)
                if showWarning && !warningBannerDismissed {
                    showTimeWarningBanner = true
                }
            }
            .onChange(of: isTestCompleted) { completed in
                // Stop timer when test is completed
                if completed {
                    timerManager.stop()
                }
            }
            .onChange(of: timerManager.hasExpired) { expired in
                // Handle timer expiration during test-taking
                if expired && !isTestCompleted {
                    onExpire()
                }
            }
    }
}
