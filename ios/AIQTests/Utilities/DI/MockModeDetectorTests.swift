@testable import AIQ
import AIQSharedKit
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
        XCTAssertEqual(MockScenario.allCases.count, 18, "Should have exactly 18 mock scenarios")
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
        XCTAssertTrue(
            MockModeDetector.isMockMode,
            "Host-app unit test launches should use mock mode even without the UI test launch argument"
        )
    }

    func testIsUnitTestDetectedFromXCTestEnvironment() {
        XCTAssertTrue(
            MockModeDetector.isUnitTest,
            "Unit test execution should be detected from XCTest environment"
        )
    }

    // MARK: - currentScenario Tests

    func testCurrentScenarioReturnsDefaultWhenNotInMockMode() {
        // Unit tests run in mock mode by default, with no explicit scenario configured.
        let scenario = MockModeDetector.currentScenario
        XCTAssertEqual(scenario, .default, "Should return default scenario when no scenario is configured")
    }

    // MARK: - logStatus Tests

    func testLogStatusDoesNotCrash() {
        // Verify logStatus can be called without crashing
        // In unit tests, this should just be a no-op since isMockMode is false
        MockModeDetector.logStatus()
        // If we get here without crashing, the test passes
    }
}
