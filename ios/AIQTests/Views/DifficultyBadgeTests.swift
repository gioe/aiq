import SwiftUI
import XCTest

@testable import AIQ

@MainActor
final class DifficultyBadgeTests: XCTestCase {
    func testViewCanBeInitializedWithEasyDifficulty() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "easy")

        // Then
        XCTAssertNotNil(view, "View should be initialized successfully")
    }

    func testViewCanBeInitializedWithMediumDifficulty() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "medium")

        // Then
        XCTAssertNotNil(view, "View should be initialized successfully")
    }

    func testViewCanBeInitializedWithHardDifficulty() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "hard")

        // Then
        XCTAssertNotNil(view, "View should be initialized successfully")
    }

    func testViewCanBeInitializedWithUnknownDifficulty() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "unknown")

        // Then
        XCTAssertNotNil(view, "View should be initialized successfully")
    }

    func testViewInitializesWithProvidedDifficultyLevel() {
        // Given
        let expectedDifficulty = "hard"

        // When
        let view = DifficultyBadge(difficultyLevel: expectedDifficulty)

        // Then
        let mirror = Mirror(reflecting: view)
        if let difficultyLevel = mirror.descendant("difficultyLevel") as? String {
            XCTAssertEqual(difficultyLevel, expectedDifficulty, "difficultyLevel should match provided value")
        } else {
            XCTFail("Could not access difficultyLevel property")
        }
    }

    func testDifficultyCirclesReturnsOneForEasy() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "easy")

        // Then
        XCTAssertEqual(view.difficultyCircles, 1, "Easy difficulty should return 1 circle")
    }

    func testDifficultyCirclesReturnsTwoForMedium() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "medium")

        // Then
        XCTAssertEqual(view.difficultyCircles, 2, "Medium difficulty should return 2 circles")
    }

    func testDifficultyCirclesReturnsThreeForHard() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "hard")

        // Then
        XCTAssertEqual(view.difficultyCircles, 3, "Hard difficulty should return 3 circles")
    }

    func testDifficultyCirclesReturnsDefaultTwoForUnknown() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "unknown")

        // Then
        XCTAssertEqual(view.difficultyCircles, 2, "Unknown difficulty should return default 2 circles")
    }

    func testColorForDifficultyReturnsGreenForEasy() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "easy")

        // Then
        XCTAssertEqual(view.colorForDifficulty, .green, "Easy difficulty should return green color")
    }

    func testColorForDifficultyReturnsOrangeForMedium() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "medium")

        // Then
        XCTAssertEqual(view.colorForDifficulty, .orange, "Medium difficulty should return orange color")
    }

    func testColorForDifficultyReturnsRedForHard() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "hard")

        // Then
        XCTAssertEqual(view.colorForDifficulty, .red, "Hard difficulty should return red color")
    }

    func testColorForDifficultyReturnsDefaultOrangeForUnknown() {
        // Given/When
        let view = DifficultyBadge(difficultyLevel: "unknown")

        // Then
        XCTAssertEqual(view.colorForDifficulty, .orange, "Unknown difficulty should return default orange color")
    }
}
