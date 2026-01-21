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
        // Then - All tab paths should be empty initially
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "dashboard should be at root initially")
        XCTAssertTrue(sut.isAtRoot(in: .history), "history should be at root initially")
        XCTAssertTrue(sut.isAtRoot(in: .settings), "settings should be at root initially")
        XCTAssertEqual(sut.depth(in: .dashboard), 0, "dashboard depth should be 0 initially")
        XCTAssertEqual(sut.depth(in: .history), 0, "history depth should be 0 initially")
        XCTAssertEqual(sut.depth(in: .settings), 0, "settings depth should be 0 initially")
    }

    // MARK: - Push Navigation Tests

    func testPush_AddsRouteToPath() {
        // Given - currentTab is dashboard
        sut.currentTab = .dashboard

        // When
        sut.push(.testTaking())

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "dashboard path should contain one route")
        XCTAssertFalse(sut.isAtRoot(in: .dashboard), "dashboard should not be at root after push")
        XCTAssertEqual(sut.depth, 1, "current tab depth should be 1")
    }

    func testPush_MultipleRoutes() {
        // Given - currentTab is dashboard
        sut.currentTab = .dashboard

        // When
        sut.push(.testTaking())
        sut.push(.notificationSettings)
        sut.push(.help)

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 3, "dashboard path should contain three routes")
        XCTAssertEqual(sut.depth, 3, "current tab depth should be 3")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    func testPush_WithAssociatedValues() {
        // Given
        sut.currentTab = .dashboard
        let mockResult = createMockSubmittedTestResult()

        // When
        sut.push(.testResults(result: mockResult))

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "dashboard path should contain one route")
        XCTAssertEqual(sut.depth, 1, "current tab depth should be 1")
    }

    // MARK: - Pop Navigation Tests

    func testPop_RemovesLastRoute() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        sut.push(.help)
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "setup: should have 2 routes")

        // When
        sut.pop()

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "path should contain one route after pop")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
        XCTAssertFalse(sut.isAtRoot, "should not be at root yet")
    }

    func testPop_ToRoot() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "setup: should have 1 route")

        // When
        sut.pop()

        // Then
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
        XCTAssertEqual(sut.depth, 0, "depth should be 0")
    }

    func testPop_OnEmptyPath_DoesNothing() {
        // Given - empty path
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "setup: path should be empty")

        // When
        sut.pop()

        // Then
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "path should still be empty")
        XCTAssertTrue(sut.isAtRoot, "should still be at root")
    }

    // MARK: - Pop to Root Tests

    func testPopToRoot_ClearsEntirePath() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        sut.push(.notificationSettings)
        sut.push(.help)
        XCTAssertEqual(sut.depth(in: .dashboard), 3, "setup: should have 3 routes")

        // When
        sut.popToRoot()

        // Then
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
        XCTAssertEqual(sut.depth, 0, "depth should be 0")
    }

    func testPopToRoot_OnEmptyPath_DoesNothing() {
        // Given - empty path
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "setup: path should be empty")

        // When
        sut.popToRoot()

        // Then
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "path should still be empty")
        XCTAssertTrue(sut.isAtRoot, "should still be at root")
    }

    func testPopToRoot_OnSingleRoute() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "setup: should have 1 route")

        // When
        sut.popToRoot()

        // Then
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
    }

    // MARK: - Direct Navigation Tests

    func testNavigateTo_SingleRoute_ReplacesStack() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        sut.push(.help)
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "setup: should have 2 routes")

        // When
        sut.navigateTo(.notificationSettings)

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "path should contain one route")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    func testNavigateTo_SingleRoute_FromEmptyStack() {
        // Given - empty path
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "setup: path should be empty")

        // When
        sut.navigateTo(.testTaking())

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "path should contain one route")
        XCTAssertEqual(sut.depth, 1, "depth should be 1")
    }

    func testNavigateTo_MultipleRoutes_CreatesStack() {
        // Given - empty path
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "setup: path should be empty")

        // When
        let routes: [Route] = [.testTaking(), .notificationSettings]
        sut.navigateTo(routes)

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "path should contain two routes")
        XCTAssertEqual(sut.depth, 2, "depth should be 2")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    func testNavigateTo_MultipleRoutes_ReplacesExistingStack() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.help)
        sut.push(.registration)
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "setup: should have 2 routes")

        // When
        let routes: [Route] = [.testTaking(), .notificationSettings, .help]
        sut.navigateTo(routes)

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 3, "path should contain three routes")
        XCTAssertEqual(sut.depth, 3, "depth should be 3")
    }

    func testNavigateTo_EmptyArray_ClearsStack() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        sut.push(.help)
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "setup: should have 2 routes")

        // When
        sut.navigateTo([])

        // Then
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "path should be empty")
        XCTAssertTrue(sut.isAtRoot, "should be at root")
        XCTAssertEqual(sut.depth, 0, "depth should be 0")
    }

    // MARK: - State Query Tests

    func testIsAtRoot_WhenPathEmpty() {
        // Given - empty path
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "setup: path should be empty")

        // Then
        XCTAssertTrue(sut.isAtRoot, "isAtRoot should be true when path is empty")
    }

    func testIsAtRoot_WhenPathNotEmpty() {
        // Given
        sut.currentTab = .dashboard
        sut.push(.testTaking())

        // Then
        XCTAssertFalse(sut.isAtRoot, "isAtRoot should be false when path is not empty")
    }

    func testDepth_ReflectsPathCount() {
        // Given - empty path
        sut.currentTab = .dashboard
        XCTAssertEqual(sut.depth, 0, "depth should be 0 initially")

        // When/Then - add routes and check depth
        sut.push(.testTaking())
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
        let route1 = Route.testTaking()
        let route2 = Route.testTaking()
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
        let route1 = Route.testTaking()
        let route2 = Route.testTaking()
        let route3 = Route.help

        // When
        let set: Set<Route> = [route1, route2, route3]

        // Then
        XCTAssertEqual(set.count, 2, "set should contain 2 unique routes")
        XCTAssertTrue(set.contains(.testTaking()), "set should contain testTaking")
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
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot, "start at root")

        // User starts a test
        sut.push(.testTaking())
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
        sut.currentTab = .dashboard
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

        sut.currentTab = .dashboard
        let result = createMockSubmittedTestResult()
        let routes: [Route] = [
            .testTaking(),
            .testResults(result: result)
        ]

        sut.navigateTo(routes)

        XCTAssertEqual(sut.depth, 2, "should have 2 routes")
        XCTAssertFalse(sut.isAtRoot, "should not be at root")
    }

    // MARK: - Per-Tab Navigation Tests

    func testPerTabPaths_AreIndependent() {
        // When - Push routes to different tabs
        sut.push(.testTaking(), in: .dashboard)
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        sut.push(.help, in: .settings)

        // Then - Each tab should have its own route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 1, "Settings should have 1 route")

        // Verify each tab is independent
        XCTAssertFalse(sut.isAtRoot(in: .dashboard), "Dashboard should not be at root")
        XCTAssertFalse(sut.isAtRoot(in: .history), "History should not be at root")
        XCTAssertFalse(sut.isAtRoot(in: .settings), "Settings should not be at root")
    }

    func testPushToDashboard_DoesNotAffectHistory() {
        // Given - Both tabs at root
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "setup: dashboard should be at root")
        XCTAssertTrue(sut.isAtRoot(in: .history), "setup: history should be at root")

        // When - Push to dashboard
        sut.push(.testTaking(), in: .dashboard)

        // Then - Dashboard has route, history still at root
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 0, "History should still be at root")
        XCTAssertTrue(sut.isAtRoot(in: .history), "History should remain at root")
    }

    func testPushToHistory_DoesNotAffectSettings() {
        // Given - Both tabs at root
        XCTAssertTrue(sut.isAtRoot(in: .history), "setup: history should be at root")
        XCTAssertTrue(sut.isAtRoot(in: .settings), "setup: settings should be at root")

        // When - Push to history
        let testResult = createMockTestResult()
        sut.push(.testDetail(result: testResult, userAverage: 105), in: .history)

        // Then - History has route, settings still at root
        XCTAssertEqual(sut.depth(in: .history), 1, "History should have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 0, "Settings should still be at root")
        XCTAssertTrue(sut.isAtRoot(in: .settings), "Settings should remain at root")
    }

    func testPopToRootInOneTab_DoesNotAffectOtherTabs() {
        // Given - All tabs have routes
        sut.push(.testTaking(), in: .dashboard)
        sut.push(.testTaking(), in: .dashboard)
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        sut.push(.help, in: .settings)

        XCTAssertEqual(sut.depth(in: .dashboard), 2, "setup: dashboard should have 2 routes")
        XCTAssertEqual(sut.depth(in: .history), 1, "setup: history should have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 1, "setup: settings should have 1 route")

        // When - Pop dashboard to root
        sut.popToRoot(in: .dashboard)

        // Then - Dashboard at root, other tabs unchanged
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Dashboard should be at root")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should still have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 1, "Settings should still have 1 route")
    }

    func testCurrentTabNavigation_TargetsCorrectTab() {
        // Given - Current tab is dashboard
        sut.currentTab = .dashboard

        // When - Push without specifying tab
        sut.push(.testTaking())

        // Then - Should push to dashboard
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 0, "History should be at root")
        XCTAssertEqual(sut.depth(in: .settings), 0, "Settings should be at root")
    }

    func testSwitchingCurrentTab_UpdatesNavigationContext() {
        // Given - Start with dashboard
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")

        // When - Switch to history and push
        sut.currentTab = .history
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100))

        // Then - History should have the route, not dashboard
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should still have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should have 1 route")
    }

    func testNavigateTo_WithTab_TargetsSpecificTab() {
        // Given - Dashboard has some routes
        sut.push(.testTaking(), in: .dashboard)
        sut.push(.help, in: .dashboard)
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "setup: dashboard should have 2 routes")

        // When - Navigate to history with specific route
        let testResult = createMockTestResult()
        sut.navigateTo(.testDetail(result: testResult, userAverage: 105), in: .history)

        // Then - History has new route, dashboard cleared
        XCTAssertEqual(sut.depth(in: .history), 1, "History should have 1 route")
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "Dashboard should still have 2 routes")
    }

    func testBinding_ReturnsCorrectPathForTab() {
        // Given - Push routes to different tabs
        sut.push(.testTaking(), in: .dashboard)
        sut.push(.help, in: .settings)

        // When - Get bindings
        let dashboardBinding = sut.binding(for: .dashboard)
        let historyBinding = sut.binding(for: .history)
        let settingsBinding = sut.binding(for: .settings)

        // Then - Bindings reflect correct state
        XCTAssertEqual(dashboardBinding.wrappedValue.count, 1, "Dashboard binding should have 1 route")
        XCTAssertEqual(historyBinding.wrappedValue.count, 0, "History binding should be empty")
        XCTAssertEqual(settingsBinding.wrappedValue.count, 1, "Settings binding should have 1 route")
    }

    func testBinding_ModifiesCorrectPath() {
        // Given - Get binding for dashboard
        let dashboardBinding = sut.binding(for: .dashboard)

        // When - Modify binding by appending a route
        var modifiedPath = dashboardBinding.wrappedValue
        modifiedPath.append(Route.testTaking())
        dashboardBinding.wrappedValue = modifiedPath

        // Then - Dashboard path should be updated
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 0, "History should still be at root")
    }

    func testMultipleRoutesInDifferentTabs_PreserveState() {
        // Given - Complex navigation state across tabs
        sut.push(.testTaking(), in: .dashboard)
        let testResult = createMockSubmittedTestResult()
        sut.push(.testResults(result: testResult), in: .dashboard)

        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)

        sut.push(.notificationSettings, in: .settings)
        sut.push(.help, in: .settings)

        // Then - All tabs preserve their state
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "Dashboard should have 2 routes")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 2, "Settings should have 2 routes")

        // When - Pop from one tab
        sut.pop(from: .settings)

        // Then - Only that tab is affected
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "Dashboard should still have 2 routes")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should still have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 1, "Settings should now have 1 route")
    }

    // MARK: - Deep Link with Tab Tests

    func testDeepLink_ToSpecificTab_ClearsOnlyThatTab() {
        // Given - All tabs have routes
        sut.push(.testTaking(), in: .dashboard)
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        sut.push(.help, in: .settings)

        // When - Deep link to dashboard
        sut.navigateTo(.testResults(result: createMockSubmittedTestResult()), in: .dashboard)

        // Then - Dashboard has new route, others unchanged
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should have 1 route after deep link")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should still have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 1, "Settings should still have 1 route")
    }

    func testDeepLink_WithMultipleRoutes_ToSpecificTab() {
        // Given - Empty state
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "setup: dashboard should be at root")

        // When - Deep link with hierarchy to dashboard
        let routes: [Route] = [
            .testTaking(),
            .testResults(result: createMockSubmittedTestResult())
        ]
        sut.navigateTo(routes, in: .dashboard)

        // Then - Dashboard has hierarchy, other tabs unaffected
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "Dashboard should have 2 routes")
        XCTAssertTrue(sut.isAtRoot(in: .history), "History should be at root")
        XCTAssertTrue(sut.isAtRoot(in: .settings), "Settings should be at root")
    }

    func testTabSwitching_PreservesNavigationState() {
        // Simulate user flow: navigate in dashboard, switch to history, switch back

        // When - Navigate in dashboard
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        sut.push(.testResults(result: createMockSubmittedTestResult()))
        XCTAssertEqual(sut.depth, 2, "Dashboard should have 2 routes")

        // When - Switch to history and navigate
        sut.currentTab = .history
        XCTAssertEqual(sut.depth, 0, "History should be at root initially")
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100))
        XCTAssertEqual(sut.depth, 1, "History should have 1 route")

        // When - Switch back to dashboard
        sut.currentTab = .dashboard

        // Then - Dashboard state preserved
        XCTAssertEqual(sut.depth, 2, "Dashboard should still have 2 routes")
    }

    // MARK: - Helper Methods

    /// Create a mock SubmittedTestResult for testing
    private func createMockSubmittedTestResult(sessionId: Int = 1) -> SubmittedTestResult {
        MockDataFactory.makeTestResult(
            id: sessionId,
            testSessionId: sessionId,
            userId: 1,
            iqScore: 120,
            totalQuestions: 30,
            correctAnswers: 26,
            accuracyPercentage: 85.0,
            completedAt: Date()
        )
    }

    /// Create a mock TestResult for testing
    private func createMockTestResult(id: Int = 1) -> TestResult {
        MockDataFactory.makeTestResult(
            id: id,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 30,
            correctAnswers: 24,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
    }
}
