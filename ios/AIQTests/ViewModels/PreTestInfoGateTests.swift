@testable import AIQ
import XCTest

/// Unit tests for `PreTestInfoGate.shouldShow(testCount:didSkipOnboarding:hasSeenPreTestInfo:)`.
///
/// The gate function is a pure, stateless helper — no mocks or async setup needed.
final class PreTestInfoGateTests: XCTestCase {
    // MARK: - Show Cases

    /// testCount == 0, didSkipOnboarding == false, hasSeenPreTestInfo == false → should show
    func testShouldShow_WhenNoTestsAndNotSkippedAndNotSeen() {
        let result = PreTestInfoGate.shouldShow(
            testCount: 0,
            didSkipOnboarding: false,
            hasSeenPreTestInfo: false
        )
        XCTAssertTrue(result, "Modal should show for first-time users with no tests")
    }

    /// testCount == 0, didSkipOnboarding == true, hasSeenPreTestInfo == false → should show
    func testShouldShow_WhenNoTestsAndSkippedOnboardingAndNotSeen() {
        let result = PreTestInfoGate.shouldShow(
            testCount: 0,
            didSkipOnboarding: true,
            hasSeenPreTestInfo: false
        )
        XCTAssertTrue(result, "Modal should show when user has no tests and skipped onboarding")
    }

    /// testCount > 0, didSkipOnboarding == true, hasSeenPreTestInfo == false → should show
    func testShouldShow_WhenHasTestsButSkippedOnboardingAndNotSeen() {
        let result = PreTestInfoGate.shouldShow(
            testCount: 3,
            didSkipOnboarding: true,
            hasSeenPreTestInfo: false
        )
        XCTAssertTrue(
            result,
            "Modal should show when user skipped onboarding, even if they have prior tests"
        )
    }

    // MARK: - Hide Cases

    /// testCount > 0, didSkipOnboarding == false, hasSeenPreTestInfo == false → should NOT show
    func testShouldNotShow_WhenHasTestsAndNotSkippedAndNotSeen() {
        let result = PreTestInfoGate.shouldShow(
            testCount: 5,
            didSkipOnboarding: false,
            hasSeenPreTestInfo: false
        )
        XCTAssertFalse(
            result,
            "Modal should not show for established users who did not skip onboarding"
        )
    }

    /// testCount == 0, hasSeenPreTestInfo == true → should NOT show (don't show again set)
    func testShouldNotShow_WhenHasSeenPreTestInfo() {
        let result = PreTestInfoGate.shouldShow(
            testCount: 0,
            didSkipOnboarding: false,
            hasSeenPreTestInfo: true
        )
        XCTAssertFalse(
            result,
            "Modal should not show when the 'Don't Show Again' preference has been set"
        )
    }

    /// testCount > 0, didSkipOnboarding == true, hasSeenPreTestInfo == true → should NOT show
    func testShouldNotShow_WhenSkippedOnboardingButAlreadySeen() {
        let result = PreTestInfoGate.shouldShow(
            testCount: 2,
            didSkipOnboarding: true,
            hasSeenPreTestInfo: true
        )
        XCTAssertFalse(
            result,
            "hasSeenPreTestInfo == true suppresses the modal regardless of other conditions"
        )
    }
}
