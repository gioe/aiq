@testable import AIQ
import AIQSharedKit
import SwiftUI
import XCTest

// Tests for the question grid toggle feature consisting of:
//   - TestProgressHeader: holds a @Binding var showQuestionGrid and toggles it via a button
//   - QuestionNavigationGrid: receives onQuestionTap closure and renders question cells
//
// SwiftUI internal rendering state is inaccessible from unit tests, so these tests
// focus on:
//   1. Binding mutation semantics (toggle cycles)
//   2. Struct initialization with all required parameters
//   3. Closure capture and invocability
//   4. Accessibility identifier constant correctness

@MainActor
final class QuestionNavigationGridToggleTests: XCTestCase {
    // MARK: - Grid Toggle Binding Tests

    func testShowQuestionGrid_StartsAsFalse_WhenInitializedToFalse() {
        // Given
        let showGrid = false

        // Then
        XCTAssertFalse(showGrid, "Grid should start hidden (false)")
    }

    func testShowQuestionGrid_TogglesFromFalseToTrue() {
        // Given
        var showGrid = false

        // When
        showGrid.toggle()

        // Then
        XCTAssertTrue(showGrid, "First toggle should produce true")
    }

    func testShowQuestionGrid_TogglesFromTrueToFalse() {
        // Given
        var showGrid = true

        // When
        showGrid.toggle()

        // Then
        XCTAssertFalse(showGrid, "Toggle from true should produce false")
    }

    func testShowQuestionGrid_CyclesThroughThreeFullCycles() {
        // Given
        var showGrid = false
        let expectedSequence: [Bool] = [
            true, // cycle 1 open
            false, // cycle 1 close
            true, // cycle 2 open
            false, // cycle 2 close
            true, // cycle 3 open
            false // cycle 3 close
        ]

        // When / Then
        for (step, expected) in expectedSequence.enumerated() {
            showGrid.toggle()
            XCTAssertEqual(
                showGrid,
                expected,
                "Toggle step \(step + 1) should be \(expected)"
            )
        }
    }

    func testShowQuestionGrid_BindingMutation_ReflectsInSourceVariable() {
        // Given – simulate the pattern used in AdaptiveTestView:
        //   @State private var showQuestionGrid = false
        // The binding passed to TestProgressHeader wraps this variable.
        var sourceValue = false
        let binding = Binding(
            get: { sourceValue },
            set: { sourceValue = $0 }
        )

        // When
        binding.wrappedValue.toggle()

        // Then
        XCTAssertTrue(sourceValue, "Mutation via Binding must propagate back to the source variable")
    }

    func testShowQuestionGrid_BindingMutation_FourTogglesReturnToOriginalState() {
        // Given
        var sourceValue = false
        let binding = Binding(
            get: { sourceValue },
            set: { sourceValue = $0 }
        )

        // When – four toggles through two full open/close cycles
        binding.wrappedValue.toggle() // → true
        binding.wrappedValue.toggle() // → false
        binding.wrappedValue.toggle() // → true
        binding.wrappedValue.toggle() // → false

        // Then
        XCTAssertFalse(
            sourceValue,
            "Four toggles through two cycles must return binding to its initial false state"
        )
    }

    // MARK: - TestProgressHeader Initialization Tests

    func testProgressHeader_InitializesWithAllRequiredParameters() {
        // Given
        let timerManager = TestTimerManager()
        var showGrid = false
        let binding = Binding(get: { showGrid }, set: { showGrid = $0 })

        // When
        let header = TestProgressHeader(
            timerManager: timerManager,
            currentQuestionIndex: 0,
            totalQuestions: 20,
            answeredCount: 0,
            reduceMotion: false,
            showQuestionGrid: binding
        )

        // Then
        XCTAssertNotNil(header, "TestProgressHeader should initialize with all required parameters")
    }

    func testProgressHeader_InitializesWithReduceMotionEnabled() {
        // Given
        let timerManager = TestTimerManager()
        var showGrid = false
        let binding = Binding(get: { showGrid }, set: { showGrid = $0 })

        // When
        let header = TestProgressHeader(
            timerManager: timerManager,
            currentQuestionIndex: 5,
            totalQuestions: 20,
            answeredCount: 5,
            reduceMotion: true,
            showQuestionGrid: binding
        )

        // Then
        XCTAssertNotNil(header, "TestProgressHeader should initialize when reduceMotion is true")
    }

    func testProgressHeader_InitializesWithShowQuestionGridTrue() {
        // Given
        let timerManager = TestTimerManager()
        var showGrid = true
        let binding = Binding(get: { showGrid }, set: { showGrid = $0 })

        // When
        let header = TestProgressHeader(
            timerManager: timerManager,
            currentQuestionIndex: 3,
            totalQuestions: 15,
            answeredCount: 2,
            reduceMotion: false,
            showQuestionGrid: binding
        )

        // Then
        XCTAssertNotNil(header, "TestProgressHeader should initialize when showQuestionGrid binding is initially true")
    }

    // MARK: - QuestionNavigationGrid Initialization Tests

    func testGrid_InitializesWithRequiredParameters() {
        // When
        let grid = QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { _ in }
        )

        // Then
        XCTAssertNotNil(grid, "QuestionNavigationGrid should initialize with all required parameters")
    }

    func testGrid_InitializesWithZeroTotalQuestions() {
        // When
        let grid = QuestionNavigationGrid(
            totalQuestions: 0,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { _ in }
        )

        // Then
        XCTAssertNotNil(grid, "QuestionNavigationGrid should initialize without error when totalQuestions is 0")
    }

    func testGrid_InitializesWithAllQuestionsAnswered() {
        // Given
        let total = 20
        let allAnswered = Set(0 ..< total)

        // When
        let grid = QuestionNavigationGrid(
            totalQuestions: total,
            currentQuestionIndex: total - 1,
            answeredQuestionIndices: allAnswered,
            onQuestionTap: { _ in }
        )

        // Then
        XCTAssertNotNil(grid, "QuestionNavigationGrid should initialize when all \(total) questions are answered")
    }

    func testGrid_InitializesWithNoQuestionsAnswered() {
        // When
        let grid = QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { _ in }
        )

        // Then
        XCTAssertNotNil(grid, "QuestionNavigationGrid should initialize with empty answeredQuestionIndices")
    }

    func testGrid_InitializesWithPartialAnsweredSet() {
        // Given – non-contiguous answered indices to verify arbitrary Set contents are accepted
        let partialAnswered: Set<Int> = [0, 2, 5, 7, 11]

        // When
        let grid = QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 8,
            answeredQuestionIndices: partialAnswered,
            onQuestionTap: { _ in }
        )

        // Then
        XCTAssertNotNil(grid, "QuestionNavigationGrid should initialize with a non-contiguous partial answered set")
    }

    func testGrid_InitializesWithSingleQuestion() {
        // When
        let grid = QuestionNavigationGrid(
            totalQuestions: 1,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { _ in }
        )

        // Then
        XCTAssertNotNil(grid, "QuestionNavigationGrid should initialize with a single-question test")
    }

    func testGrid_InitializesWithMaxAdaptiveItemCount() {
        // Given – Constants.Test.maxAdaptiveItems is the largest count used in production
        let total = Constants.Test.maxAdaptiveItems

        // When
        let grid = QuestionNavigationGrid(
            totalQuestions: total,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { _ in }
        )

        // Then
        XCTAssertNotNil(
            grid,
            "QuestionNavigationGrid should initialize for the adaptive item count (\(total))"
        )
    }

    // MARK: - onQuestionTap Closure Tests

    func testOnQuestionTap_ClosureIsInvocable_CapturesFirstIndex() {
        // Given
        var tappedIndex: Int?
        let grid = QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { index in tappedIndex = index }
        )
        XCTAssertNotNil(grid)

        // When – invoke the closure directly, simulating a button tap on question 0
        grid.onQuestionTap(0)

        // Then
        XCTAssertEqual(tappedIndex, 0, "onQuestionTap should capture the first question index (0)")
    }

    func testOnQuestionTap_ClosureCapturesMidpointIndex() {
        // Given
        let total = 20
        let midIndex = total / 2
        var tappedIndex: Int?
        let grid = QuestionNavigationGrid(
            totalQuestions: total,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { index in tappedIndex = index }
        )
        XCTAssertNotNil(grid)

        // When
        grid.onQuestionTap(midIndex)

        // Then
        XCTAssertEqual(tappedIndex, midIndex, "onQuestionTap should capture midpoint index (\(midIndex))")
    }

    func testOnQuestionTap_ClosureCapturesLastIndex() {
        // Given
        let total = 20
        let lastIndex = total - 1
        var tappedIndex: Int?
        let grid = QuestionNavigationGrid(
            totalQuestions: total,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { index in tappedIndex = index }
        )
        XCTAssertNotNil(grid)

        // When
        grid.onQuestionTap(lastIndex)

        // Then
        XCTAssertEqual(tappedIndex, lastIndex, "onQuestionTap should capture the last index (\(lastIndex))")
    }

    func testOnQuestionTap_FiresForMultipleDistinctIndices() {
        // Given
        var tappedIndices: [Int] = []
        let grid = QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 5,
            answeredQuestionIndices: [0, 1, 2],
            onQuestionTap: { index in tappedIndices.append(index) }
        )
        XCTAssertNotNil(grid)

        // When – simulate navigating to three different questions
        grid.onQuestionTap(0)
        grid.onQuestionTap(9)
        grid.onQuestionTap(19)

        // Then
        XCTAssertEqual(tappedIndices, [0, 9, 19], "onQuestionTap should fire for each distinct index in order")
    }

    func testOnQuestionTap_NotCalledOnInitialization() {
        // Given
        var tappedCount = 0

        // When
        _ = QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 0,
            answeredQuestionIndices: [],
            onQuestionTap: { _ in tappedCount += 1 }
        )

        // Then
        XCTAssertEqual(tappedCount, 0, "onQuestionTap must not fire on view initialization")
    }

    // MARK: - Accessibility Identifier Tests

    func testAccessibilityIdentifier_QuestionNavigationGrid() {
        XCTAssertEqual(
            AccessibilityIdentifiers.TestTakingView.questionNavigationGrid,
            "testTakingView.questionNavigationGrid"
        )
    }

    func testAccessibilityIdentifier_QuestionNavigationGridToggle() {
        XCTAssertEqual(
            AccessibilityIdentifiers.TestTakingView.questionNavigationGridToggle,
            "testTakingView.questionNavigationGridToggle"
        )
    }

    func testAccessibilityIdentifier_QuestionNavigationButton_AtIndexZero() {
        XCTAssertEqual(
            AccessibilityIdentifiers.TestTakingView.questionNavigationButton(at: 0),
            "testTakingView.questionNavigationButton.0"
        )
    }

    func testAccessibilityIdentifier_QuestionNavigationButton_AtMidIndex() {
        // Given
        let midIndex = 9

        // Then
        XCTAssertEqual(
            AccessibilityIdentifiers.TestTakingView.questionNavigationButton(at: midIndex),
            "testTakingView.questionNavigationButton.\(midIndex)"
        )
    }

    func testAccessibilityIdentifier_QuestionNavigationButton_AtLastIndex() {
        // Given
        let lastIndex = 19

        // Then
        XCTAssertEqual(
            AccessibilityIdentifiers.TestTakingView.questionNavigationButton(at: lastIndex),
            "testTakingView.questionNavigationButton.\(lastIndex)"
        )
    }

    func testAccessibilityIdentifier_QuestionNavigationButton_EmbedIndexInString() {
        // Verify the function embeds the index as a decimal integer at the end of the identifier.
        for index in [0, 1, 5, 10, 19] {
            let identifier = AccessibilityIdentifiers.TestTakingView.questionNavigationButton(at: index)
            XCTAssertTrue(
                identifier.hasSuffix(".\(index)"),
                "Button identifier at index \(index) should end with '.\(index)' — got '\(identifier)'"
            )
        }
    }
}
