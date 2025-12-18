import Charts
import SwiftUI

/// Chart component displaying IQ score trends over time
struct IQTrendChart: View {
    let testHistory: [TestResult]

    // Maximum number of data points to render for performance
    private let maxDataPoints = 50

    /// Whether any results have confidence interval data
    private var hasConfidenceIntervals: Bool {
        testHistory.contains { $0.confidenceInterval != nil }
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
                    ForEach(sampledDataWithCI) { result in
                        if let ci = result.confidenceInterval {
                            AreaMark(
                                x: .value("Date", result.completedAt),
                                yStart: .value("CI Lower", ci.lower),
                                yEnd: .value("CI Upper", ci.upper)
                            )
                            .foregroundStyle(Color.accentColor.opacity(0.15))
                            .interpolationMethod(.catmullRom)
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
        guard testHistory.count > maxDataPoints else {
            return testHistory
        }

        // Always include first and last test
        var sampled: [TestResult] = []
        let sortedHistory = testHistory.sorted { $0.completedAt < $1.completedAt }

        // Calculate sampling interval
        let interval = Double(sortedHistory.count) / Double(maxDataPoints)

        for sampleIndex in 0 ..< maxDataPoints {
            let index = min(Int(Double(sampleIndex) * interval), sortedHistory.count - 1)
            sampled.append(sortedHistory[index])
        }

        // Ensure we include the last test if not already included
        if let last = sortedHistory.last, sampled.last?.id != last.id {
            sampled.append(last)
        }

        return sampled
    }

    /// Sampled data filtered to only results with confidence intervals
    private var sampledDataWithCI: [TestResult] {
        sampledData.filter { $0.confidenceInterval != nil }
    }

    /// Calculate appropriate Y-axis domain based on score range (including CI bounds)
    private var chartYDomain: ClosedRange<Int> {
        guard !testHistory.isEmpty else { return 70 ... 130 }

        // Collect all scores and CI bounds in a single pass for better performance
        var allValues: [Int] = []
        allValues.reserveCapacity(testHistory.count * 3) // Pre-allocate for score + CI bounds

        for result in testHistory {
            allValues.append(result.iqScore)
            if let ci = result.confidenceInterval {
                allValues.append(ci.lower)
                allValues.append(ci.upper)
            }
        }

        let minValue = allValues.min() ?? 100
        let maxValue = allValues.max() ?? 100

        // Add padding to make the chart more readable
        let padding = 10
        let lowerBound = max(70, minValue - padding)
        let upperBound = min(160, maxValue + padding)

        return lowerBound ... upperBound
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

        if hasConfidenceIntervals {
            label += "Shaded areas show 95% confidence intervals for measurement uncertainty."
        }

        return label
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
