@testable import AIQ
import XCTest

/// Unit tests for the cooldown state introduced by TASK-1347.
///
/// Covers:
/// 1. `handleTestStartError(.testCooldown(...))` populates `testCooldownInfo` with the
///    correct date and days-remaining value.
/// 2. The same call sets `isLoading` to false and leaves `error` nil (i.e., it does NOT
///    call `handleError`).
/// 3. The ViewModel state satisfies all conditions that `TestTakingView.shouldShowLoadFailure`
///    evaluates when a cooldown error is received: not loading, no questions, `testCooldownInfo`
///    non-nil, and `isActiveSessionConflict` false — even when `error` is nil.
@MainActor
final class TestTakingViewModelCooldownTests: XCTestCase {
    var sut: TestTakingViewModel!
    var mockService: MockOpenAPIService!
    var mockAnswerStorage: MockLocalAnswerStorage!

    override func setUp() {
        super.setUp()
        mockService = MockOpenAPIService()
        mockAnswerStorage = MockLocalAnswerStorage()
        sut = TestTakingViewModel(
            apiService: mockService,
            answerStorage: mockAnswerStorage
        )
    }

    override func tearDown() {
        sut = nil
        mockService = nil
        mockAnswerStorage = nil
        super.tearDown()
    }

    // MARK: - Helpers

    private func makeCooldownDate(daysFromNow: Int = 10) -> Date {
        Calendar.current.date(byAdding: .day, value: daysFromNow, to: Date())!
    }

    // MARK: - testCooldownInfo population

    func testHandleTestStartError_Cooldown_SetsCooldownInfo() {
        // Given
        let nextDate = makeCooldownDate(daysFromNow: 7)
        let daysRemaining = 7
        let error = APIError.testCooldown(nextEligibleDate: nextDate, daysRemaining: daysRemaining)

        // When
        sut.handleTestStartError(error, questionCount: 20)

        // Then
        XCTAssertNotNil(sut.testCooldownInfo, "testCooldownInfo should be set after a cooldown error")
        XCTAssertEqual(
            sut.testCooldownInfo?.nextDate,
            nextDate,
            "testCooldownInfo.nextDate should match the error's nextEligibleDate"
        )
        XCTAssertEqual(
            sut.testCooldownInfo?.daysRemaining,
            daysRemaining,
            "testCooldownInfo.daysRemaining should match the error's daysRemaining"
        )
    }

    func testHandleTestStartError_Cooldown_PreservesExactDate() throws {
        // Given — use a fixed reference date to assert the exact value stored
        var components = DateComponents()
        components.year = 2026
        components.month = 3
        components.day = 4
        let nextDate = try XCTUnwrap(Calendar(identifier: .gregorian).date(from: components))

        // When
        sut.handleTestStartError(.testCooldown(nextEligibleDate: nextDate, daysRemaining: 10), questionCount: 20)

        // Then
        let stored = sut.testCooldownInfo?.nextDate
        XCTAssertEqual(stored, nextDate, "The exact Date value should round-trip through testCooldownInfo")
    }

    // MARK: - isLoading / error invariants

    func testHandleTestStartError_Cooldown_SetsIsLoadingFalse() {
        // Given — force isLoading to true to verify it is cleared
        sut.setLoading(true)
        XCTAssertTrue(sut.isLoading, "Precondition: isLoading should be true before the call")

        // When
        sut.handleTestStartError(
            .testCooldown(nextEligibleDate: makeCooldownDate(), daysRemaining: 5),
            questionCount: 20
        )

        // Then
        XCTAssertFalse(sut.isLoading, "isLoading should be false after a cooldown error is handled")
    }

    func testHandleTestStartError_Cooldown_DoesNotSetError() {
        // Given
        XCTAssertNil(sut.error, "Precondition: error should be nil")

        // When
        sut.handleTestStartError(
            .testCooldown(nextEligibleDate: makeCooldownDate(), daysRemaining: 5),
            questionCount: 20
        )

        // Then — cooldown bypasses handleError; ViewModel.error must remain nil
        XCTAssertNil(sut.error, "error should remain nil — cooldown must not go through handleError")
    }

    // MARK: - shouldShowLoadFailure conditions

    /// TestTakingView.shouldShowLoadFailure reads:
    ///   !viewModel.isLoading && viewModel.navigationState.questions.isEmpty
    ///       && (viewModel.error != nil || viewModel.testCooldownInfo != nil)
    ///       && !viewModel.isActiveSessionConflict
    ///
    /// This test verifies that after a cooldown error the ViewModel satisfies every
    /// condition in that expression — even though error is nil.
    func testCooldownState_SatisfiesLoadFailureConditions() {
        // Given — default state: not loading, no questions, no error
        XCTAssertFalse(sut.isLoading, "Precondition: not loading")
        XCTAssertTrue(sut.navigationState.questions.isEmpty, "Precondition: no questions loaded")
        XCTAssertNil(sut.error, "Precondition: no error")

        // When
        sut.handleTestStartError(
            .testCooldown(nextEligibleDate: makeCooldownDate(), daysRemaining: 3),
            questionCount: 20
        )

        // Then — evaluate the shouldShowLoadFailure expression explicitly
        let notLoading = !sut.isLoading
        let questionsEmpty = sut.navigationState.questions.isEmpty
        let hasCooldownOrError = sut.error != nil || sut.testCooldownInfo != nil
        let notConflict = !sut.isActiveSessionConflict
        let shouldShowLoadFailure = notLoading && questionsEmpty && hasCooldownOrError && notConflict

        XCTAssertTrue(notLoading, "isLoading should be false after cooldown")
        XCTAssertTrue(questionsEmpty, "questions should remain empty after cooldown")
        XCTAssertNotNil(sut.testCooldownInfo, "testCooldownInfo should be set")
        XCTAssertNil(sut.error, "error should be nil — cooldown does not set error")
        XCTAssertFalse(sut.isActiveSessionConflict, "isActiveSessionConflict should be false")
        XCTAssertTrue(
            shouldShowLoadFailure,
            "shouldShowLoadFailure must be true when testCooldownInfo is set, even with error == nil"
        )
    }

    func testCooldownState_SatisfiesLoadFailure_ViaStartTest() async {
        // Given — simulate the full startTest path returning a cooldown error
        let nextDate = makeCooldownDate(daysFromNow: 42)
        mockService.startTestError = APIError.testCooldown(nextEligibleDate: nextDate, daysRemaining: 42)
        mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)

        // When
        await sut.startTest(questionCount: 20)

        // Then — same shouldShowLoadFailure expression as the view
        let shouldShowLoadFailure =
            !sut.isLoading
                && sut.navigationState.questions.isEmpty
                && (sut.error != nil || sut.testCooldownInfo != nil)
                && !sut.isActiveSessionConflict

        XCTAssertFalse(sut.isLoading, "isLoading should be false after startTest + cooldown")
        XCTAssertTrue(sut.navigationState.questions.isEmpty, "questions should be empty")
        XCTAssertNotNil(sut.testCooldownInfo, "testCooldownInfo should be populated")
        XCTAssertNil(sut.error, "error should remain nil for cooldown path")
        XCTAssertTrue(
            shouldShowLoadFailure,
            "shouldShowLoadFailure must be true after a cooldown error from startTest"
        )
    }
}
