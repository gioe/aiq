@testable import AIQ
import XCTest

/// Tests for MockModeDetector functionality
final class MockModeDetectorTests: XCTestCase {
    // MARK: - Mock Scenario Tests

    func testMockScenarioAllCasesExist() {
        // Verify all expected scenarios are defined
        let allCases = MockScenario.allCases

        XCTAssertTrue(allCases.contains(.default), "Should have default scenario")
        XCTAssertTrue(allCases.contains(.loggedOut), "Should have loggedOut scenario")
        XCTAssertTrue(allCases.contains(.loggedInNoHistory), "Should have loggedInNoHistory scenario")
        XCTAssertTrue(allCases.contains(.loggedInWithHistory), "Should have loggedInWithHistory scenario")
        XCTAssertTrue(allCases.contains(.testInProgress), "Should have testInProgress scenario")
        XCTAssertTrue(allCases.contains(.loginFailure), "Should have loginFailure scenario")
        XCTAssertTrue(allCases.contains(.networkError), "Should have networkError scenario")
    }

    func testMockScenarioRawValues() {
        // Verify raw values match expected strings
        XCTAssertEqual(MockScenario.default.rawValue, "default")
        XCTAssertEqual(MockScenario.loggedOut.rawValue, "loggedOut")
        XCTAssertEqual(MockScenario.loggedInNoHistory.rawValue, "loggedInNoHistory")
        XCTAssertEqual(MockScenario.loggedInWithHistory.rawValue, "loggedInWithHistory")
        XCTAssertEqual(MockScenario.testInProgress.rawValue, "testInProgress")
        XCTAssertEqual(MockScenario.loginFailure.rawValue, "loginFailure")
        XCTAssertEqual(MockScenario.networkError.rawValue, "networkError")
    }

    func testMockScenarioInitFromValidRawValue() {
        // Verify scenarios can be initialized from raw values
        XCTAssertEqual(MockScenario(rawValue: "default"), .default)
        XCTAssertEqual(MockScenario(rawValue: "loggedOut"), .loggedOut)
        XCTAssertEqual(MockScenario(rawValue: "loggedInNoHistory"), .loggedInNoHistory)
        XCTAssertEqual(MockScenario(rawValue: "loggedInWithHistory"), .loggedInWithHistory)
        XCTAssertEqual(MockScenario(rawValue: "testInProgress"), .testInProgress)
        XCTAssertEqual(MockScenario(rawValue: "loginFailure"), .loginFailure)
        XCTAssertEqual(MockScenario(rawValue: "networkError"), .networkError)
    }

    func testMockScenarioInitFromInvalidRawValueReturnsNil() {
        // Verify invalid raw values return nil
        XCTAssertNil(MockScenario(rawValue: "invalid"))
        XCTAssertNil(MockScenario(rawValue: ""))
        XCTAssertNil(MockScenario(rawValue: "LOGGED_OUT"))
        XCTAssertNil(MockScenario(rawValue: "logged_out"))
    }

    func testMockScenarioCount() {
        // Verify the expected number of scenarios
        XCTAssertEqual(MockScenario.allCases.count, 7, "Should have exactly 7 mock scenarios")
    }

    // MARK: - MockModeDetector Constants Tests

    func testMockModeArgumentConstant() {
        XCTAssertEqual(
            MockModeDetector.mockModeArgument,
            "-UITestMockMode",
            "Mock mode argument should be -UITestMockMode"
        )
    }

    func testScenarioEnvironmentKeyConstant() {
        XCTAssertEqual(
            MockModeDetector.scenarioEnvironmentKey,
            "MOCK_SCENARIO",
            "Scenario environment key should be MOCK_SCENARIO"
        )
    }

    // MARK: - isMockMode Tests

    func testIsMockModeReturnsBooleanType() {
        // Just verify it returns a boolean - the actual value depends on launch args
        // In unit tests running without -UITestMockMode, this should be false
        let isMockMode = MockModeDetector.isMockMode
        XCTAssertFalse(isMockMode, "Should be false when not launched with mock mode argument")
    }

    // MARK: - currentScenario Tests

    func testCurrentScenarioReturnsDefaultWhenNotInMockMode() {
        // When not in mock mode, should always return default
        // This test runs in unit test environment without -UITestMockMode
        let scenario = MockModeDetector.currentScenario
        XCTAssertEqual(scenario, .default, "Should return default scenario when not in mock mode")
    }

    // MARK: - logStatus Tests

    func testLogStatusDoesNotCrash() {
        // Verify logStatus can be called without crashing
        // In unit tests, this should just be a no-op since isMockMode is false
        MockModeDetector.logStatus()
        // If we get here without crashing, the test passes
    }
}
