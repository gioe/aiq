import XCTest

@testable import AIQ

/// Tests for IQTrendChart domain calculation logic.
///
/// These tests verify the computed properties that determine chart Y-axis domain,
/// confidence interval detection, and data sampling for chart rendering.
final class IQTrendChartTests: XCTestCase {
    // MARK: - Test Helpers

    /// Creates a TestResult with specified score and optional confidence interval
    private func makeTestResult(
        id: Int = 1,
        iqScore: Int,
        confidenceInterval: ConfidenceInterval? = nil,
        daysAgo: Int = 0
    ) -> TestResult {
        TestResult(
            id: id,
            testSessionId: id,
            userId: 1,
            iqScore: iqScore,
            percentileRank: nil,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completionTimeSeconds: 1200,
            completedAt: Date().addingTimeInterval(-Double(daysAgo) * 24 * 60 * 60),
            confidenceInterval: confidenceInterval
        )
    }

    /// Creates a ConfidenceInterval with specified bounds
    private func makeConfidenceInterval(lower: Int, upper: Int) -> ConfidenceInterval {
        ConfidenceInterval(
            lower: lower,
            upper: upper,
            confidenceLevel: 0.95,
            standardError: 3.5
        )
    }

    // MARK: - chartYDomain Tests

    func testChartYDomainWithEmptyHistory() {
        // Given
        let history: [TestResult] = []

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then - should return default range
        XCTAssertEqual(domain.lowerBound, 70)
        XCTAssertEqual(domain.upperBound, 130)
    }

    func testChartYDomainWithSingleScore() {
        // Given
        let history = [makeTestResult(iqScore: 100)]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then - should have padding around the single score
        // minValue = 100, maxValue = 100
        // lowerBound = max(70, 100 - 10) = 90
        // upperBound = min(160, 100 + 10) = 110
        XCTAssertEqual(domain.lowerBound, 90)
        XCTAssertEqual(domain.upperBound, 110)
    }

    func testChartYDomainWithMultipleScoresNoCI() {
        // Given
        let history = [
            makeTestResult(id: 1, iqScore: 95, daysAgo: 30),
            makeTestResult(id: 2, iqScore: 105, daysAgo: 20),
            makeTestResult(id: 3, iqScore: 110, daysAgo: 10),
            makeTestResult(id: 4, iqScore: 100, daysAgo: 0)
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then
        // min = 95, max = 110
        // lowerBound = max(70, 95 - 10) = 85
        // upperBound = min(160, 110 + 10) = 120
        XCTAssertEqual(domain.lowerBound, 85)
        XCTAssertEqual(domain.upperBound, 120)
    }

    func testChartYDomainWithConfidenceIntervalsExpandsDomain() {
        // Given - scores are 100-110 but CI extends to 90-120
        let history = [
            makeTestResult(
                id: 1,
                iqScore: 100,
                confidenceInterval: makeConfidenceInterval(lower: 90, upper: 110),
                daysAgo: 10
            ),
            makeTestResult(
                id: 2,
                iqScore: 110,
                confidenceInterval: makeConfidenceInterval(lower: 100, upper: 120),
                daysAgo: 0
            )
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then - CI bounds should be included
        // min = 90 (from CI lower), max = 120 (from CI upper)
        // lowerBound = max(70, 90 - 10) = 80
        // upperBound = min(160, 120 + 10) = 130
        XCTAssertEqual(domain.lowerBound, 80)
        XCTAssertEqual(domain.upperBound, 130)
    }

    func testChartYDomainWithMixedCIAndNonCIData() {
        // Given - some results have CI, others don't
        let history = [
            makeTestResult(
                id: 1,
                iqScore: 100,
                confidenceInterval: makeConfidenceInterval(lower: 92, upper: 108),
                daysAgo: 30
            ),
            makeTestResult(
                id: 2,
                iqScore: 105,
                confidenceInterval: nil, // No CI
                daysAgo: 20
            ),
            makeTestResult(
                id: 3,
                iqScore: 115,
                confidenceInterval: makeConfidenceInterval(lower: 107, upper: 123),
                daysAgo: 10
            ),
            makeTestResult(
                id: 4,
                iqScore: 110,
                confidenceInterval: nil, // No CI
                daysAgo: 0
            )
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then
        // Scores: 100, 105, 115, 110
        // CI bounds: 92, 108, 107, 123
        // min = 92, max = 123
        // lowerBound = max(70, 92 - 10) = 82
        // upperBound = min(160, 123 + 10) = 133
        XCTAssertEqual(domain.lowerBound, 82)
        XCTAssertEqual(domain.upperBound, 133)
    }

    func testChartYDomainClampsToMinimum70() {
        // Given - very low score
        let history = [
            makeTestResult(
                iqScore: 75,
                confidenceInterval: makeConfidenceInterval(lower: 65, upper: 85)
            )
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then
        // min = 65, max = 85
        // lowerBound = max(70, 65 - 10) = max(70, 55) = 70 (clamped)
        // upperBound = min(160, 85 + 10) = 95
        XCTAssertEqual(domain.lowerBound, 70)
        XCTAssertEqual(domain.upperBound, 95)
    }

    func testChartYDomainClampsToMaximum160() {
        // Given - very high score
        let history = [
            makeTestResult(
                iqScore: 155,
                confidenceInterval: makeConfidenceInterval(lower: 148, upper: 160)
            )
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then
        // min = 148, max = 160
        // lowerBound = max(70, 148 - 10) = 138
        // upperBound = min(160, 160 + 10) = min(160, 170) = 160 (clamped)
        XCTAssertEqual(domain.lowerBound, 138)
        XCTAssertEqual(domain.upperBound, 160)
    }

    func testChartYDomainWithExtremeRange() {
        // Given - wide range of scores
        let history = [
            makeTestResult(
                id: 1,
                iqScore: 75,
                confidenceInterval: makeConfidenceInterval(lower: 68, upper: 82),
                daysAgo: 20
            ),
            makeTestResult(
                id: 2,
                iqScore: 145,
                confidenceInterval: makeConfidenceInterval(lower: 138, upper: 152),
                daysAgo: 0
            )
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then
        // min = 68, max = 152
        // lowerBound = max(70, 68 - 10) = max(70, 58) = 70 (clamped)
        // upperBound = min(160, 152 + 10) = min(160, 162) = 160 (clamped)
        XCTAssertEqual(domain.lowerBound, 70)
        XCTAssertEqual(domain.upperBound, 160)
    }

    // MARK: - hasConfidenceIntervals Tests

    func testHasConfidenceIntervalsWithEmptyHistory() {
        // Given
        let history: [TestResult] = []

        // When
        let hasCI = ChartDomainCalculator.hasConfidenceIntervals(in: history)

        // Then
        XCTAssertFalse(hasCI)
    }

    func testHasConfidenceIntervalsWithNonePresent() {
        // Given
        let history = [
            makeTestResult(id: 1, iqScore: 100, daysAgo: 20),
            makeTestResult(id: 2, iqScore: 105, daysAgo: 10),
            makeTestResult(id: 3, iqScore: 110, daysAgo: 0)
        ]

        // When
        let hasCI = ChartDomainCalculator.hasConfidenceIntervals(in: history)

        // Then
        XCTAssertFalse(hasCI)
    }

    func testHasConfidenceIntervalsWithAllPresent() {
        // Given
        let history = [
            makeTestResult(
                id: 1,
                iqScore: 100,
                confidenceInterval: makeConfidenceInterval(lower: 93, upper: 107),
                daysAgo: 20
            ),
            makeTestResult(
                id: 2,
                iqScore: 105,
                confidenceInterval: makeConfidenceInterval(lower: 98, upper: 112),
                daysAgo: 10
            ),
            makeTestResult(
                id: 3,
                iqScore: 110,
                confidenceInterval: makeConfidenceInterval(lower: 103, upper: 117),
                daysAgo: 0
            )
        ]

        // When
        let hasCI = ChartDomainCalculator.hasConfidenceIntervals(in: history)

        // Then
        XCTAssertTrue(hasCI)
    }

    func testHasConfidenceIntervalsWithSomePresent() {
        // Given
        let history = [
            makeTestResult(id: 1, iqScore: 100, daysAgo: 30),
            makeTestResult(
                id: 2,
                iqScore: 105,
                confidenceInterval: makeConfidenceInterval(lower: 98, upper: 112),
                daysAgo: 20
            ),
            makeTestResult(id: 3, iqScore: 110, daysAgo: 10),
            makeTestResult(id: 4, iqScore: 115, daysAgo: 0)
        ]

        // When
        let hasCI = ChartDomainCalculator.hasConfidenceIntervals(in: history)

        // Then
        XCTAssertTrue(hasCI)
    }

    func testHasConfidenceIntervalsWithOnlyOneResult() {
        // Given - single result with CI
        let historyWithCI = [
            makeTestResult(
                iqScore: 100,
                confidenceInterval: makeConfidenceInterval(lower: 93, upper: 107)
            )
        ]

        // Given - single result without CI
        let historyWithoutCI = [
            makeTestResult(iqScore: 100)
        ]

        // When/Then
        XCTAssertTrue(ChartDomainCalculator.hasConfidenceIntervals(in: historyWithCI))
        XCTAssertFalse(ChartDomainCalculator.hasConfidenceIntervals(in: historyWithoutCI))
    }

    // MARK: - sampledDataWithCI Tests

    func testSampledDataWithCIEmptyHistory() {
        // Given
        let history: [TestResult] = []

        // When
        let filtered = ChartDomainCalculator.filterResultsWithCI(from: history)

        // Then
        XCTAssertTrue(filtered.isEmpty)
    }

    func testSampledDataWithCIFiltersCorrectly() {
        // Given
        let history = [
            makeTestResult(id: 1, iqScore: 100, daysAgo: 40),
            makeTestResult(
                id: 2,
                iqScore: 105,
                confidenceInterval: makeConfidenceInterval(lower: 98, upper: 112),
                daysAgo: 30
            ),
            makeTestResult(id: 3, iqScore: 110, daysAgo: 20),
            makeTestResult(
                id: 4,
                iqScore: 115,
                confidenceInterval: makeConfidenceInterval(lower: 108, upper: 122),
                daysAgo: 10
            ),
            makeTestResult(id: 5, iqScore: 120, daysAgo: 0)
        ]

        // When
        let filtered = ChartDomainCalculator.filterResultsWithCI(from: history)

        // Then
        XCTAssertEqual(filtered.count, 2)
        XCTAssertEqual(filtered[0].id, 2)
        XCTAssertEqual(filtered[1].id, 4)
    }

    func testSampledDataWithCIWhenAllHaveCI() {
        // Given
        let history = [
            makeTestResult(
                id: 1,
                iqScore: 100,
                confidenceInterval: makeConfidenceInterval(lower: 93, upper: 107),
                daysAgo: 20
            ),
            makeTestResult(
                id: 2,
                iqScore: 110,
                confidenceInterval: makeConfidenceInterval(lower: 103, upper: 117),
                daysAgo: 10
            ),
            makeTestResult(
                id: 3,
                iqScore: 120,
                confidenceInterval: makeConfidenceInterval(lower: 113, upper: 127),
                daysAgo: 0
            )
        ]

        // When
        let filtered = ChartDomainCalculator.filterResultsWithCI(from: history)

        // Then
        XCTAssertEqual(filtered.count, 3)
        XCTAssertEqual(filtered.map(\.id), [1, 2, 3])
    }

    func testSampledDataWithCIWhenNoneHaveCI() {
        // Given
        let history = [
            makeTestResult(id: 1, iqScore: 100, daysAgo: 20),
            makeTestResult(id: 2, iqScore: 110, daysAgo: 10),
            makeTestResult(id: 3, iqScore: 120, daysAgo: 0)
        ]

        // When
        let filtered = ChartDomainCalculator.filterResultsWithCI(from: history)

        // Then
        XCTAssertTrue(filtered.isEmpty)
    }

    // MARK: - Data Sampling Tests

    func testDataSamplingWithSmallDataset() {
        // Given - less than maxDataPoints (50)
        var history: [TestResult] = []
        for i in 0 ..< 10 {
            history.append(makeTestResult(id: i, iqScore: 100 + i, daysAgo: 10 - i))
        }

        // When
        let sampled = ChartDomainCalculator.sampleData(from: history, maxDataPoints: 50)

        // Then - should return all data
        XCTAssertEqual(sampled.count, 10)
    }

    func testDataSamplingWithLargeDataset() {
        // Given - more than maxDataPoints
        var history: [TestResult] = []
        for i in 0 ..< 100 {
            history.append(makeTestResult(id: i, iqScore: 100, daysAgo: 100 - i))
        }

        // When
        let sampled = ChartDomainCalculator.sampleData(from: history, maxDataPoints: 50)

        // Then - should sample down to approximately maxDataPoints
        // The exact count may be 50 or 51 depending on whether the last element is duplicated
        XCTAssertLessThanOrEqual(sampled.count, 51)
        XCTAssertGreaterThanOrEqual(sampled.count, 50)
    }

    func testDataSamplingPreservesOrder() {
        // Given
        var history: [TestResult] = []
        for i in 0 ..< 100 {
            history.append(makeTestResult(id: i, iqScore: 100 + i, daysAgo: 100 - i))
        }

        // When
        let sampled = ChartDomainCalculator.sampleData(from: history, maxDataPoints: 50)

        // Then - data should be sorted by date (ascending)
        let dates = sampled.map(\.completedAt)
        for i in 1 ..< dates.count {
            XCTAssertLessThanOrEqual(dates[i - 1], dates[i])
        }
    }

    func testDataSamplingIncludesLastResult() {
        // Given
        var history: [TestResult] = []
        for i in 0 ..< 100 {
            history.append(makeTestResult(id: i, iqScore: 100, daysAgo: 100 - i))
        }

        // When
        let sampled = ChartDomainCalculator.sampleData(from: history, maxDataPoints: 50)

        // Then - the most recent result should be included
        let sortedHistory = history.sorted { $0.completedAt < $1.completedAt }
        let lastHistoryId = sortedHistory.last?.id
        let sampledIds = sampled.map(\.id)

        XCTAssertTrue(sampledIds.contains(lastHistoryId!))
    }

    // MARK: - Edge Case: Single Result Tests

    func testSingleResultWithCI() {
        // Given
        let history = [
            makeTestResult(
                iqScore: 108,
                confidenceInterval: makeConfidenceInterval(lower: 101, upper: 115)
            )
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)
        let hasCI = ChartDomainCalculator.hasConfidenceIntervals(in: history)
        let filtered = ChartDomainCalculator.filterResultsWithCI(from: history)

        // Then
        XCTAssertEqual(domain.lowerBound, 91) // max(70, 101 - 10)
        XCTAssertEqual(domain.upperBound, 125) // min(160, 115 + 10)
        XCTAssertTrue(hasCI)
        XCTAssertEqual(filtered.count, 1)
    }

    func testSingleResultWithoutCI() {
        // Given
        let history = [
            makeTestResult(iqScore: 108)
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)
        let hasCI = ChartDomainCalculator.hasConfidenceIntervals(in: history)
        let filtered = ChartDomainCalculator.filterResultsWithCI(from: history)

        // Then
        XCTAssertEqual(domain.lowerBound, 98) // max(70, 108 - 10)
        XCTAssertEqual(domain.upperBound, 118) // min(160, 108 + 10)
        XCTAssertFalse(hasCI)
        XCTAssertTrue(filtered.isEmpty)
    }

    // MARK: - Score at Boundary Tests

    func testScoreAtExactlyAverageIQ() {
        // Given - score is exactly 100 (average IQ)
        let history = [
            makeTestResult(iqScore: 100)
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then
        XCTAssertEqual(domain.lowerBound, 90) // max(70, 100 - 10)
        XCTAssertEqual(domain.upperBound, 110) // min(160, 100 + 10)
    }

    func testCIExactlyAtBoundaries() {
        // Given - CI exactly at 40-160 bounds
        let history = [
            makeTestResult(
                iqScore: 100,
                confidenceInterval: ConfidenceInterval(
                    lower: 40,
                    upper: 160,
                    confidenceLevel: 0.95,
                    standardError: 30.0
                )
            )
        ]

        // When
        let domain = ChartDomainCalculator.calculateYDomain(for: history)

        // Then - even with padding, should clamp to 70-160
        XCTAssertEqual(domain.lowerBound, 70) // max(70, 40 - 10) = max(70, 30) = 70
        XCTAssertEqual(domain.upperBound, 160) // min(160, 160 + 10) = min(160, 170) = 160
    }
}
