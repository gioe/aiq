@testable import AIQ
import AIQSharedKit
import SwiftUI
import XCTest

/// Tests for DashboardScrollBody's structure after the 4-state refactor.
///
/// DashboardScrollBody is now a thin scroll container that renders only the
/// header, onboarding card, and caller-supplied bottomContent. InProgressTestCard
/// is no longer injected here — each call site in DashboardView owns it explicitly.
@MainActor
final class DashboardScrollBodyTests: XCTestCase {
    // MARK: - Structural Tests

    /// Verifies DashboardScrollBody can be instantiated without active-test parameters,
    /// confirming the simplified post-refactor signature compiles and initialises correctly.
    func testScrollBody_CanBeInstantiated_WithoutActiveTestParams() {
        // Given / When
        let sut = DashboardScrollBody(
            userName: "Test User",
            onRefresh: {},
            onboardingInfoCard: { EmptyView() },
            scoreSummary: { EmptyView() },
            bottomContent: { EmptyView() }
        )

        // Then - userName is stored and surfaced to the header
        XCTAssertEqual(sut.userName, "Test User")
    }

    /// Verifies DashboardScrollBody accepts a nil userName without crashing.
    func testScrollBody_AcceptsNilUserName() {
        // Given / When
        let sut = DashboardScrollBody(
            userName: nil,
            onRefresh: {},
            onboardingInfoCard: { EmptyView() },
            scoreSummary: { EmptyView() },
            bottomContent: { EmptyView() }
        )

        // Then
        XCTAssertNil(sut.userName)
    }
}
