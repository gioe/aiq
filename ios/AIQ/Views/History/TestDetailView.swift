import SwiftUI

/// Detailed view for a past test result from history
struct TestDetailView: View {
    let testResult: TestResult
    let userAverage: Int?

    @Environment(\.dismiss) private var dismiss
    @State private var showAnimation = false
    @State private var showConfidenceIntervalInfo = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // IQ Score - Main highlight
                iqScoreCard

                // Performance comparison (if user has multiple tests)
                if let average = userAverage, testResult.iqScore != average {
                    comparisonCard
                }

                // Performance metrics
                metricsGrid

                // Performance interpretation
                performanceInterpretation

                // Detailed statistics
                statisticsSection
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Test Details")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            withAnimation(.spring(response: 0.6, dampingFraction: 0.7).delay(0.1)) {
                showAnimation = true
            }
        }
    }

    // MARK: - IQ Score Card

    private var iqScoreCard: some View {
        VStack(spacing: 16) {
            // Score badge icon
            Image(systemName: scoreIconName)
                .font(.system(size: 50))
                .foregroundStyle(scoreGradient)
                .scaleEffect(showAnimation ? 1.0 : 0.5)
                .opacity(showAnimation ? 1.0 : 0.0)
                .accessibilityHidden(true)

            // IQ Score
            VStack(spacing: 8) {
                Text("IQ Score")
                    .font(.headline)
                    .foregroundColor(.secondary)
                    .accessibilityHidden(true)

                Text("\(testResult.iqScore)")
                    .font(.system(size: 72, weight: .bold, design: .rounded))
                    .foregroundStyle(scoreGradient)
                    .scaleEffect(showAnimation ? 1.0 : 0.8)
                    .opacity(showAnimation ? 1.0 : 0.0)
                    .accessibilityLabel(testResult.scoreAccessibilityDescription)

                // Confidence interval display (when available)
                if let ci = testResult.confidenceInterval {
                    confidenceIntervalDisplay(ci)
                }

                // IQ Range classification
                Text(iqRangeDescription)
                    .font(.title3)
                    .fontWeight(.semibold)
                    .foregroundColor(scoreColor)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(scoreColor.opacity(0.1))
                    .cornerRadius(8)
            }

            // Test date
            Text(formatFullDate(testResult.completedAt))
                .font(.subheadline)
                .foregroundColor(.secondary)
                .opacity(showAnimation ? 1.0 : 0.0)
        }
        .padding(24)
        .frame(maxWidth: .infinity)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 8, x: 0, y: 2)
    }

    // MARK: - Confidence Interval Display

    @ViewBuilder
    private func confidenceIntervalDisplay(_ ci: ConfidenceInterval) -> some View {
        VStack(spacing: 8) {
            HStack(spacing: 4) {
                Text("Range: \(ci.rangeFormatted)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                Button {
                    showConfidenceIntervalInfo = true
                } label: {
                    Image(systemName: "info.circle")
                        .font(.system(size: DesignSystem.IconSize.sm))
                        .foregroundColor(.accentColor)
                }
                .accessibilityLabel("Learn about score range")
                .accessibilityHint("Shows explanation of confidence interval")
            }
            .scaleEffect(showAnimation ? 1.0 : 0.9)
            .opacity(showAnimation ? 1.0 : 0.0)
        }
        .alert("Understanding Your Score Range", isPresented: $showConfidenceIntervalInfo) {
            Button("Got it", role: .cancel) {}
        } message: {
            Text(confidenceIntervalExplanation)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(ci.accessibilityDescription)
    }

    /// Explanation text for the confidence interval info alert
    private var confidenceIntervalExplanation: String {
        guard let ci = testResult.confidenceInterval else {
            return "No confidence interval available."
        }
        let confidenceText = "\(ci.confidencePercentage)% confidence"
        return """
        Your score of \(testResult.iqScore) represents our best estimate of your cognitive ability.

        Due to the nature of measurement, your true ability likely falls between \
        \(ci.lower) and \(ci.upper) (\(confidenceText)).

        This range accounts for normal variation in test performance.
        """
    }

    // MARK: - Comparison Card

    private var comparisonCard: some View {
        HStack(spacing: 16) {
            Image(systemName: comparisonIcon)
                .font(.title2)
                .foregroundColor(comparisonColor)

            VStack(alignment: .leading, spacing: 4) {
                Text(comparisonText)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)

                Text("Your average: \(userAverage!)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Text(comparisonDifference)
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(comparisonColor)
        }
        .padding()
        .background(comparisonColor.opacity(0.1))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(comparisonColor.opacity(0.3), lineWidth: 1)
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 10)
    }

    // MARK: - Metrics Grid

    private var metricsGrid: some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                metricCard(
                    icon: "percent",
                    title: "Accuracy",
                    value: String(format: "%.1f%%", testResult.accuracyPercentage),
                    color: .green
                )

                metricCard(
                    icon: "checkmark.circle.fill",
                    title: "Correct",
                    value: "\(testResult.correctAnswers)/\(testResult.totalQuestions)",
                    color: .blue
                )
            }

            HStack(spacing: 12) {
                metricCard(
                    icon: "clock.fill",
                    title: "Time Taken",
                    value: testResult.completionTimeFormatted,
                    color: .orange
                )

                metricCard(
                    icon: "xmark.circle.fill",
                    title: "Incorrect",
                    value: "\(testResult.totalQuestions - testResult.correctAnswers)",
                    color: .red
                )
            }
        }
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    private func metricCard(icon: String, title: String, value: String, color: Color) -> some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundColor(color)

            VStack(spacing: 4) {
                Text(value)
                    .font(.title3)
                    .fontWeight(.semibold)

                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 1)
    }

    // MARK: - Performance Interpretation

    private var performanceInterpretation: some View {
        VStack(spacing: 12) {
            Image(systemName: performanceIcon)
                .font(.system(size: 32))
                .foregroundColor(performanceColor)

            Text(performanceTitle)
                .font(.headline)

            Text(performanceDescription)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(performanceColor.opacity(0.1))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(performanceColor.opacity(0.3), lineWidth: 1)
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    // MARK: - Statistics Section

    private var statisticsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Additional Details")
                .font(.headline)
                .padding(.horizontal, 4)

            VStack(spacing: 0) {
                statisticRow(
                    label: "Test Session ID",
                    value: "#\(testResult.testSessionId)"
                )

                Divider()

                statisticRow(
                    label: "Questions Answered",
                    value: "\(testResult.totalQuestions)"
                )

                Divider()

                statisticRow(
                    label: "Success Rate",
                    value: String(format: "%.0f%%", testResult.accuracyPercentage)
                )

                if let time = testResult.completionTimeSeconds {
                    Divider()

                    statisticRow(
                        label: "Average Time per Question",
                        value: formatAverageTime(time, questions: testResult.totalQuestions)
                    )
                }
            }
            .background(Color(.systemBackground))
            .cornerRadius(12)
            .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 1)
        }
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    private func statisticRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundColor(.secondary)

            Spacer()

            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(.primary)
        }
        .padding()
    }
}

// MARK: - Preview

#Preview("High Score - With CI") {
    NavigationStack {
        TestDetailView(
            testResult: TestResult(
                id: 1,
                testSessionId: 123,
                userId: 1,
                iqScore: 135,
                percentileRank: 98.0,
                totalQuestions: 20,
                correctAnswers: 18,
                accuracyPercentage: 90.0,
                completionTimeSeconds: 1200,
                completedAt: Date(),
                confidenceInterval: ConfidenceInterval(
                    lower: 128,
                    upper: 142,
                    confidenceLevel: 0.95,
                    standardError: 3.5
                )
            ),
            userAverage: 120
        )
    }
}

#Preview("Average Score - With CI") {
    NavigationStack {
        TestDetailView(
            testResult: TestResult(
                id: 2,
                testSessionId: 124,
                userId: 1,
                iqScore: 105,
                percentileRank: 65.0,
                totalQuestions: 20,
                correctAnswers: 14,
                accuracyPercentage: 70.0,
                completionTimeSeconds: 1500,
                completedAt: Date().addingTimeInterval(-86400 * 7),
                confidenceInterval: ConfidenceInterval(
                    lower: 98,
                    upper: 112,
                    confidenceLevel: 0.95,
                    standardError: 3.5
                )
            ),
            userAverage: 110
        )
    }
}

#Preview("First Test - No CI") {
    NavigationStack {
        TestDetailView(
            testResult: TestResult(
                id: 3,
                testSessionId: 125,
                userId: 1,
                iqScore: 115,
                percentileRank: 80.0,
                totalQuestions: 20,
                correctAnswers: 16,
                accuracyPercentage: 80.0,
                completionTimeSeconds: 1350,
                completedAt: Date().addingTimeInterval(-86400 * 30)
            ),
            userAverage: nil
        )
    }
}
