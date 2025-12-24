import SwiftUI
import XCTest

@testable import AIQ

/// Tests for AppRouter navigation functionality
@MainActor
final class AppRouterTests: XCTestCase {
    var sut: AppRouter!

    override func setUp() {
        super.setUp()
        sut = AppRouter()
    }

    override func tearDown() {
        sut = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        // Then
        XCTAssertTrue(sut.path.isEmpty, "path should be empty initially")
        XCTAssertTrue(sut.isAtRoot, "should be at root initially")
        XCTAssertEqual(sut.depth, 0, "depth should be 0 initially")
    }

    // MARK: - Push Navigation Tests

    func testPush_AddsRouteToPath() {
        // When
        sut.push(.testTaking)

        // Then
        XCTAssertEqual(sut.path.count, 1, "path should contain one route")
        XCTAssertFalse(sut.isAtRoot, "should not be at root after push")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
    }

    func testPush_MultipleRoutes() {
        // When
        sut.push(.testTaking)
        sut.push(.notificationSettings)
        sut.push(.help)

        // Then
        XCTAssertEqual(sut.path.count, 3, "path should contain three routes")
        XCTAssertEqual(sut.depth, 3, "depth should be 3")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    func testPush_WithAssociatedValues() {
        // Given
        let mockResult = createMockSubmittedTestResult()

        // When
        sut.push(.testResults(result: mockResult))

        // Then
        XCTAssertEqual(sut.path.count, 1, "path should contain one route")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
    }

    // MARK: - Pop Navigation Tests

    func testPop_RemovesLastRoute() {
        // Given
        sut.push(.testTaking)
        sut.push(.help)
        XCTAssertEqual(sut.path.count, 2, "setup: should have 2 routes")

        // When
        sut.pop()

        // Then
        XCTAssertEqual(sut.path.count, 1, "path should contain one route after pop")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
        XCTAssertFalse(sut.isAtRoot, "should not be at root yet")
    }

    func testPop_ToRoot() {
        // Given
        sut.push(.testTaking)
        XCTAssertEqual(sut.path.count, 1, "setup: should have 1 route")

        // When
        sut.pop()

        // Then
        XCTAssertTrue(sut.path.isEmpty, "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
        XCTAssertEqual(sut.depth, 0, "depth should be 0")
    }

    func testPop_OnEmptyPath_DoesNothing() {
        // Given - empty path
        XCTAssertTrue(sut.path.isEmpty, "setup: path should be empty")

        // When
        sut.pop()

        // Then
        XCTAssertTrue(sut.path.isEmpty, "path should still be empty")
        XCTAssertTrue(sut.isAtRoot, "should still be at root")
    }

    // MARK: - Pop to Root Tests

    func testPopToRoot_ClearsEntirePath() {
        // Given
        sut.push(.testTaking)
        sut.push(.notificationSettings)
        sut.push(.help)
        XCTAssertEqual(sut.path.count, 3, "setup: should have 3 routes")

        // When
        sut.popToRoot()

        // Then
        XCTAssertTrue(sut.path.isEmpty, "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
        XCTAssertEqual(sut.depth, 0, "depth should be 0")
    }

    func testPopToRoot_OnEmptyPath_DoesNothing() {
        // Given - empty path
        XCTAssertTrue(sut.path.isEmpty, "setup: path should be empty")

        // When
        sut.popToRoot()

        // Then
        XCTAssertTrue(sut.path.isEmpty, "path should still be empty")
        XCTAssertTrue(sut.isAtRoot, "should still be at root")
    }

    func testPopToRoot_OnSingleRoute() {
        // Given
        sut.push(.testTaking)
        XCTAssertEqual(sut.path.count, 1, "setup: should have 1 route")

        // When
        sut.popToRoot()

        // Then
        XCTAssertTrue(sut.path.isEmpty, "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
    }

    // MARK: - Direct Navigation Tests

    func testNavigateTo_SingleRoute_ReplacesStack() {
        // Given
        sut.push(.testTaking)
        sut.push(.help)
        XCTAssertEqual(sut.path.count, 2, "setup: should have 2 routes")

        // When
        sut.navigateTo(.notificationSettings)

        // Then
        XCTAssertEqual(sut.path.count, 1, "path should contain one route")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    func testNavigateTo_SingleRoute_FromEmptyStack() {
        // Given - empty path
        XCTAssertTrue(sut.path.isEmpty, "setup: path should be empty")

        // When
        sut.navigateTo(.testTaking)

        // Then
        XCTAssertEqual(sut.path.count, 1, "path should contain one route")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
    }

    func testNavigateTo_MultipleRoutes_CreatesStack() {
        // Given - empty path
        XCTAssertTrue(sut.path.isEmpty, "setup: path should be empty")

        // When
        let routes: [Route] = [.testTaking, .notificationSettings]
        sut.navigateTo(routes)

        // Then
        XCTAssertEqual(sut.path.count, 2, "path should contain two routes")
        XCTAssertEqual(sut.depth, 2, "depth should be 2")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    func testNavigateTo_MultipleRoutes_ReplacesExistingStack() {
        // Given
        sut.push(.help)
        sut.push(.registration)
        XCTAssertEqual(sut.path.count, 2, "setup: should have 2 routes")

        // When
        let routes: [Route] = [.testTaking, .notificationSettings, .help]
        sut.navigateTo(routes)

        // Then
        XCTAssertEqual(sut.path.count, 3, "path should contain three routes")
        XCTAssertEqual(sut.depth, 3, "depth should be 3")
    }

    func testNavigateTo_EmptyArray_ClearsStack() {
        // Given
        sut.push(.testTaking)
        sut.push(.help)
        XCTAssertEqual(sut.path.count, 2, "setup: should have 2 routes")

        // When
        sut.navigateTo([])

        // Then
        XCTAssertTrue(sut.path.isEmpty, "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
        XCTAssertEqual(sut.depth, 0, "depth should be 0")
    }

    // MARK: - State Query Tests

    func testIsAtRoot_WhenPathEmpty() {
        // Given - empty path
        XCTAssertTrue(sut.path.isEmpty, "setup: path should be empty")

        // Then
        XCTAssertTrue(sut.isAtRoot, "isAtRoot should be true when path is empty")
    }

    func testIsAtRoot_WhenPathNotEmpty() {
        // Given
        sut.push(.testTaking)

        // Then
        XCTAssertFalse(sut.isAtRoot, "isAtRoot should be false when path is not empty")
    }

    func testDepth_ReflectsPathCount() {
        // Given - empty path
        XCTAssertEqual(sut.depth, 0, "depth should be 0 initially")

        // When/Then - add routes and check depth
        sut.push(.testTaking)
        XCTAssertEqual(sut.depth, 1, "depth should be 1")

        sut.push(.help)
        XCTAssertEqual(sut.depth, 2, "depth should be 2")

        sut.push(.notificationSettings)
        XCTAssertEqual(sut.depth, 3, "depth should be 3")

        // Pop and check
        sut.pop()
        XCTAssertEqual(sut.depth, 2, "depth should be 2 after pop")

        sut.popToRoot()
        XCTAssertEqual(sut.depth, 0, "depth should be 0 after popToRoot")
    }

    // MARK: - Route Equality Tests

    func testRoute_Equality_SimpleRoutes() {
        // Given
        let route1 = Route.testTaking
        let route2 = Route.testTaking
        let route3 = Route.help

        // Then
        XCTAssertEqual(route1, route2, "identical routes should be equal")
        XCTAssertNotEqual(route1, route3, "different routes should not be equal")
    }

    func testRoute_Equality_RoutesWithAssociatedValues() {
        // Given
        let result1 = createMockSubmittedTestResult(sessionId: 1)
        let result2 = createMockSubmittedTestResult(sessionId: 1)
        let result3 = createMockSubmittedTestResult(sessionId: 2)

        let route1 = Route.testResults(result: result1)
        let route2 = Route.testResults(result: result2)
        let route3 = Route.testResults(result: result3)

        // Then
        XCTAssertEqual(route1, route2, "routes with same session ID should be equal")
        XCTAssertNotEqual(route1, route3, "routes with different session IDs should not be equal")
    }

    func testRoute_Equality_TestDetailRoutes() {
        // Given
        let testResult1 = createMockTestResult(id: 1)
        let testResult2 = createMockTestResult(id: 1)
        let testResult3 = createMockTestResult(id: 2)

        let route1 = Route.testDetail(result: testResult1, userAverage: 100)
        let route2 = Route.testDetail(result: testResult2, userAverage: 100)
        let route3 = Route.testDetail(result: testResult3, userAverage: 100)
        let route4 = Route.testDetail(result: testResult1, userAverage: 110)

        // Then
        XCTAssertEqual(route1, route2, "routes with same test ID and average should be equal")
        XCTAssertNotEqual(route1, route3, "routes with different test IDs should not be equal")
        XCTAssertNotEqual(route1, route4, "routes with different averages should not be equal")
    }

    // MARK: - Route Hashability Tests

    func testRoute_Hashability_SimpleRoutes() {
        // Given
        let route1 = Route.testTaking
        let route2 = Route.testTaking
        let route3 = Route.help

        // When
        let set: Set<Route> = [route1, route2, route3]

        // Then
        XCTAssertEqual(set.count, 2, "set should contain 2 unique routes")
        XCTAssertTrue(set.contains(.testTaking), "set should contain testTaking")
        XCTAssertTrue(set.contains(.help), "set should contain help")
    }

    func testRoute_Hashability_RoutesWithAssociatedValues() {
        // Given
        let result1 = createMockSubmittedTestResult(sessionId: 1)
        let result2 = createMockSubmittedTestResult(sessionId: 1)
        let result3 = createMockSubmittedTestResult(sessionId: 2)

        let route1 = Route.testResults(result: result1)
        let route2 = Route.testResults(result: result2)
        let route3 = Route.testResults(result: result3)

        // When
        let set: Set<Route> = [route1, route2, route3]

        // Then
        XCTAssertEqual(set.count, 2, "set should contain 2 unique routes")
    }

    // MARK: - Integration Tests

    func testCompleteNavigationFlow() {
        // Simulate a typical user navigation flow
        XCTAssertTrue(sut.isAtRoot, "start at root")

        // User starts a test
        sut.push(.testTaking)
        XCTAssertEqual(sut.depth, 1, "should have 1 route")

        // User completes test and views results
        let result = createMockSubmittedTestResult()
        sut.push(.testResults(result: result))
        XCTAssertEqual(sut.depth, 2, "should have 2 routes")

        // User goes back to test taking
        sut.pop()
        XCTAssertEqual(sut.depth, 1, "should have 1 route after pop")

        // User returns to dashboard
        sut.popToRoot()
        XCTAssertTrue(sut.isAtRoot, "should be at root")
    }

    func testDeepLinkNavigation() {
        // Simulate deep link to a specific test detail
        let testResult = createMockTestResult(id: 123)

        // Navigate to test detail from anywhere in the app
        sut.push(.help)
        sut.push(.notificationSettings)
        XCTAssertEqual(sut.depth, 2, "setup: should have 2 routes")

        // Deep link replaces stack
        sut.navigateTo(.testDetail(result: testResult, userAverage: 105))
        XCTAssertEqual(sut.depth, 1, "should have 1 route after deep link")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    func testDeepLinkWithHierarchy() {
        // Simulate deep link with navigation hierarchy
        // e.g., Dashboard -> Test Taking -> Results

        let result = createMockSubmittedTestResult()
        let routes: [Route] = [
            .testTaking,
            .testResults(result: result)
        ]

        sut.navigateTo(routes)

        XCTAssertEqual(sut.depth, 2, "should have 2 routes")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    // MARK: - Published Property Tests

    func testPath_IsPublished() async {
        // Given
        var publishedCount = 0
        let expectation = expectation(description: "path publishes changes")
        expectation.expectedFulfillmentCount = 2 // Initial + 1 change

        let cancellable = sut.$path.sink { _ in
            publishedCount += 1
            expectation.fulfill()
        }

        // When
        sut.push(.testTaking)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(publishedCount, 2, "path should publish initial value and change")

        cancellable.cancel()
    }

    // MARK: - Helper Methods

    /// Create a mock SubmittedTestResult for testing
    private func createMockSubmittedTestResult(sessionId: Int = 1) -> SubmittedTestResult {
        SubmittedTestResult(
            id: sessionId,
            testSessionId: sessionId,
            userId: 1,
            iqScore: 120,
            percentileRank: 91,
            totalQuestions: 30,
            correctAnswers: 26,
            accuracyPercentage: 85.0,
            completionTimeSeconds: 1800,
            completedAt: Date(),
            responseTimeFlags: nil,
            domainScores: nil,
            strongestDomain: nil,
            weakestDomain: nil,
            confidenceInterval: ConfidenceInterval(
                lower: 115,
                upper: 125,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        )
    }

    /// Create a mock TestResult for testing
    private func createMockTestResult(id: Int = 1) -> TestResult {
        TestResult(
            id: id,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            percentileRank: 80.0,
            totalQuestions: 30,
            correctAnswers: 24,
            accuracyPercentage: 80.0,
            completionTimeSeconds: 1500,
            completedAt: Date(),
            domainScores: nil,
            confidenceInterval: nil
        )
    }
}
