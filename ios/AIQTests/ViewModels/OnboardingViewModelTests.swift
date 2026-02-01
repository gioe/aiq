@testable import AIQ
import XCTest

@MainActor
final class OnboardingViewModelTests: XCTestCase {
    var sut: OnboardingViewModel!

    override func setUp() {
        super.setUp()
        // Reset UserDefaults for testing
        UserDefaults.standard.removeObject(forKey: "hasCompletedOnboarding")
        sut = OnboardingViewModel()
    }

    override func tearDown() {
        UserDefaults.standard.removeObject(forKey: "hasCompletedOnboarding")
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialState_DefaultValues() {
        // Then
        XCTAssertEqual(sut.currentPage, 0, "currentPage should start at 0")
        XCTAssertFalse(sut.hasCompletedOnboarding, "hasCompletedOnboarding should be false initially")
    }

    // MARK: - Computed Properties Tests

    func testShouldShowSkip_Page0_ReturnsTrue() {
        // Given
        sut.currentPage = 0

        // When
        let shouldShowSkip = sut.shouldShowSkip

        // Then
        XCTAssertTrue(shouldShowSkip, "shouldShowSkip should be true on page 0")
    }

    func testShouldShowSkip_Page1_ReturnsTrue() {
        // Given
        sut.currentPage = 1

        // When
        let shouldShowSkip = sut.shouldShowSkip

        // Then
        XCTAssertTrue(shouldShowSkip, "shouldShowSkip should be true on page 1")
    }

    func testShouldShowSkip_Page2_ReturnsTrue() {
        // Given
        sut.currentPage = 2

        // When
        let shouldShowSkip = sut.shouldShowSkip

        // Then
        XCTAssertTrue(shouldShowSkip, "shouldShowSkip should be true on page 2")
    }

    func testShouldShowSkip_Page3_ReturnsFalse() {
        // Given
        sut.currentPage = 3

        // When
        let shouldShowSkip = sut.shouldShowSkip

        // Then
        XCTAssertFalse(shouldShowSkip, "shouldShowSkip should be false on page 3 (last page)")
    }

    func testIsLastPage_Page0_ReturnsFalse() {
        // Given
        sut.currentPage = 0

        // When
        let isLastPage = sut.isLastPage

        // Then
        XCTAssertFalse(isLastPage, "isLastPage should be false on page 0")
    }

    func testIsLastPage_Page1_ReturnsFalse() {
        // Given
        sut.currentPage = 1

        // When
        let isLastPage = sut.isLastPage

        // Then
        XCTAssertFalse(isLastPage, "isLastPage should be false on page 1")
    }

    func testIsLastPage_Page2_ReturnsFalse() {
        // Given
        sut.currentPage = 2

        // When
        let isLastPage = sut.isLastPage

        // Then
        XCTAssertFalse(isLastPage, "isLastPage should be false on page 2")
    }

    func testIsLastPage_Page3_ReturnsTrue() {
        // Given
        sut.currentPage = 3

        // When
        let isLastPage = sut.isLastPage

        // Then
        XCTAssertTrue(isLastPage, "isLastPage should be true on page 3")
    }

    // MARK: - Navigation Tests

    func testNextPage_FromPage0_IncrementsToPage1() {
        // Given
        sut.currentPage = 0

        // When
        sut.nextPage()

        // Then
        XCTAssertEqual(sut.currentPage, 1, "nextPage should increment from 0 to 1")
    }

    func testNextPage_FromPage1_IncrementsToPage2() {
        // Given
        sut.currentPage = 1

        // When
        sut.nextPage()

        // Then
        XCTAssertEqual(sut.currentPage, 2, "nextPage should increment from 1 to 2")
    }

    func testNextPage_FromPage2_IncrementsToPage3() {
        // Given
        sut.currentPage = 2

        // When
        sut.nextPage()

        // Then
        XCTAssertEqual(sut.currentPage, 3, "nextPage should increment from 2 to 3")
    }

    func testNextPage_FromPage3_StaysAtPage3() {
        // Given
        sut.currentPage = 3

        // When
        sut.nextPage()

        // Then
        XCTAssertEqual(sut.currentPage, 3, "nextPage should not increment beyond page 3")
    }

    func testNextPage_MultipleCallsFromPage0_AdvancesToPage3() {
        // Given
        sut.currentPage = 0

        // When
        sut.nextPage()
        sut.nextPage()
        sut.nextPage()

        // Then
        XCTAssertEqual(sut.currentPage, 3, "Multiple nextPage calls should advance to page 3")
    }

    func testNextPage_BeyondLastPage_DoesNotOverflow() {
        // Given
        sut.currentPage = 3

        // When - Try to advance multiple times beyond last page
        sut.nextPage()
        sut.nextPage()
        sut.nextPage()

        // Then
        XCTAssertEqual(sut.currentPage, 3, "currentPage should stay at 3 even with multiple calls")
    }

    // MARK: - Completion Tests

    func testCompleteOnboarding_SetsHasCompletedOnboardingToTrue() {
        // Given
        XCTAssertFalse(sut.hasCompletedOnboarding, "Precondition: should start as false")

        // When
        sut.completeOnboarding()

        // Then
        XCTAssertTrue(sut.hasCompletedOnboarding, "completeOnboarding should set hasCompletedOnboarding to true")
    }

    func testSkipOnboarding_SetsHasCompletedOnboardingToTrue() {
        // Given
        XCTAssertFalse(sut.hasCompletedOnboarding, "Precondition: should start as false")

        // When
        sut.skipOnboarding()

        // Then
        XCTAssertTrue(sut.hasCompletedOnboarding, "skipOnboarding should set hasCompletedOnboarding to true")
    }

    func testCompleteOnboarding_CalledMultipleTimes_RemainsTrue() {
        // When
        sut.completeOnboarding()
        sut.completeOnboarding()
        sut.completeOnboarding()

        // Then
        XCTAssertTrue(sut.hasCompletedOnboarding, "Multiple calls should keep hasCompletedOnboarding as true")
    }

    // MARK: - AppStorage Persistence Tests

    func testAppStorage_PersistsCompletionState() {
        // Given
        XCTAssertFalse(sut.hasCompletedOnboarding, "Precondition: should start as false")

        // When
        sut.completeOnboarding()

        // Then - Create new instance to verify persistence
        let newViewModel = OnboardingViewModel()
        XCTAssertTrue(newViewModel.hasCompletedOnboarding, "hasCompletedOnboarding should be persisted via @AppStorage")
    }

    func testAppStorage_DefaultValueWhenNotSet() {
        // Given - Clean UserDefaults
        UserDefaults.standard.removeObject(forKey: "hasCompletedOnboarding")

        // When - Create fresh instance
        let freshViewModel = OnboardingViewModel()

        // Then
        XCTAssertFalse(freshViewModel.hasCompletedOnboarding, "hasCompletedOnboarding should default to false")
    }

    func testAppStorage_SkipOnboardingPersistsState() {
        // Given
        XCTAssertFalse(sut.hasCompletedOnboarding, "Precondition: should start as false")

        // When
        sut.skipOnboarding()

        // Then - Create new instance to verify persistence
        let newViewModel = OnboardingViewModel()
        XCTAssertTrue(newViewModel.hasCompletedOnboarding, "skipOnboarding should persist via @AppStorage")
    }

    // MARK: - Integration Tests

    func testFullOnboardingFlow_NavigateToLastPageAndComplete() {
        // Given
        XCTAssertEqual(sut.currentPage, 0, "Start at page 0")
        XCTAssertTrue(sut.shouldShowSkip, "Should show skip initially")
        XCTAssertFalse(sut.isLastPage, "Should not be last page initially")

        // When - Navigate through all pages
        sut.nextPage()
        XCTAssertEqual(sut.currentPage, 1)
        XCTAssertTrue(sut.shouldShowSkip)
        XCTAssertFalse(sut.isLastPage)

        sut.nextPage()
        XCTAssertEqual(sut.currentPage, 2)
        XCTAssertTrue(sut.shouldShowSkip)
        XCTAssertFalse(sut.isLastPage)

        sut.nextPage()
        XCTAssertEqual(sut.currentPage, 3)
        XCTAssertFalse(sut.shouldShowSkip, "Should not show skip on last page")
        XCTAssertTrue(sut.isLastPage, "Should be last page")

        // Then - Complete onboarding
        sut.completeOnboarding()
        XCTAssertTrue(sut.hasCompletedOnboarding)
    }

    func testSkipFlow_FromAnyPage_CompletesOnboarding() {
        // Given
        sut.currentPage = 1

        // When
        sut.skipOnboarding()

        // Then
        XCTAssertTrue(sut.hasCompletedOnboarding, "Skip should complete onboarding from any page")
    }

    // MARK: - Edge Cases

    func testNextPage_WithManualPageSet_HandlesCorrectly() {
        // Given - Manually set page to 2
        sut.currentPage = 2

        // When
        sut.nextPage()

        // Then
        XCTAssertEqual(sut.currentPage, 3, "nextPage should work correctly even when page is manually set")
    }

    func testComputedProperties_UpdateWhenPageChanges() {
        // Given
        sut.currentPage = 0
        XCTAssertTrue(sut.shouldShowSkip)
        XCTAssertFalse(sut.isLastPage)

        // When - Change to last page
        sut.currentPage = 3

        // Then - Computed properties should update
        XCTAssertFalse(sut.shouldShowSkip, "shouldShowSkip should update when page changes")
        XCTAssertTrue(sut.isLastPage, "isLastPage should update when page changes")
    }

    // MARK: - Thread Safety Tests (MainActor)

    func testViewModel_IsMainActorIsolated() async {
        // Given - ViewModel should be @MainActor
        // When - Access properties on main actor
        await MainActor.run {
            XCTAssertEqual(sut.currentPage, 0)
            sut.nextPage()
            XCTAssertEqual(sut.currentPage, 1)
        }

        // Then - No crashes or issues
    }
}
