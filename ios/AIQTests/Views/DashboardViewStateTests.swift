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
        await mockService.reset()
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
        XCTAssertTrue(!sut.hasTests && !sut.hasActiveTest, "State 1 branch condition should be true")
        XCTAssertNil(sut.latestTestResult, "latestTestResult should be nil in State 1")
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
        XCTAssertTrue(!sut.hasTests && sut.hasActiveTest, "State 2 branch condition should be true")
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
        sut.testCount = 3
        sut.latestTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
        sut.activeTestSession = nil

        // Then
        XCTAssertTrue(sut.hasTests, "hasTests should be true when testCount is 3")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false when activeTestSession is nil")
    }

    func testState3_HasTestsNoActiveTest_ShowsStatsBranch() {
        // Given
        sut.testCount = 3
        sut.latestTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
        sut.activeTestSession = nil

        // Then
        XCTAssertTrue(sut.hasTests && !sut.hasActiveTest, "State 3 branch condition should be true")
        XCTAssertTrue(sut.testCount > 0, "testCount should be greater than 0 in State 3")
        XCTAssertNotNil(sut.latestTestResult, "latestTestResult should not be nil in State 3")
    }

    func testState3_HasTestsNoActiveTest_InProgressCardNotVisible() {
        // Given
        sut.testCount = 3
        sut.latestTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
        sut.activeTestSession = nil

        // Then
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false so InProgressTestCard is not shown")
    }

    // MARK: - State 4: Has Tests and Active Test

    func testState4_HasTestsAndActiveTest_BothFlagsTrue() {
        // Given
        sut.testCount = 2
        sut.latestTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
        sut.activeTestSession = MockDataFactory.makeInProgressSession()
        sut.activeSessionQuestionsAnswered = 5

        // Then
        XCTAssertTrue(sut.hasTests, "hasTests should be true when testCount is 2")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should be true when activeTestSession is set")
    }

    func testState4_HasTestsAndActiveTest_ShowsFullStatsBranch() {
        // Given
        sut.testCount = 2
        sut.latestTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
        sut.activeTestSession = MockDataFactory.makeInProgressSession()
        sut.activeSessionQuestionsAnswered = 5

        // Then
        XCTAssertTrue(sut.hasTests && sut.hasActiveTest, "State 4 branch condition should be true")
        XCTAssertTrue(sut.testCount > 0, "testCount should be greater than 0 in State 4")
        XCTAssertNotNil(sut.latestTestResult, "latestTestResult should not be nil in State 4")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should not be nil in State 4")
    }

    func testState4_HasTestsAndActiveTest_NoSecondResumeCTA() {
        // Given
        sut.testCount = 2
        sut.latestTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
        sut.activeTestSession = MockDataFactory.makeInProgressSession()
        sut.activeSessionQuestionsAnswered = 5

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
        XCTAssertTrue(!sut.hasTests && !sut.hasActiveTest, "Pre-condition: should be in State 1")

        // When
        sut.activeTestSession = MockDataFactory.makeInProgressSession()

        // Then - State 2
        XCTAssertTrue(!sut.hasTests && sut.hasActiveTest, "Should transition to State 2 after adding active test")
    }

    func testTransition_State3ToState4_AddActiveTest() {
        // Given - State 3
        sut.testCount = 1
        sut.latestTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
        sut.activeTestSession = nil
        XCTAssertTrue(sut.hasTests && !sut.hasActiveTest, "Pre-condition: should be in State 3")

        // When
        sut.activeTestSession = MockDataFactory.makeInProgressSession()

        // Then - State 4
        XCTAssertTrue(sut.hasTests && sut.hasActiveTest, "Should transition to State 4 after adding active test")
    }
}
