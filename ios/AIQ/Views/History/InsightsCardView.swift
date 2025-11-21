import SwiftUI

/// Card view displaying performance insights and analytics
struct InsightsCardView: View {
    let insights: PerformanceInsights

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // Header
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(.yellow)
                    .font(.title2)

                Text("Performance Insights")
                    .font(.headline)
                    .fontWeight(.bold)

                Spacer()
            }
            .padding(.bottom, 4)

            // Performance Overview Section
            performanceOverview

            Divider()

            // Detailed Metrics Section
            detailedMetrics

            Divider()

            // Actionable Insights
            actionableInsights
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 8, x: 0, y: 2)
    }

    // MARK: - Performance Overview

    private var performanceOverview: some View {
        VStack(spacing: 12) {
            // Trend Direction
            HStack(spacing: 16) {
                Image(systemName: insights.trendDirection.icon)
                    .font(.system(size: 32))
                    .foregroundColor(trendColor)

                VStack(alignment: .leading, spacing: 4) {
                    Text("Trend")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Text(insights.trendDirection.description)
                        .font(.title3)
                        .fontWeight(.semibold)
                        .foregroundColor(trendColor)

                    if let percentage = insights.trendPercentage {
                        Text(formatPercentage(percentage))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()
            }
            .padding()
            .background(trendColor.opacity(0.1))
            .cornerRadius(12)

            // Recent Performance Description
            if insights.trendDirection != .insufficient {
                HStack(spacing: 12) {
                    Image(systemName: "info.circle.fill")
                        .foregroundColor(.accentColor)
                        .font(.body)

                    Text(insights.recentPerformance)
                        .font(.subheadline)
                        .foregroundColor(.primary)

                    Spacer()
                }
            }
        }
    }

    // MARK: - Detailed Metrics

    private var detailedMetrics: some View {
        VStack(spacing: 16) {
            // Consistency Score
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Consistency")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    HStack(spacing: 8) {
                        Text(String(format: "%.0f%%", insights.consistencyScore))
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(consistencyColor)

                        Image(systemName: consistencyIcon)
                            .foregroundColor(consistencyColor)
                    }

                    Text(consistencyDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }

            // Improvement Since First Test
            if let improvement = insights.improvementSinceFirst {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Overall Progress")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        HStack(spacing: 8) {
                            Text(formatPercentage(improvement))
                                .font(.title2)
                                .fontWeight(.bold)
                                .foregroundColor(improvementColor(improvement))

                            Image(systemName: improvementIcon(improvement))
                                .foregroundColor(improvementColor(improvement))
                        }

                        Text("Since your first test")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()
                }
            }

            // Average Improvement Per Test
            if let avgImprovement = insights.averageImprovement,
               abs(avgImprovement) >= 0.5 {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Average Change")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        HStack(spacing: 8) {
                            Text(formatPoints(avgImprovement))
                                .font(.title3)
                                .fontWeight(.semibold)
                                .foregroundColor(.primary)

                            Text("per test")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }

                    Spacer()
                }
            }

            // Best Period
            if let bestPeriod = insights.bestPeriod {
                HStack(spacing: 12) {
                    Image(systemName: "star.fill")
                        .foregroundColor(.yellow)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("Peak Performance")
                            .font(.caption)
                            .foregroundColor(.secondary)

                        Text(bestPeriod)
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }

                    Spacer()
                }
                .padding(.vertical, 8)
                .padding(.horizontal, 12)
                .background(Color.yellow.opacity(0.1))
                .cornerRadius(8)
            }
        }
    }

    // MARK: - Actionable Insights

    private var actionableInsights: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Key Insights")
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)

            ForEach(Array(insights.insights.enumerated()), id: \.offset) { index, insight in
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "\(index + 1).circle.fill")
                        .foregroundColor(.accentColor)
                        .font(.body)

                    Text(insight)
                        .font(.subheadline)
                        .foregroundColor(.primary)
                        .fixedSize(horizontal: false, vertical: true)

                    Spacer(minLength: 0)
                }
            }
        }
    }

    // MARK: - Helper Properties

    private var trendColor: Color {
        switch insights.trendDirection {
        case .improving:
            .green
        case .declining:
            .red
        case .stable:
            .blue
        case .insufficient:
            .gray
        }
    }

    private var consistencyColor: Color {
        if insights.consistencyScore >= 80 {
            .green
        } else if insights.consistencyScore >= 60 {
            .blue
        } else {
            .orange
        }
    }

    private var consistencyIcon: String {
        if insights.consistencyScore >= 80 {
            "checkmark.circle.fill"
        } else if insights.consistencyScore >= 60 {
            "minus.circle.fill"
        } else {
            "exclamationmark.circle.fill"
        }
    }

    private var consistencyDescription: String {
        if insights.consistencyScore >= 80 {
            "Highly consistent performance"
        } else if insights.consistencyScore >= 60 {
            "Moderately consistent"
        } else {
            "Performance varies significantly"
        }
    }

    // MARK: - Helper Methods

    private func improvementColor(_ improvement: Double) -> Color {
        if improvement > 5 {
            .green
        } else if improvement < -5 {
            .red
        } else {
            .blue
        }
    }

    private func improvementIcon(_ improvement: Double) -> String {
        if improvement > 5 {
            "arrow.up.circle.fill"
        } else if improvement < -5 {
            "arrow.down.circle.fill"
        } else {
            "equal.circle.fill"
        }
    }

    private func formatPercentage(_ value: Double) -> String {
        let formatted = String(format: "%.1f%%", abs(value))
        if value > 0 {
            return "+\(formatted)"
        } else if value < 0 {
            return "-\(formatted)"
        } else {
            return formatted
        }
    }

    private func formatPoints(_ value: Double) -> String {
        let formatted = String(format: "%.1f", abs(value))
        if value > 0 {
            return "+\(formatted) pts"
        } else if value < 0 {
            return "-\(formatted) pts"
        } else {
            return "\(formatted) pts"
        }
    }
}

// MARK: - Preview

#Preview("Improving Trend") {
    ScrollView {
        InsightsCardView(
            insights: PerformanceInsights(
                from: [
                    TestResult(
                        id: 1,
                        testSessionId: 1,
                        userId: 1,
                        iqScore: 105,
                        percentileRank: 60.0,
                        totalQuestions: 20,
                        correctAnswers: 14,
                        accuracyPercentage: 70.0,
                        completionTimeSeconds: 1500,
                        completedAt: Date().addingTimeInterval(-86400 * 180)
                    ),
                    TestResult(
                        id: 2,
                        testSessionId: 2,
                        userId: 1,
                        iqScore: 110,
                        percentileRank: 70.0,
                        totalQuestions: 20,
                        correctAnswers: 15,
                        accuracyPercentage: 75.0,
                        completionTimeSeconds: 1450,
                        completedAt: Date().addingTimeInterval(-86400 * 90)
                    ),
                    TestResult(
                        id: 3,
                        testSessionId: 3,
                        userId: 1,
                        iqScore: 118,
                        percentileRank: 85.0,
                        totalQuestions: 20,
                        correctAnswers: 17,
                        accuracyPercentage: 85.0,
                        completionTimeSeconds: 1400,
                        completedAt: Date()
                    )
                ]
            )
        )
        .padding()
    }
}

#Preview("Stable Performance") {
    ScrollView {
        InsightsCardView(
            insights: PerformanceInsights(
                from: [
                    TestResult(
                        id: 1,
                        testSessionId: 1,
                        userId: 1,
                        iqScore: 115,
                        percentileRank: 80.0,
                        totalQuestions: 20,
                        correctAnswers: 16,
                        accuracyPercentage: 80.0,
                        completionTimeSeconds: 1350,
                        completedAt: Date().addingTimeInterval(-86400 * 180)
                    ),
                    TestResult(
                        id: 2,
                        testSessionId: 2,
                        userId: 1,
                        iqScore: 113,
                        percentileRank: 78.0,
                        totalQuestions: 20,
                        correctAnswers: 16,
                        accuracyPercentage: 80.0,
                        completionTimeSeconds: 1380,
                        completedAt: Date().addingTimeInterval(-86400 * 90)
                    ),
                    TestResult(
                        id: 3,
                        testSessionId: 3,
                        userId: 1,
                        iqScore: 117,
                        percentileRank: 82.0,
                        totalQuestions: 20,
                        correctAnswers: 17,
                        accuracyPercentage: 85.0,
                        completionTimeSeconds: 1320,
                        completedAt: Date()
                    )
                ]
            )
        )
        .padding()
    }
}
