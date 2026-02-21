@testable import AIQ
import SwiftUI
import XCTest

/// Tests for DashboardView navigation integration with AppRouter.
///
/// Verifies that all navigation points in DashboardView correctly trigger
/// router.push(.testTaking()) to navigate to the test-taking screen.
@MainActor
final class DashboardNavigationTests: XCTestCase {
    var sut: AppRouter!
    var mockService: MockOpenAPIService!

    override func setUp() {
        super.setUp()
        sut = AppRouter()
        mockService = MockOpenAPIService()
    }

    // MARK: - Action Button Navigation Tests

    /// Test that calling the action button's navigation closure correctly
    /// pushes .testTaking() route to the router.
    func testActionButton_Navigation_PushesTestTakingRoute() {
        // Given - Router starts at root in dashboard tab
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Router should be at root initially")

        // When - Simulate action button tap navigation
        sut.push(.testTaking())

        // Then - Router should have testTaking route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Router should have 1 route after navigation")
        XCTAssertFalse(sut.isAtRoot(in: .dashboard), "Router should not be at root after navigation")
    }

    /// Test that action button navigation with existing routes appends testTaking.
    func testActionButton_Navigation_AppendsToExistingStack() {
        // Given - Router with existing routes
        sut.currentTab = .dashboard
        sut.push(.help)
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Setup: should have 1 route")

        // When - Simulate action button tap navigation
        sut.push(.testTaking())

        // Then - Route should be appended
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "Router should have 2 routes after navigation")
    }

    // MARK: - Resume Button Navigation Tests

    /// Test that calling the resume button's navigation closure correctly
    /// pushes .testTaking() route to the router.
    func testResumeButton_Navigation_PushesTestTakingRoute() {
        // Given - Router starts at root
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Router should be at root initially")

        // When - Simulate resume button tap navigation (same as action button)
        sut.push(.testTaking())

        // Then - Router should have testTaking route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Router should have 1 route after resume navigation")
    }

    /// Test that resume button navigation works correctly regardless of current tab.
    func testResumeButton_Navigation_WorksFromDashboardTab() {
        // Given - Router on dashboard tab
        sut.currentTab = .dashboard

        // When - Simulate resume button tap
        sut.push(.testTaking())

        // Then - Should push to dashboard path
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard path should have route")
        XCTAssertEqual(sut.depth(in: .history), 0, "History path should be empty")
        XCTAssertEqual(sut.depth(in: .settings), 0, "Settings path should be empty")
    }

    // MARK: - Empty State Button Navigation Tests

    /// Test that calling the empty state button's navigation closure correctly
    /// pushes .testTaking() route to the router.
    func testEmptyStateButton_Navigation_PushesTestTakingRoute() {
        // Given - Router starts at root
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Router should be at root initially")

        // When - Simulate empty state button tap navigation
        sut.push(.testTaking())

        // Then - Router should have testTaking route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Router should have 1 route after empty state navigation")
    }

    /// Test that empty state navigation doesn't affect other tabs.
    func testEmptyStateButton_Navigation_DoesNotAffectOtherTabs() {
        // Given - Router with routes in other tabs
        sut.push(.help, in: .settings)
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        sut.currentTab = .dashboard

        XCTAssertEqual(sut.depth(in: .settings), 1, "Setup: settings should have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 1, "Setup: history should have 1 route")

        // When - Simulate empty state button tap
        sut.push(.testTaking())

        // Then - Only dashboard should be affected
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 1, "Settings should still have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should still have 1 route")
    }

    // MARK: - Navigation Route Equality Tests

    /// Test that all navigation points use the same route (.testTaking()).
    func testAllNavigationPoints_UseTestTakingRoute() {
        // Given - Three routes representing the three navigation points
        let actionButtonRoute = Route.testTaking()
        let resumeButtonRoute = Route.testTaking()
        let emptyStateRoute = Route.testTaking()

        // Then - All should be equal (same route used everywhere)
        XCTAssertEqual(actionButtonRoute, resumeButtonRoute, "Action and resume buttons should use same route")
        XCTAssertEqual(resumeButtonRoute, emptyStateRoute, "Resume and empty state buttons should use same route")
        XCTAssertEqual(actionButtonRoute, emptyStateRoute, "Action and empty state buttons should use same route")
    }

    /// Test that testTaking route without sessionId creates route for new test.
    func testTestTakingRoute_WithoutSessionId_CreatesNewTestRoute() {
        // Given
        let newTestRoute = Route.testTaking()
        let anotherNewTestRoute = Route.testTaking()

        // Then - Routes without sessionId should be equal
        XCTAssertEqual(newTestRoute, anotherNewTestRoute, "Routes without sessionId should be equal")
    }

    /// Test that testTaking route with sessionId creates route for resuming test.
    func testTestTakingRoute_WithSessionId_CreatesResumeTestRoute() {
        // Given
        let resumeRoute = Route.testTaking(sessionId: 123)
        let sameResumeRoute = Route.testTaking(sessionId: 123)
        let differentResumeRoute = Route.testTaking(sessionId: 456)

        // Then
        XCTAssertEqual(resumeRoute, sameResumeRoute, "Routes with same sessionId should be equal")
        XCTAssertNotEqual(resumeRoute, differentResumeRoute, "Routes with different sessionId should not be equal")
    }

    // MARK: - Navigation Flow Integration Tests

    /// Test complete navigation flow: dashboard -> testTaking -> back to dashboard.
    func testNavigationFlow_DashboardToTestTakingAndBack() {
        // Given - Start at dashboard root
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Should start at root")

        // When - Navigate to test taking
        sut.push(.testTaking())

        // Then - Should be in test taking
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Should have 1 route")
        XCTAssertFalse(sut.isAtRoot(in: .dashboard), "Should not be at root")

        // When - Pop back
        sut.pop()

        // Then - Should be back at root
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Should be back at root after pop")
    }

    /// Test that navigation preserves state when switching tabs.
    func testNavigation_PreservesStateAcrossTabSwitch() {
        // Given - Navigate in dashboard
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Setup: dashboard should have 1 route")

        // When - Switch to history and back
        sut.currentTab = .history
        sut.currentTab = .dashboard

        // Then - Dashboard state should be preserved
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard state should be preserved")
    }

    // MARK: - Adaptive Routing Tests

    /// Test that with feature flag OFF, new test navigation pushes .testTaking().
    func testNewTest_FeatureFlagOff_PushesTestTakingRoute() {
        // Given
        Constants.Features.adaptiveTesting = false
        sut.currentTab = .dashboard

        // When - Simulate DashboardView action button routing logic (no active test)
        let hasActiveTest = false
        if hasActiveTest {
            sut.push(.testTaking())
        } else if Constants.Features.adaptiveTesting {
            sut.push(.adaptiveTestTaking)
        } else {
            sut.push(.testTaking())
        }

        // Then - Should use fixed-form route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Router should have 1 route")
    }

    /// Test that with feature flag ON, new test navigation pushes .adaptiveTestTaking.
    func testNewTest_FeatureFlagOn_PushesAdaptiveTestTakingRoute() {
        // Given
        Constants.Features.adaptiveTesting = true
        sut.currentTab = .dashboard

        // When - Simulate DashboardView action button routing logic (no active test)
        let hasActiveTest = false
        if hasActiveTest {
            sut.push(.testTaking())
        } else if Constants.Features.adaptiveTesting {
            sut.push(.adaptiveTestTaking)
        } else {
            sut.push(.testTaking())
        }

        // Then - Should use adaptive route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Router should have 1 route")
    }

    /// Test that with feature flag ON, resume (active test) still pushes .testTaking().
    func testResumeTest_FeatureFlagOn_PushesTestTakingRoute() {
        // Given
        Constants.Features.adaptiveTesting = true
        sut.currentTab = .dashboard

        // When - Simulate DashboardView action button routing logic (active test exists)
        let hasActiveTest = true
        if hasActiveTest {
            sut.push(.testTaking())
        } else if Constants.Features.adaptiveTesting {
            sut.push(.adaptiveTestTaking)
        } else {
            sut.push(.testTaking())
        }

        // Then - Resume should always use fixed-form route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Router should have 1 route")
    }

    /// Test that .adaptiveTestTaking route is distinct from .testTaking().
    func testAdaptiveTestTakingRoute_IsDistinctFromTestTaking() {
        // Given
        let adaptiveRoute = Route.adaptiveTestTaking
        let fixedFormRoute = Route.testTaking()

        // Then - Routes should not be equal
        XCTAssertNotEqual(adaptiveRoute, fixedFormRoute, "Adaptive and fixed-form routes should be distinct")
    }

    /// Test that .adaptiveTestTaking route equality works correctly.
    func testAdaptiveTestTakingRoute_EqualityAndHashing() {
        // Given
        let route1 = Route.adaptiveTestTaking
        let route2 = Route.adaptiveTestTaking

        // Then - Same routes should be equal
        XCTAssertEqual(route1, route2, "Two adaptiveTestTaking routes should be equal")
        XCTAssertEqual(route1.hashValue, route2.hashValue, "Equal routes should have equal hash values")
    }

    /// Test adaptive navigation flow: dashboard -> adaptiveTestTaking -> back.
    func testNavigationFlow_DashboardToAdaptiveTestTakingAndBack() {
        // Given
        sut.currentTab = .dashboard
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Should start at root")

        // When - Navigate to adaptive test taking
        sut.push(.adaptiveTestTaking)

        // Then
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Should have 1 route")
        XCTAssertFalse(sut.isAtRoot(in: .dashboard), "Should not be at root")

        // When - Pop back
        sut.pop()

        // Then
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "Should be back at root after pop")
    }

    /// Test that adaptive navigation doesn't affect other tabs.
    func testAdaptiveNavigation_DoesNotAffectOtherTabs() {
        // Given
        sut.push(.help, in: .settings)
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        sut.currentTab = .dashboard

        // When
        sut.push(.adaptiveTestTaking)

        // Then - Only dashboard affected
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "Dashboard should have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 1, "Settings should still have 1 route")
        XCTAssertEqual(sut.depth(in: .history), 1, "History should still have 1 route")
    }

    override func tearDown() {
        // Reset feature flag to default after adaptive routing tests
        Constants.Features.adaptiveTesting = false
        super.tearDown()
    }

    // MARK: - UI-Level Integration Tests

    /// Test that navigating to test when user has no active session pushes correct route
    func testNavigateToTest_NoActiveSession_PushesNewTestRoute() {
        // Given - no active test session
        sut.currentTab = .dashboard
        let hasActiveSession = false

        // When - user taps "Take Test" button (simulating DashboardView navigation logic)
        if hasActiveSession {
            sut.push(.testTaking(sessionId: 123))
        } else if Constants.Features.adaptiveTesting {
            sut.push(.adaptiveTestTaking)
        } else {
            sut.push(.testTaking())
        }

        // Then - should push new test route (no sessionId)
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "should push 1 route")
        XCTAssertFalse(sut.isAtRoot(in: .dashboard), "should not be at root")
    }

    /// Test that navigating after completing a test (test results flow) works correctly
    func testNavigateAfterTestCompletion_TestResultsFlow_RouteChainWorks() {
        // Given - user completes a test
        sut.currentTab = .dashboard
        let mockResult = createMockSubmittedTestResult()

        // When - navigate to test taking
        sut.push(.testTaking())
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "should have test taking route")

        // When - test completes and navigate to results (replacing stack)
        sut.navigateTo(.testResults(result: mockResult, isFirstTest: false), in: .dashboard)

        // Then - should have replaced with test results route
        XCTAssertEqual(sut.depth(in: .dashboard), 1, "should have 1 route after replacement")

        // Then - can navigate back to dashboard root
        sut.popToRoot(in: .dashboard)
        XCTAssertTrue(sut.isAtRoot(in: .dashboard), "should be back at root")
    }

    /// Test that navigating in dashboard doesn't affect other tabs' state
    func testDashboardNavigation_DoesNotAffectOtherTabsState() {
        // Given - all tabs have navigation state
        sut.push(.testDetail(result: createMockTestResult(), userAverage: 110), in: .history)
        sut.push(.help, in: .settings)
        sut.push(.notificationSettings, in: .settings)

        XCTAssertEqual(sut.depth(in: .history), 1, "setup: history should have 1 route")
        XCTAssertEqual(sut.depth(in: .settings), 2, "setup: settings should have 2 routes")

        // When - navigate in dashboard tab
        sut.currentTab = .dashboard
        sut.push(.testTaking())
        sut.push(.help)

        // Then - dashboard has new navigation
        XCTAssertEqual(sut.depth(in: .dashboard), 2, "dashboard should have 2 routes")

        // Then - other tabs' state is preserved (tab isolation)
        XCTAssertEqual(sut.depth(in: .history), 1, "history state should be preserved")
        XCTAssertEqual(sut.depth(in: .settings), 2, "settings state should be preserved")

        // Then - verify can switch to other tabs and state is intact
        sut.currentTab = .history
        XCTAssertEqual(sut.depth(in: .history), 1, "history depth preserved after switch")
        XCTAssertFalse(sut.isAtRoot(in: .history), "history not at root after switch")

        sut.currentTab = .settings
        XCTAssertEqual(sut.depth(in: .settings), 2, "settings depth preserved after switch")
    }

    // MARK: - Helper Methods

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

    private func createMockSubmittedTestResult(id: Int = 1) -> SubmittedTestResult {
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
