@testable import AIQ
import XCTest

final class OAuthSignInButtonsTests: XCTestCase {
    func testWelcomePlacementUsesWelcomeAccessibilityIdentifiers() {
        let identifiers = OAuthSignInButtons.Placement.welcome.identifiers

        XCTAssertEqual(identifiers.apple, AccessibilityIdentifiers.WelcomeView.signInWithAppleButton)
        XCTAssertEqual(identifiers.google, AccessibilityIdentifiers.WelcomeView.signInWithGoogleButton)
    }

    func testGuestResultsPlacementUsesGuestAccessibilityIdentifiers() {
        let identifiers = OAuthSignInButtons.Placement.guestResults.identifiers

        XCTAssertEqual(
            identifiers.apple,
            AccessibilityIdentifiers.GuestTestContainerView.signInWithAppleButton
        )
        XCTAssertEqual(
            identifiers.google,
            AccessibilityIdentifiers.GuestTestContainerView.signInWithGoogleButton
        )
    }
}
