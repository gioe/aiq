import Charts
import SwiftUI

/// Chart component displaying IQ score trends over time
struct IQTrendChart: View {
    let testHistory: [TestResult]

    // Maximum number of data points to render for performance
    private let maxDataPoints = 50

    /// Whether any results have confidence interval data
    private var hasConfidenceIntervals: Bool {
        ChartDomainCalculator.hasConfidenceIntervals(in: testHistory)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("IQ Score Trend")
                    .font(.headline)
                    .foregroundColor(.primary)

                Spacer()

                // Legend for confidence interval band (when applicable)
                if hasConfidenceIntervals {
                    HStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.accentColor.opacity(0.2))
                            .frame(width: 12, height: 8)
                        Text("95% CI")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    .accessibilityLabel("Shaded area shows 95% confidence interval")
                }
            }

            if testHistory.count >= 2 {
                Chart {
                    // Confidence interval area (rendered first to be behind line)
                    // Uses linear interpolation rather than smooth curves because CI represents
                    // measurement uncertainty at discrete test points - we have no data about
                    // uncertainty between tests, so smooth interpolation would be misleading.
                    ForEach(sampledDataWithCI) { result in
                        if let ci = result.confidenceInterval {
                            AreaMark(
                                x: .value("Date", result.completedAt),
                                yStart: .value("CI Lower", ci.lower),
                                yEnd: .value("CI Upper", ci.upper)
                            )
                            .foregroundStyle(Color.accentColor.opacity(0.15))
                            .interpolationMethod(.linear)
                        }
                    }

                    // Main score line
                    ForEach(sampledData) { result in
                        LineMark(
                            x: .value("Date", result.completedAt),
                            y: .value("IQ Score", result.iqScore)
                        )
                        .foregroundStyle(Color.accentColor)
                        .lineStyle(StrokeStyle(lineWidth: 2))

                        PointMark(
                            x: .value("Date", result.completedAt),
                            y: .value("IQ Score", result.iqScore)
                        )
                        .foregroundStyle(Color.accentColor)
                        .symbolSize(60)
                    }

                    // Add a reference line at average IQ (100)
                    RuleMark(y: .value("Average", 100))
                        .foregroundStyle(Color.secondary.opacity(0.3))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 5]))
                        .annotation(position: .top, alignment: .trailing) {
                            Text("Avg (100)")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                }
                .chartYScale(domain: chartYDomain)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 3)) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading)
                }
                .frame(height: 200)
                .drawingGroup() // Rasterize chart for better rendering performance
                .accessibilityElement(children: .combine)
                .accessibilityLabel(chartAccessibilityLabel)
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "chart.xyaxis.line")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)

                    Text("Not enough data")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    Text("Complete at least 2 tests to see your trend")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(height: 200)
                .frame(maxWidth: .infinity)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 4, x: 0, y: 2)
    }

    /// Sampled data for rendering (improves performance with large datasets)
    private var sampledData: [TestResult] {
        ChartDomainCalculator.sampleData(from: testHistory, maxDataPoints: maxDataPoints)
    }

    /// Sampled data filtered to only results with confidence intervals
    private var sampledDataWithCI: [TestResult] {
        ChartDomainCalculator.filterResultsWithCI(from: sampledData)
    }

    /// Calculate appropriate Y-axis domain based on score range (including CI bounds)
    private var chartYDomain: ClosedRange<Int> {
        ChartDomainCalculator.calculateYDomain(for: testHistory)
    }

    /// Accessibility label describing the chart content
    private var chartAccessibilityLabel: String {
        guard !testHistory.isEmpty else {
            return "IQ score trend chart with no data"
        }

        let scores = testHistory.map(\.iqScore)
        let minScore = scores.min() ?? 0
        let maxScore = scores.max() ?? 0
        let avgScore = scores.reduce(0, +) / scores.count

        var label = "IQ score trend chart showing \(testHistory.count) test results. "
        label += "Scores range from \(minScore) to \(maxScore) with an average of \(avgScore). "

        // Add date range for temporal context
        label += dateRangeDescription

        if hasConfidenceIntervals {
            label += "Shaded areas show 95% confidence intervals for measurement uncertainty."
        }

        return label
    }

    /// Formatted date range description for accessibility
    private var dateRangeDescription: String {
        let sortedDates = testHistory.map(\.completedAt).sorted()
        guard let firstDate = sortedDates.first,
              let lastDate = sortedDates.last else {
            return ""
        }

        // If all tests are on the same day, just mention that date
        if Calendar.current.isDate(firstDate, inSameDayAs: lastDate) {
            return "Tests taken on \(firstDate.toShortString()). "
        }

        return "Tests span from \(firstDate.toShortString()) to \(lastDate.toShortString()). "
    }
}

#Preview("With Confidence Intervals") {
    let sampleHistory = [
        TestResult(
            id: 1,
            testSessionId: 1,
            userId: 1,
            iqScore: 105,
            percentileRank: 63.0,
            totalQuestions: 20,
            correctAnswers: 13,
            accuracyPercentage: 65.0,
            completionTimeSeconds: 1200,
            completedAt: Date().addingTimeInterval(-30 * 24 * 60 * 60),
            confidenceInterval: ConfidenceInterval(
                lower: 98,
                upper: 112,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        ),
        TestResult(
            id: 2,
            testSessionId: 2,
            userId: 1,
            iqScore: 112,
            percentileRank: 75.0,
            totalQuestions: 20,
            correctAnswers: 15,
            accuracyPercentage: 75.0,
            completionTimeSeconds: 1100,
            completedAt: Date().addingTimeInterval(-20 * 24 * 60 * 60),
            confidenceInterval: ConfidenceInterval(
                lower: 105,
                upper: 119,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        ),
        TestResult(
            id: 3,
            testSessionId: 3,
            userId: 1,
            iqScore: 118,
            percentileRank: 88.0,
            totalQuestions: 20,
            correctAnswers: 17,
            accuracyPercentage: 85.0,
            completionTimeSeconds: 1050,
            completedAt: Date().addingTimeInterval(-10 * 24 * 60 * 60),
            confidenceInterval: ConfidenceInterval(
                lower: 111,
                upper: 125,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        ),
        TestResult(
            id: 4,
            testSessionId: 4,
            userId: 1,
            iqScore: 125,
            percentileRank: 95.0,
            totalQuestions: 20,
            correctAnswers: 18,
            accuracyPercentage: 90.0,
            completionTimeSeconds: 1000,
            completedAt: Date(),
            confidenceInterval: ConfidenceInterval(
                lower: 118,
                upper: 132,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        )
    ]

    ScrollView {
        IQTrendChart(testHistory: sampleHistory)
            .padding()
    }
}

#Preview("Without Confidence Intervals") {
    let sampleHistory = [
        TestResult(
            id: 1,
            testSessionId: 1,
            userId: 1,
            iqScore: 105,
            percentileRank: 63.0,
            totalQuestions: 20,
            correctAnswers: 13,
            accuracyPercentage: 65.0,
            completionTimeSeconds: 1200,
            completedAt: Date().addingTimeInterval(-30 * 24 * 60 * 60)
        ),
        TestResult(
            id: 2,
            testSessionId: 2,
            userId: 1,
            iqScore: 112,
            percentileRank: 75.0,
            totalQuestions: 20,
            correctAnswers: 15,
            accuracyPercentage: 75.0,
            completionTimeSeconds: 1100,
            completedAt: Date().addingTimeInterval(-20 * 24 * 60 * 60)
        ),
        TestResult(
            id: 3,
            testSessionId: 3,
            userId: 1,
            iqScore: 118,
            percentileRank: 88.0,
            totalQuestions: 20,
            correctAnswers: 17,
            accuracyPercentage: 85.0,
            completionTimeSeconds: 1050,
            completedAt: Date().addingTimeInterval(-10 * 24 * 60 * 60)
        ),
        TestResult(
            id: 4,
            testSessionId: 4,
            userId: 1,
            iqScore: 125,
            percentileRank: 95.0,
            totalQuestions: 20,
            correctAnswers: 18,
            accuracyPercentage: 90.0,
            completionTimeSeconds: 1000,
            completedAt: Date()
        )
    ]

    ScrollView {
        IQTrendChart(testHistory: sampleHistory)
            .padding()
    }
}

#Preview("Not Enough Data") {
    let sampleHistory = [
        TestResult(
            id: 1,
            testSessionId: 1,
            userId: 1,
            iqScore: 105,
            percentileRank: 63.0,
            totalQuestions: 20,
            correctAnswers: 13,
            accuracyPercentage: 65.0,
            completionTimeSeconds: 1200,
            completedAt: Date()
        )
    ]

    ScrollView {
        IQTrendChart(testHistory: sampleHistory)
            .padding()
    }
}
