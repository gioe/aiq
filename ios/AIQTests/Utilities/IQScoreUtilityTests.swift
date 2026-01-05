@testable import AIQ
import SwiftUI
import XCTest

final class IQScoreUtilityTests: XCTestCase {
    // MARK: - Score Classification Tests

    func testClassify_ExtremelyLowScores_ReturnsExtremelyLow() {
        // Given
        let extremelyLowScores = [0, 30, 50, 69]

        for score in extremelyLowScores {
            // When
            let category = IQScoreUtility.classify(score)

            // Then
            XCTAssertEqual(category, .extremelyLow, "Expected score \(score) to be Extremely Low")
        }
    }

    func testClassify_BelowAverageScores_ReturnsBelowAverage() {
        // Given
        let belowAverageScores = [70, 75, 80, 84]

        for score in belowAverageScores {
            // When
            let category = IQScoreUtility.classify(score)

            // Then
            XCTAssertEqual(category, .belowAverage, "Expected score \(score) to be Below Average")
        }
    }

    func testClassify_AverageScores_ReturnsAverage() {
        // Given
        let averageScores = [85, 90, 100, 110, 114]

        for score in averageScores {
            // When
            let category = IQScoreUtility.classify(score)

            // Then
            XCTAssertEqual(category, .average, "Expected score \(score) to be Average")
        }
    }

    func testClassify_AboveAverageScores_ReturnsAboveAverage() {
        // Given
        let aboveAverageScores = [115, 120, 125, 129]

        for score in aboveAverageScores {
            // When
            let category = IQScoreUtility.classify(score)

            // Then
            XCTAssertEqual(category, .aboveAverage, "Expected score \(score) to be Above Average")
        }
    }

    func testClassify_GiftedScores_ReturnsGifted() {
        // Given
        let giftedScores = [130, 135, 140, 144]

        for score in giftedScores {
            // When
            let category = IQScoreUtility.classify(score)

            // Then
            XCTAssertEqual(category, .gifted, "Expected score \(score) to be Gifted")
        }
    }

    func testClassify_HighlyGiftedScores_ReturnsHighlyGifted() {
        // Given
        let highlyGiftedScores = [145, 150, 160, 180, 200]

        for score in highlyGiftedScores {
            // When
            let category = IQScoreUtility.classify(score)

            // Then
            XCTAssertEqual(category, .highlyGifted, "Expected score \(score) to be Highly Gifted")
        }
    }

    func testClassify_NegativeScores_ReturnsInvalid() {
        // Given
        let negativeScores = [-1, -10, -100]

        for score in negativeScores {
            // When
            let category = IQScoreUtility.classify(score)

            // Then
            XCTAssertEqual(category, .invalid, "Expected score \(score) to be Invalid")
        }
    }

    // MARK: - Boundary Tests

    func testClassify_BoundaryAt70_ReturnsBelowAverage() {
        // Given
        let score = 70

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .belowAverage)
    }

    func testClassify_BoundaryAt69_ReturnsExtremelyLow() {
        // Given
        let score = 69

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .extremelyLow)
    }

    func testClassify_BoundaryAt85_ReturnsAverage() {
        // Given
        let score = 85

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .average)
    }

    func testClassify_BoundaryAt84_ReturnsBelowAverage() {
        // Given
        let score = 84

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .belowAverage)
    }

    func testClassify_BoundaryAt115_ReturnsAboveAverage() {
        // Given
        let score = 115

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .aboveAverage)
    }

    func testClassify_BoundaryAt114_ReturnsAverage() {
        // Given
        let score = 114

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .average)
    }

    func testClassify_BoundaryAt130_ReturnsGifted() {
        // Given
        let score = 130

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .gifted)
    }

    func testClassify_BoundaryAt129_ReturnsAboveAverage() {
        // Given
        let score = 129

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .aboveAverage)
    }

    func testClassify_BoundaryAt145_ReturnsHighlyGifted() {
        // Given
        let score = 145

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .highlyGifted)
    }

    func testClassify_BoundaryAt144_ReturnsGifted() {
        // Given
        let score = 144

        // When
        let category = IQScoreUtility.classify(score)

        // Then
        XCTAssertEqual(category, .gifted)
    }

    // MARK: - Category Description Tests

    func testCategoryDescription_ExtremelyLow_ReturnsCorrectString() {
        XCTAssertEqual(IQScoreUtility.Category.extremelyLow.description, "Extremely Low")
    }

    func testCategoryDescription_BelowAverage_ReturnsCorrectString() {
        XCTAssertEqual(IQScoreUtility.Category.belowAverage.description, "Below Average")
    }

    func testCategoryDescription_Average_ReturnsCorrectString() {
        XCTAssertEqual(IQScoreUtility.Category.average.description, "Average")
    }

    func testCategoryDescription_AboveAverage_ReturnsCorrectString() {
        XCTAssertEqual(IQScoreUtility.Category.aboveAverage.description, "Above Average")
    }

    func testCategoryDescription_Gifted_ReturnsCorrectString() {
        XCTAssertEqual(IQScoreUtility.Category.gifted.description, "Gifted")
    }

    func testCategoryDescription_HighlyGifted_ReturnsCorrectString() {
        XCTAssertEqual(IQScoreUtility.Category.highlyGifted.description, "Highly Gifted")
    }

    func testCategoryDescription_Invalid_ReturnsCorrectString() {
        XCTAssertEqual(IQScoreUtility.Category.invalid.description, "Invalid Score")
    }

    // MARK: - Category Color Tests

    func testCategoryColor_ExtremelyLow_ReturnsError() {
        XCTAssertEqual(IQScoreUtility.Category.extremelyLow.color, ColorPalette.error)
    }

    func testCategoryColor_BelowAverage_ReturnsWarning() {
        XCTAssertEqual(IQScoreUtility.Category.belowAverage.color, ColorPalette.warning)
    }

    func testCategoryColor_Average_ReturnsInfo() {
        XCTAssertEqual(IQScoreUtility.Category.average.color, ColorPalette.info)
    }

    func testCategoryColor_AboveAverage_ReturnsInfo() {
        XCTAssertEqual(IQScoreUtility.Category.aboveAverage.color, ColorPalette.info)
    }

    func testCategoryColor_Gifted_ReturnsSuccess() {
        XCTAssertEqual(IQScoreUtility.Category.gifted.color, ColorPalette.success)
    }

    func testCategoryColor_HighlyGifted_ReturnsSuccess() {
        XCTAssertEqual(IQScoreUtility.Category.highlyGifted.color, ColorPalette.success)
    }

    func testCategoryColor_Invalid_ReturnsError() {
        XCTAssertEqual(IQScoreUtility.Category.invalid.color, ColorPalette.error)
    }

    // MARK: - Category Icon Tests

    func testCategoryIcon_ExtremelyLow_ReturnsCircle() {
        XCTAssertEqual(IQScoreUtility.Category.extremelyLow.icon, "circle")
    }

    func testCategoryIcon_BelowAverage_ReturnsCircle() {
        XCTAssertEqual(IQScoreUtility.Category.belowAverage.icon, "circle")
    }

    func testCategoryIcon_Average_ReturnsCircleFill() {
        XCTAssertEqual(IQScoreUtility.Category.average.icon, "circle.fill")
    }

    func testCategoryIcon_AboveAverage_ReturnsRosette() {
        XCTAssertEqual(IQScoreUtility.Category.aboveAverage.icon, "rosette")
    }

    func testCategoryIcon_Gifted_ReturnsStarFill() {
        XCTAssertEqual(IQScoreUtility.Category.gifted.icon, "star.fill")
    }

    func testCategoryIcon_HighlyGifted_ReturnsStarFill() {
        XCTAssertEqual(IQScoreUtility.Category.highlyGifted.icon, "star.fill")
    }

    func testCategoryIcon_Invalid_ReturnsCircle() {
        XCTAssertEqual(IQScoreUtility.Category.invalid.icon, "circle")
    }

    // MARK: - Integration Tests

    func testClassify_EndToEnd_ReturnsCorrectDescriptions() {
        // Test the full flow from score to description
        let testCases: [(score: Int, expectedDescription: String)] = [
            (50, "Extremely Low"),
            (75, "Below Average"),
            (100, "Average"),
            (120, "Above Average"),
            (135, "Gifted"),
            (160, "Highly Gifted"),
            (-5, "Invalid Score")
        ]

        for testCase in testCases {
            // When
            let description = IQScoreUtility.classify(testCase.score).description

            // Then
            XCTAssertEqual(
                description,
                testCase.expectedDescription,
                "Score \(testCase.score) should have description '\(testCase.expectedDescription)'"
            )
        }
    }

    func testClassify_EndToEnd_ReturnsCorrectColors() {
        // Test the full flow from score to color using ColorPalette
        let testCases: [(score: Int, expectedColor: Color)] = [
            (50, ColorPalette.error),
            (75, ColorPalette.warning),
            (100, ColorPalette.info),
            (120, ColorPalette.info),
            (135, ColorPalette.success),
            (160, ColorPalette.success),
            (-5, ColorPalette.error)
        ]

        for testCase in testCases {
            // When
            let color = IQScoreUtility.classify(testCase.score).color

            // Then
            XCTAssertEqual(
                color,
                testCase.expectedColor,
                "Score \(testCase.score) should have color \(testCase.expectedColor)"
            )
        }
    }

    // MARK: - Edge Cases

    func testClassify_Zero_ReturnsExtremelyLow() {
        XCTAssertEqual(IQScoreUtility.classify(0), .extremelyLow)
    }

    func testClassify_VeryHighScore_ReturnsHighlyGifted() {
        XCTAssertEqual(IQScoreUtility.classify(300), .highlyGifted)
    }

    func testClassify_IntMaxValue_ReturnsHighlyGifted() {
        XCTAssertEqual(IQScoreUtility.classify(Int.max), .highlyGifted)
    }

    func testClassify_IntMinValue_ReturnsInvalid() {
        XCTAssertEqual(IQScoreUtility.classify(Int.min), .invalid)
    }
}
