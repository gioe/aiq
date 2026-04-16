@testable import AIQ
import XCTest

/// Unit tests for `PreTestInfoGate.shouldShow(hasSeenPreTestInfo:)`.
///
/// The gate function is a pure, stateless helper — no mocks or async setup needed.
final class PreTestInfoGateTests: XCTestCase {
    /// hasSeenPreTestInfo == false → should show
    func testShouldShow_WhenNotSeen() {
        XCTAssertTrue(
            PreTestInfoGate.shouldShow(hasSeenPreTestInfo: false),
            "Modal should show for any user who has not completed the onboarding"
        )
    }

    /// hasSeenPreTestInfo == true → should NOT show
    func testShouldNotShow_WhenAlreadySeen() {
        XCTAssertFalse(
            PreTestInfoGate.shouldShow(hasSeenPreTestInfo: true),
            "Modal should not show once the user has completed the onboarding"
        )
    }
}
