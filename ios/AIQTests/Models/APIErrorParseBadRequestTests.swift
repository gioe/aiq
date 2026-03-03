@testable import AIQ
import XCTest

/// Tests for APIError.parseBadRequest(_:) — covers active-session detection and the new
/// testCooldown typed case.
final class APIErrorParseBadRequestTests: XCTestCase {
    // MARK: - Helpers

    private static let sampleCooldownMessage =
        "You must wait 90 days (3 months) between tests. " +
        "Your last test was completed on 2025-12-04. " +
        "You can take your next test on 2026-03-04 " +
        "(10 days remaining)."

    // MARK: - testCooldown detection

    func testParseBadRequest_CooldownMessage_ReturnsTestCooldown() {
        let result = APIError.parseBadRequest(message: Self.sampleCooldownMessage)
        guard case let .testCooldown(nextEligibleDate, daysRemaining) = result else {
            XCTFail("Expected APIError.testCooldown, got \(result)")
            return
        }
        XCTAssertEqual(daysRemaining, 10)

        // Verify the parsed date is 2026-03-04
        let cal = Calendar(identifier: .gregorian)
        let components = cal.dateComponents([.year, .month, .day], from: nextEligibleDate)
        XCTAssertEqual(components.year, 2026)
        XCTAssertEqual(components.month, 3)
        XCTAssertEqual(components.day, 4)
    }

    func testParseBadRequest_CooldownMessage_DaysRemainingIsOne() {
        let message =
            "You must wait 90 days (3 months) between tests. " +
            "Your last test was completed on 2026-03-02. " +
            "You can take your next test on 2026-03-03 " +
            "(1 days remaining)."
        let result = APIError.parseBadRequest(message: message)
        guard case let .testCooldown(_, daysRemaining) = result else {
            XCTFail("Expected APIError.testCooldown, got \(result)")
            return
        }
        XCTAssertEqual(daysRemaining, 1)
    }

    // MARK: - Cooldown message does NOT fall through to badRequest

    func testParseBadRequest_CooldownMessage_IsNotBadRequest() {
        let result = APIError.parseBadRequest(message: Self.sampleCooldownMessage)
        if case .badRequest = result {
            XCTFail("Cooldown response must not produce APIError.badRequest")
        }
    }

    // MARK: - Non-cooldown messages still produce badRequest

    func testParseBadRequest_OtherMessage_ReturnsBadRequest() {
        let result = APIError.parseBadRequest(message: "Some unrelated error")
        guard case .badRequest = result else {
            XCTFail("Non-cooldown message should produce APIError.badRequest, got \(result)")
            return
        }
    }

    func testParseBadRequest_NilMessage_ReturnsBadRequest() {
        let result = APIError.parseBadRequest(message: nil)
        guard case .badRequest = result else {
            XCTFail("Nil message should produce APIError.badRequest, got \(result)")
            return
        }
    }

    // MARK: - Active session conflict still works

    func testParseBadRequest_ActiveSessionMessage_ReturnsActiveSessionConflict() {
        let message = "User already has an active test session (ID: 42). Please complete it first."
        let result = APIError.parseBadRequest(message: message)
        guard case let .activeSessionConflict(sessionId, _) = result else {
            XCTFail("Expected APIError.activeSessionConflict, got \(result)")
            return
        }
        XCTAssertEqual(sessionId, 42)
    }
}
