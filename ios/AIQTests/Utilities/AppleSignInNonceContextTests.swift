@testable import AIQ
import AuthenticationServices
import XCTest

final class AppleSignInNonceContextTests: XCTestCase {
    func testPrepareStoresRawNonceAndHashesRequestNonce() {
        var context = AppleSignInNonceContext()
        let request = ASAuthorizationAppleIDProvider().createRequest()

        context.prepare(request)

        let rawNonce = context.rawNonce
        XCTAssertEqual(rawNonce?.count, 32)
        XCTAssertEqual(request.requestedScopes, [.email])
        XCTAssertEqual(request.nonce, rawNonce.map(AppleSignInNonceContext.sha256))
        XCTAssertNotEqual(request.nonce, rawNonce)
    }

    func testConsumeRawNonceClearsStoredNonce() {
        var context = AppleSignInNonceContext()
        let request = ASAuthorizationAppleIDProvider().createRequest()
        context.prepare(request)

        let rawNonce = context.rawNonce

        XCTAssertEqual(context.consumeRawNonce(), rawNonce)
        XCTAssertNil(context.rawNonce)
        XCTAssertNil(context.consumeRawNonce())
    }

    func testClearRemovesStoredNonce() {
        var context = AppleSignInNonceContext()
        let request = ASAuthorizationAppleIDProvider().createRequest()
        context.prepare(request)

        context.clear()

        XCTAssertNil(context.rawNonce)
    }

    func testSHA256MatchesKnownDigest() {
        XCTAssertEqual(
            AppleSignInNonceContext.sha256("raw.nonce"),
            "f6044ccc4f348585d4b519ff1c06416850d681d4d4bd7d965c3c9182627ff5cc" // pragma: allowlist secret
        )
    }
}
