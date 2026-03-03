@testable import AIQ
import XCTest

/// Tests for DashboardScrollBody's conditional rendering logic.
///
/// DashboardScrollBody is the shared scroll container used by both dashboardContent and
/// emptyState in DashboardView. It renders InProgressTestCard only when activeTestSession
/// is non-nil. These tests verify that conditional binding by checking the stored property
/// that drives the conditional rendering decision.
@MainActor
final class DashboardScrollBodyTests: XCTestCase {
    // MARK: - InProgressTestCard Visibility

    /// Verifies that DashboardScrollBody stores a non-nil activeTestSession when one is
    /// provided, which causes InProgressTestCard to render in the view body.
    func testInProgressCard_IsShownWhenActiveTestSessionIsNonNil() {
        // Given
        let mockSession = MockDataFactory.makeInProgressSession()

        // When
        let sut = DashboardScrollBody(
            userName: "Test User",
            activeTestSession: mockSession,
            questionsAnswered: 5,
            onResume: {},
            onAbandon: {},
            onRefresh: {},
            onboardingInfoCard: { EmptyView() },
            bottomContent: { EmptyView() }
        )

        // Then - non-nil activeTestSession means the `if let activeSession` branch fires
        XCTAssertNotNil(
            sut.activeTestSession,
            "InProgressTestCard should be shown when activeTestSession is non-nil"
        )
    }

    /// Verifies that DashboardScrollBody stores a nil activeTestSession when none is
    /// provided, which causes InProgressTestCard to be omitted from the view body.
    func testInProgressCard_IsAbsentWhenActiveTestSessionIsNil() {
        // Given / When
        let sut = DashboardScrollBody(
            userName: nil,
            activeTestSession: nil,
            questionsAnswered: nil,
            onResume: {},
            onAbandon: {},
            onRefresh: {},
            onboardingInfoCard: { EmptyView() },
            bottomContent: { EmptyView() }
        )

        // Then - nil activeTestSession means the `if let activeSession` branch is skipped
        XCTAssertNil(
            sut.activeTestSession,
            "InProgressTestCard should be absent when activeTestSession is nil"
        )
    }
}
