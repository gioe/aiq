@testable import AIQ
import XCTest

final class PerformanceInsightsTests: XCTestCase {
    // MARK: - Helper Methods

    private func createTestResult(
        id: Int,
        iqScore: Int,
        completedAt: Date,
        completionTimeSeconds: Int? = nil
    ) -> TestResult {
        TestResult(
            accuracyPercentage: 75.0,
            completedAt: completedAt,
            completionTimeSeconds: completionTimeSeconds,
            confidenceInterval: nil,
            correctAnswers: 15,
            domainScores: nil,
            id: id,
            iqScore: iqScore,
            percentileRank: nil,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: id,
            totalQuestions: 20,
            userId: 1,
            weakestDomain: nil
        )
    }

    // MARK: - Initialization Tests

    func testInit_EmptyTestHistory_ReturnsInsufficientData() {
        // Given
        let testHistory: [TestResult] = []

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.trendDirection, .insufficient)
        XCTAssertNil(insights.trendPercentage)
        XCTAssertEqual(insights.consistencyScore, 0)
        XCTAssertEqual(insights.recentPerformance, "No tests completed yet")
        XCTAssertNil(insights.bestPeriod)
        XCTAssertNil(insights.improvementSinceFirst)
        XCTAssertNil(insights.averageImprovement)
        XCTAssertEqual(insights.insights, ["Complete your first test to see insights!"])
    }

    func testInit_SingleTest_ReturnsInsufficientData() {
        // Given
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: Date())
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.trendDirection, .insufficient)
        XCTAssertNil(insights.trendPercentage)
        XCTAssertEqual(insights.recentPerformance, "Complete more tests to see trends")
    }

    // MARK: - Trend Direction Tests

    func testTrendDirection_ImprovingScores_ReturnsImproving() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 90, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)), // 30 days ago
            createTestResult(id: 2, iqScore: 95, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)), // 20 days ago
            createTestResult(id: 3, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)), // 10 days ago
            createTestResult(id: 4, iqScore: 110, completedAt: now) // Today
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.trendDirection, .improving)
        XCTAssertNotNil(insights.trendPercentage)
        if let percentage = insights.trendPercentage {
            XCTAssertGreaterThan(percentage, 3.0) // Should be > 3% improvement
        }
    }

    func testTrendDirection_DecliningScores_ReturnsDeclining() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 110, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 95, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 90, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.trendDirection, .declining)
        XCTAssertNotNil(insights.trendPercentage)
        if let percentage = insights.trendPercentage {
            XCTAssertLessThan(percentage, -3.0) // Should be < -3% (declining)
        }
    }

    func testTrendDirection_StableScores_ReturnsStable() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 101, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 99, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 100, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.trendDirection, .stable)
        XCTAssertNotNil(insights.trendPercentage)
        if let percentage = insights.trendPercentage {
            XCTAssertLessThanOrEqual(abs(percentage), 3.0) // Within ±3%
        }
    }

    // MARK: - Consistency Score Tests

    func testConsistencyScore_IdenticalScores_ReturnsHighConsistency() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 100, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.consistencyScore, 100.0, accuracy: 0.1)
    }

    func testConsistencyScore_HighVariance_ReturnsLowConsistency() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 80, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 120, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 90, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 110, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertLessThan(insights.consistencyScore, 50.0) // Low consistency
    }

    func testConsistencyScore_SingleTest_ReturnsZero() {
        // Given
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: Date())
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.consistencyScore, 0)
    }

    // MARK: - Recent Performance Tests

    func testRecentPerformance_AboveAverage() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 95, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 2, iqScore: 97, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 3, iqScore: 105, completedAt: now) // Well above average
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.recentPerformance.contains("Above"))
    }

    func testRecentPerformance_BelowAverage() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 2, iqScore: 103, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 3, iqScore: 95, completedAt: now) // Well below average
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.recentPerformance.contains("Below"))
    }

    func testRecentPerformance_ConsistentWithAverage() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 2, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 3, iqScore: 100, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.recentPerformance.contains("consistently"))
    }

    // MARK: - Best Period Tests

    func testBestPeriod_IdentifiesHighestScore() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 120, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)), // Highest
            createTestResult(id: 3, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 110, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertNotNil(insights.bestPeriod)
    }

    func testBestPeriod_LessThanThreeTests_ReturnsNil() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 2, iqScore: 105, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertNil(insights.bestPeriod)
    }

    // MARK: - Improvement Metrics Tests

    func testImprovementSinceFirst_PositiveImprovement() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 110, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertNotNil(insights.improvementSinceFirst)
        if let improvement = insights.improvementSinceFirst {
            XCTAssertEqual(improvement, 10.0, accuracy: 0.1) // 10% improvement
        }
    }

    func testImprovementSinceFirst_NegativeImprovement() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 110, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 100, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertNotNil(insights.improvementSinceFirst)
        if let improvement = insights.improvementSinceFirst {
            XCTAssertEqual(improvement, -9.09, accuracy: 0.1) // ~-9.09% decline
        }
    }

    func testAverageImprovement_CalculatesCorrectly() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 40)),
            createTestResult(id: 2, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 3, iqScore: 110, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 4, iqScore: 115, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertNotNil(insights.averageImprovement)
        if let avgImprovement = insights.averageImprovement {
            // Total change: 115 - 100 = 15 points over 3 intervals
            XCTAssertEqual(avgImprovement, 5.0, accuracy: 0.1) // 15 / 3 = 5 points per test
        }
    }

    // MARK: - Insights Generation Tests

    func testInsights_ImprovingTrend_ContainsPositiveMessage() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 90, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 95, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 110, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.insights.contains("Great progress! Keep up the consistent practice."))
    }

    func testInsights_DecliningTrend_ContainsSuggestion() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 110, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 95, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 90, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.insights.contains("Consider taking a break and returning refreshed for your next test."))
    }

    func testInsights_HighConsistency_ContainsConsistencyMessage() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 101, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 99, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.insights.contains { $0.contains("consistent") && $0.contains("reliability") })
    }

    func testInsights_LowConsistency_ContainsSuggestion() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 80, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 120, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 90, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 110, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.insights.contains { $0.contains("vary significantly") })
    }

    func testInsights_SignificantImprovement_ContainsCongratulations() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 90, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 95, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 105, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 4, iqScore: 110, completedAt: now) // >10% improvement
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.insights.contains { $0.contains("Impressive") && $0.contains("improvement") })
    }

    func testInsights_RecentDrop_ContainsAdvice() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 110, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 2, iqScore: 95, completedAt: now) // >10 point drop
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.insights.contains { $0.contains("well-rested") })
    }

    func testInsights_FastCompletion_SuggestsSlowingDown() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20), completionTimeSeconds: 500),
            createTestResult(id: 2, iqScore: 105, completedAt: now, completionTimeSeconds: 550)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertTrue(insights.insights.contains { $0.contains("Taking more time") })
    }

    // MARK: - TrendDirection Enum Tests

    func testTrendDirection_Description() {
        // When/Then
        XCTAssertEqual(PerformanceInsights.TrendDirection.improving.description, "Improving")
        XCTAssertEqual(PerformanceInsights.TrendDirection.declining.description, "Declining")
        XCTAssertEqual(PerformanceInsights.TrendDirection.stable.description, "Stable")
        XCTAssertEqual(PerformanceInsights.TrendDirection.insufficient.description, "Need More Data")
    }

    func testTrendDirection_Icon() {
        // When/Then
        XCTAssertEqual(PerformanceInsights.TrendDirection.improving.icon, "arrow.up.right.circle.fill")
        XCTAssertEqual(PerformanceInsights.TrendDirection.declining.icon, "arrow.down.right.circle.fill")
        XCTAssertEqual(PerformanceInsights.TrendDirection.stable.icon, "arrow.right.circle.fill")
        XCTAssertEqual(PerformanceInsights.TrendDirection.insufficient.icon, "questionmark.circle.fill")
    }

    // MARK: - Equatable Tests

    func testEquatable_IdenticalInsights_AreEqual() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 10)),
            createTestResult(id: 2, iqScore: 105, completedAt: now)
        ]

        // When
        let insights1 = PerformanceInsights(from: testHistory)
        let insights2 = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights1, insights2)
    }

    func testEquatable_DifferentInsights_AreNotEqual() {
        // Given - Use more test history to get different computed insights
        let now = Date()
        let testHistory1 = [
            createTestResult(id: 1, iqScore: 90, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 110, completedAt: now)
        ]
        let testHistory2 = [
            createTestResult(id: 1, iqScore: 110, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)),
            createTestResult(id: 2, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)),
            createTestResult(id: 3, iqScore: 90, completedAt: now)
        ]

        // When
        let insights1 = PerformanceInsights(from: testHistory1)
        let insights2 = PerformanceInsights(from: testHistory2)

        // Then - Different trends (improving vs declining) should produce different insights
        XCTAssertNotEqual(insights1, insights2)
    }

    // MARK: - Edge Cases

    func testInit_UnsortedTestHistory_SortsCorrectly() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 3, iqScore: 110, completedAt: now), // Latest
            createTestResult(id: 1, iqScore: 90, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)), // Oldest
            createTestResult(id: 2, iqScore: 100, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 15)) // Middle
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then - Should calculate improvement from 90 to 110
        XCTAssertNotNil(insights.improvementSinceFirst)
        if let improvement = insights.improvementSinceFirst {
            XCTAssertGreaterThan(improvement, 20.0) // Should be ~22% improvement
        }
    }

    func testInit_AllSameScores_NoVariance() {
        // Given
        let now = Date()
        let testHistory = Array(0 ..< 10).map { index in
            createTestResult(
                id: index,
                iqScore: 100,
                completedAt: now.addingTimeInterval(Double(-index * 60 * 60 * 24))
            )
        }

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then
        XCTAssertEqual(insights.trendDirection, .stable)
        XCTAssertEqual(insights.consistencyScore, 100.0, accuracy: 0.1)
        XCTAssertEqual(insights.improvementSinceFirst ?? 0.0, 0.0, accuracy: 0.1)
    }

    func testInit_ExtremeScoreVariation_HandlesCorrectly() {
        // Given
        let now = Date()
        let testHistory = [
            createTestResult(id: 1, iqScore: 40, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 30)), // Min valid IQ
            createTestResult(id: 2, iqScore: 160, completedAt: now.addingTimeInterval(-60 * 60 * 24 * 20)), // Max valid IQ
            createTestResult(id: 3, iqScore: 100, completedAt: now)
        ]

        // When
        let insights = PerformanceInsights(from: testHistory)

        // Then - Should handle extreme variance
        XCTAssertLessThan(insights.consistencyScore, 20.0) // Very low consistency
        XCTAssertNotNil(insights.improvementSinceFirst)
    }
}
