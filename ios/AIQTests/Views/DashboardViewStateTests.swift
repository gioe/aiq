@testable import AIQ
import XCTest

@MainActor
final class DashboardViewStateTests: XCTestCase {
    var sut: DashboardViewModel!
    var mockService: MockOpenAPIService!
    var mockAnalyticsService: MockAnalyticsService!

    override func setUp() async throws {
        try await super.setUp()
        mockService = MockOpenAPIService()
        mockAnalyticsService = MockAnalyticsService()
        sut = DashboardViewModel(apiService: mockService, analyticsService: mockAnalyticsService)

        await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
    }

    override func tearDown() async throws {
        await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
        mockService.reset()
        try await super.tearDown()
    }

    // MARK: - State 1: No Tests, No Active Test

    func testState1_NoTestsNoActiveTest_HasTestsFalse() {
        // Given
        sut.testCount = 0
        sut.activeTestSession = nil

        // Then
        XCTAssertFalse(sut.hasTests, "hasTests should be false when testCount is 0")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false when activeTestSession is nil")
    }

    func testState1_NoTestsNoActiveTest_ShowsEmptyStateBranch() {
        // Given
        sut.testCount = 0
        sut.activeTestSession = nil

        // Then
        XCTAssertFalse(sut.hasTests, "State 1: hasTests should be false")
        XCTAssertFalse(sut.hasActiveTest, "State 1: hasActiveTest should be false")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil in State 1")
    }

    func testState1_NoTestsNoActiveTest_InProgressCardNotVisible() {
        // Given
        sut.testCount = 0
        sut.activeTestSession = nil

        // Then
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false so InProgressTestCard is not shown")
    }

    // MARK: - State 2: No Tests, Active Test

    func testState2_NoTestsWithActiveTest_HasActiveTestTrue() {
        // Given
        sut.testCount = 0
        sut.activeTestSession = MockDataFactory.makeInProgressSession()

        // Then
        XCTAssertFalse(sut.hasTests, "hasTests should be false when testCount is 0")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should be true when activeTestSession is set")
    }

    func testState2_NoTestsWithActiveTest_ShowsInProgressBranch() {
        // Given
        sut.testCount = 0
        sut.activeTestSession = MockDataFactory.makeInProgressSession()

        // Then
        XCTAssertFalse(sut.hasTests, "State 2: hasTests should be false")
        XCTAssertTrue(sut.hasActiveTest, "State 2: hasActiveTest should be true")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should not be nil in State 2")
    }

    func testState2_NoTestsWithActiveTest_NoEmptyStateHeading() {
        // Given
        sut.testCount = 0
        sut.activeTestSession = MockDataFactory.makeInProgressSession()

        // Then
        XCTAssertFalse(sut.hasTests, "hasTests should be false, confirming stats grid is not shown")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should be true, confirming InProgressTestCard is shown")
    }

    // MARK: - State 3: Has Tests, No Active Test

    func testState3_HasTestsNoActiveTest_HasTestsTrue() {
        // Given
        setUpState3()

        // Then
        XCTAssertTrue(sut.hasTests, "hasTests should be true when testCount is 3")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false when activeTestSession is nil")
    }

    func testState3_HasTestsNoActiveTest_ShowsStatsBranch() {
        // Given
        setUpState3()

        // Then
        XCTAssertTrue(sut.hasTests, "State 3: hasTests should be true")
        XCTAssertFalse(sut.hasActiveTest, "State 3: hasActiveTest should be false")
        XCTAssertTrue(sut.testCount > 0, "testCount should be greater than 0 in State 3")
    }

    func testState3_HasTestsNoActiveTest_InProgressCardNotVisible() {
        // Given
        setUpState3()

        // Then
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false so InProgressTestCard is not shown")
    }

    // MARK: - State 4: Has Tests and Active Test

    func testState4_HasTestsAndActiveTest_BothFlagsTrue() {
        // Given
        setUpState4()

        // Then
        XCTAssertTrue(sut.hasTests, "hasTests should be true when testCount is 2")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should be true when activeTestSession is set")
    }

    func testState4_HasTestsAndActiveTest_ShowsFullStatsBranch() {
        // Given
        setUpState4()

        // Then
        XCTAssertTrue(sut.hasTests, "State 4: hasTests should be true")
        XCTAssertTrue(sut.hasActiveTest, "State 4: hasActiveTest should be true")
        XCTAssertTrue(sut.testCount > 0, "testCount should be greater than 0 in State 4")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should not be nil in State 4")
    }

    func testState4_HasTestsAndActiveTest_NoSecondResumeCTA() {
        // Given
        setUpState4()

        // Then - "Take Another Test" CTA branch requires hasTests && !hasActiveTest
        XCTAssertFalse(
            sut.hasTests && !sut.hasActiveTest,
            "The 'Take Another Test' CTA branch should not be entered in State 4"
        )
    }

    // MARK: - State Transition Tests

    func testTransition_State1ToState2_AddActiveTest() {
        // Given - State 1
        sut.testCount = 0
        sut.activeTestSession = nil
        XCTAssertFalse(sut.hasTests, "Pre-condition: hasTests should be false")
        XCTAssertFalse(sut.hasActiveTest, "Pre-condition: hasActiveTest should be false")

        // When
        sut.activeTestSession = MockDataFactory.makeInProgressSession()

        // Then - State 2
        XCTAssertFalse(sut.hasTests, "After transition: hasTests should remain false")
        XCTAssertTrue(sut.hasActiveTest, "After transition: hasActiveTest should be true")
    }

    func testTransition_State2ToState1_ClearActiveTest() {
        // Given - State 2
        sut.testCount = 0
        sut.activeTestSession = MockDataFactory.makeInProgressSession()
        XCTAssertFalse(sut.hasTests, "Pre-condition: hasTests should be false")
        XCTAssertTrue(sut.hasActiveTest, "Pre-condition: hasActiveTest should be true")

        // When
        sut.activeTestSession = nil

        // Then - State 1
        XCTAssertFalse(sut.hasTests, "After transition: hasTests should remain false")
        XCTAssertFalse(sut.hasActiveTest, "After transition: hasActiveTest should be false")
    }

    func testTransition_State3ToState4_AddActiveTest() {
        // Given - State 3
        setUpState3()
        XCTAssertTrue(sut.hasTests, "Pre-condition: hasTests should be true")
        XCTAssertFalse(sut.hasActiveTest, "Pre-condition: hasActiveTest should be false")

        // When
        sut.activeTestSession = MockDataFactory.makeInProgressSession()

        // Then - State 4
        XCTAssertTrue(sut.hasTests, "After transition: hasTests should remain true")
        XCTAssertTrue(sut.hasActiveTest, "After transition: hasActiveTest should be true")
    }

    func testTransition_State4ToState3_ClearActiveTest() {
        // Given - State 4
        setUpState4()
        XCTAssertTrue(sut.hasTests, "Pre-condition: hasTests should be true")
        XCTAssertTrue(sut.hasActiveTest, "Pre-condition: hasActiveTest should be true")

        // When
        sut.activeTestSession = nil

        // Then - State 3
        XCTAssertTrue(sut.hasTests, "After transition: hasTests should remain true")
        XCTAssertFalse(sut.hasActiveTest, "After transition: hasActiveTest should be false")
    }

    // MARK: - Private Helpers

    private func setUpState3() {
        sut.testCount = 3
        sut.activeTestSession = nil
    }

    private func setUpState4() {
        sut.testCount = 2
        sut.activeTestSession = MockDataFactory.makeInProgressSession()
        sut.activeSessionQuestionsAnswered = 5
    }
}
