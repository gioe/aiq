import Charts
import SwiftUI

/// Chart component displaying IQ score trends over time
struct IQTrendChart: View {
    let testHistory: [TestResult]

    // Maximum number of data points to render for performance
    private let maxDataPoints = 50

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("IQ Score Trend")
                .font(.headline)
                .foregroundColor(.primary)

            if testHistory.count >= 2 {
                Chart {
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

    /// Calculate appropriate Y-axis domain based on score range
    private var chartYDomain: ClosedRange<Int> {
        guard !testHistory.isEmpty else { return 70 ... 130 }

        let scores = testHistory.map(\.iqScore)
        let minScore = scores.min() ?? 100
        let maxScore = scores.max() ?? 100

        // Add padding to make the chart more readable
        let padding = 10
        let lowerBound = max(70, minScore - padding)
        let upperBound = min(160, maxScore + padding)

        return lowerBound ... upperBound
    }
}

#Preview {
    let sampleHistory = [
        TestResult(
            id: 1,
            testSessionId: 1,
            userId: 1,
            iqScore: 105,
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
            totalQuestions: 20,
            correctAnswers: 18,
            accuracyPercentage: 90.0,
            completionTimeSeconds: 1000,
            completedAt: Date()
        )
    ]

    return ScrollView {
        VStack(spacing: 16) {
            IQTrendChart(testHistory: sampleHistory)

            IQTrendChart(testHistory: Array(sampleHistory.prefix(1)))
        }
        .padding()
    }
}
