import Foundation

/// Represents analytical insights derived from test history
struct PerformanceInsights: Equatable {
    // MARK: - Trend Analysis

    /// Overall performance trend direction
    enum TrendDirection: Equatable {
        case improving
        case declining
        case stable
        case insufficient // Less than 2 tests

        var description: String {
            switch self {
            case .improving: "Improving"
            case .declining: "Declining"
            case .stable: "Stable"
            case .insufficient: "Need More Data"
            }
        }

        var icon: String {
            switch self {
            case .improving: "arrow.up.right.circle.fill"
            case .declining: "arrow.down.right.circle.fill"
            case .stable: "arrow.right.circle.fill"
            case .insufficient: "questionmark.circle.fill"
            }
        }
    }

    // MARK: - Properties

    let trendDirection: TrendDirection
    let trendPercentage: Double?
    let consistencyScore: Double // 0-100, higher = more consistent
    let recentPerformance: String // Description of recent performance
    let bestPeriod: String? // When user performed best
    let improvementSinceFirst: Double? // Percentage change from first to latest test
    let averageImprovement: Double? // Average point change per test
    let insights: [String] // Array of actionable insights

    // MARK: - Initialization

    /// Calculate performance insights from test history
    /// - Parameter testHistory: Array of test results, should be sorted by date
    init(from testHistory: [TestResult]) {
        guard !testHistory.isEmpty else {
            trendDirection = .insufficient
            trendPercentage = nil
            consistencyScore = 0
            recentPerformance = "No tests completed yet"
            bestPeriod = nil
            improvementSinceFirst = nil
            averageImprovement = nil
            insights = ["Complete your first test to see insights!"]
            return
        }

        // Sort by date (oldest first for chronological analysis)
        let sortedTests = testHistory.sorted { $0.completedAt < $1.completedAt }

        // Calculate trend direction
        (trendDirection, trendPercentage) = Self.calculateTrend(from: sortedTests)

        // Calculate consistency (inverse of standard deviation normalized)
        consistencyScore = Self.calculateConsistency(from: sortedTests)

        // Recent performance description
        recentPerformance = Self.describeRecentPerformance(from: sortedTests)

        // Best period identification
        bestPeriod = Self.identifyBestPeriod(from: sortedTests)

        // Improvement since first test
        improvementSinceFirst = Self.calculateImprovementSinceFirst(from: sortedTests)

        // Average improvement per test
        averageImprovement = Self.calculateAverageImprovement(from: sortedTests)

        // Generate actionable insights
        insights = Self.generateInsights(
            tests: sortedTests,
            trend: trendDirection,
            consistency: consistencyScore,
            improvement: improvementSinceFirst
        )
    }

    // MARK: - Private Calculation Methods

    /// Calculate performance trend from test history
    private static func calculateTrend(
        from tests: [TestResult]
    ) -> (TrendDirection, Double?) {
        guard tests.count >= 2 else {
            return (.insufficient, nil)
        }

        // Compare recent tests (last 3 or half, whichever is smaller) to previous tests
        let recentCount = min(3, tests.count / 2)
        let recentTests = Array(tests.suffix(recentCount))
        let previousTests = Array(tests.prefix(tests.count - recentCount))

        guard !previousTests.isEmpty else {
            return (.insufficient, nil)
        }

        let recentAverage = Double(recentTests.map(\.iqScore).reduce(0, +)) / Double(
            recentTests.count)
        let previousAverage = Double(previousTests.map(\.iqScore).reduce(0, +)) / Double(
            previousTests.count)

        let difference = recentAverage - previousAverage
        let percentChange = (difference / previousAverage) * 100

        // Threshold for "stable" is ±3%
        let direction: TrendDirection = if abs(percentChange) < 3.0 {
            .stable
        } else if percentChange > 0 {
            .improving
        } else {
            .declining
        }

        return (direction, percentChange)
    }

    /// Calculate consistency score (0-100, higher = more consistent)
    private static func calculateConsistency(from tests: [TestResult]) -> Double {
        guard tests.count >= 2 else { return 0 }

        let scores = tests.map { Double($0.iqScore) }
        let mean = scores.reduce(0, +) / Double(scores.count)

        // Calculate standard deviation
        let squaredDifferences = scores.map { pow($0 - mean, 2) }
        let variance = squaredDifferences.reduce(0, +) / Double(scores.count)
        let standardDeviation = sqrt(variance)

        // Normalize: typical IQ std dev is around 15 points
        // Lower std dev = higher consistency
        let normalizedScore = max(0, 100 - (standardDeviation / 15.0) * 100)

        return min(100, normalizedScore)
    }

    /// Describe recent performance trend
    private static func describeRecentPerformance(from tests: [TestResult]) -> String {
        guard tests.count >= 2 else {
            return "Complete more tests to see trends"
        }

        let recentCount = min(3, tests.count)
        let recentTests = Array(tests.suffix(recentCount))
        let recentAverage = recentTests.map(\.iqScore).reduce(0, +) / recentTests.count

        let latestScore = tests.last!.iqScore
        let difference = latestScore - recentAverage

        if abs(difference) <= 2 {
            return "Performing consistently with recent average"
        } else if difference > 0 {
            return "Above your recent average by \(abs(difference)) points"
        } else {
            return "Below your recent average by \(abs(difference)) points"
        }
    }

    /// Identify the best performing period
    private static func identifyBestPeriod(from tests: [TestResult]) -> String? {
        guard tests.count >= 3 else { return nil }

        // Find the test with highest score
        guard let bestTest = tests.max(by: { $0.iqScore < $1.iqScore }) else { return nil }

        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full

        let timeDescription = formatter.localizedString(for: bestTest.completedAt, relativeTo: Date())

        return "\(timeDescription)"
    }

    /// Calculate improvement percentage from first to latest test
    private static func calculateImprovementSinceFirst(from tests: [TestResult]) -> Double? {
        guard tests.count >= 2 else { return nil }

        let firstScore = Double(tests.first!.iqScore)
        let latestScore = Double(tests.last!.iqScore)

        let change = latestScore - firstScore
        let percentChange = (change / firstScore) * 100

        return percentChange
    }

    /// Calculate average improvement per test
    private static func calculateAverageImprovement(from tests: [TestResult]) -> Double? {
        guard tests.count >= 2 else { return nil }

        let firstScore = Double(tests.first!.iqScore)
        let latestScore = Double(tests.last!.iqScore)
        let totalChange = latestScore - firstScore

        return totalChange / Double(tests.count - 1)
    }

    /// Generate actionable insights based on performance data
    private static func generateInsights(
        tests: [TestResult],
        trend: TrendDirection,
        consistency: Double,
        improvement: Double?
    ) -> [String] {
        var insights: [String] = []

        insights.append(contentsOf: trendInsights(trend))
        insights.append(contentsOf: consistencyInsights(consistency: consistency, testCount: tests.count))
        insights.append(contentsOf: improvementInsights(improvement: improvement, testCount: tests.count))
        insights.append(contentsOf: recentPerformanceInsights(tests: tests))
        insights.append(contentsOf: completionTimeInsights(tests: tests))

        return insights
    }

    private static func trendInsights(_ trend: TrendDirection) -> [String] {
        switch trend {
        case .improving:
            ["Great progress! Keep up the consistent practice."]
        case .declining:
            ["Consider taking a break and returning refreshed for your next test."]
        case .stable:
            ["You're maintaining consistent performance across tests."]
        case .insufficient:
            ["Take more tests to unlock detailed insights."]
        }
    }

    private static func consistencyInsights(consistency: Double, testCount: Int) -> [String] {
        if consistency >= 80 {
            return ["Your scores are very consistent - excellent reliability!"]
        } else if consistency < 50 && testCount >= 3 {
            return ["Your scores vary significantly. Try testing in similar conditions for better consistency."]
        }
        return []
    }

    private static func improvementInsights(improvement: Double?, testCount: Int) -> [String] {
        guard let improvement, testCount >= 3 else { return [] }

        if improvement > 10 {
            return ["Impressive \(String(format: "%.1f", improvement))% improvement since your first test!"]
        } else if improvement < -10 {
            return ["Your scores have declined since your first test. Consider what might have changed."]
        }
        return []
    }

    private static func recentPerformanceInsights(tests: [TestResult]) -> [String] {
        guard tests.count >= 2 else { return [] }

        let lastTwo = Array(tests.suffix(2))
        let scoreDiff = lastTwo[1].iqScore - lastTwo[0].iqScore

        if scoreDiff >= 10 {
            return ["Strong improvement in your most recent test!"]
        } else if scoreDiff <= -10 {
            return ["Your latest score dropped. Ensure you're well-rested for your next test."]
        }
        return []
    }

    private static func completionTimeInsights(tests: [TestResult]) -> [String] {
        let testsWithTime = tests.filter { $0.completionTimeSeconds != nil }
        guard testsWithTime.count >= 2 else { return [] }

        let avgTime = testsWithTime.compactMap(\.completionTimeSeconds).reduce(0, +) / testsWithTime.count
        if avgTime < 600 {
            return ["You complete tests quickly. Taking more time might improve accuracy."]
        }
        return []
    }
}
