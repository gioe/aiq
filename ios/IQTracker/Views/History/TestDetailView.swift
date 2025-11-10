import SwiftUI

/// Detailed view for a past test result from history
// swiftlint:disable:this type_body_length file_length
struct TestDetailView: View {
    let testResult: TestResult
    let userAverage: Int?

    @Environment(\.dismiss) private var dismiss
    @State private var showAnimation = false

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

            // IQ Score
            VStack(spacing: 8) {
                Text("IQ Score")
                    .font(.headline)
                    .foregroundColor(.secondary)

                Text("\(testResult.iqScore)")
                    .font(.system(size: 72, weight: .bold, design: .rounded))
                    .foregroundStyle(scoreGradient)
                    .scaleEffect(showAnimation ? 1.0 : 0.8)
                    .opacity(showAnimation ? 1.0 : 0.0)

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

    // MARK: - Computed Properties

    private var scoreColor: Color {
        switch testResult.iqScore {
        case 130...:
            .green
        case 115 ..< 130:
            .blue
        case 85 ..< 115:
            .cyan
        case 70 ..< 85:
            .orange
        default:
            .red
        }
    }

    private var scoreGradient: LinearGradient {
        let colors: [Color] = switch testResult.iqScore {
        case 130...:
            [.green, .mint]
        case 115 ..< 130:
            [.blue, .cyan]
        case 85 ..< 115:
            [.cyan, .blue]
        case 70 ..< 85:
            [.orange, .yellow]
        default:
            [.red, .orange]
        }

        return LinearGradient(
            colors: colors,
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    private var scoreIconName: String {
        switch testResult.iqScore {
        case 130...:
            "star.fill"
        case 115 ..< 130:
            "rosette"
        case 85 ..< 115:
            "circle.fill"
        default:
            "circle"
        }
    }

    private var iqRangeDescription: String {
        switch testResult.iqScore {
        case 0 ..< 70:
            "Extremely Low"
        case 70 ..< 85:
            "Below Average"
        case 85 ..< 115:
            "Average"
        case 115 ..< 130:
            "Above Average"
        case 130 ..< 145:
            "Gifted"
        case 145...:
            "Highly Gifted"
        default:
            "Invalid Score"
        }
    }

    private var comparisonIcon: String {
        guard let average = userAverage else { return "equal.circle.fill" }
        if testResult.iqScore > average {
            return "arrow.up.circle.fill"
        } else if testResult.iqScore < average {
            return "arrow.down.circle.fill"
        } else {
            return "equal.circle.fill"
        }
    }

    private var comparisonColor: Color {
        guard let average = userAverage else { return .gray }
        if testResult.iqScore > average {
            return .green
        } else if testResult.iqScore < average {
            return .orange
        } else {
            return .blue
        }
    }

    private var comparisonText: String {
        guard let average = userAverage else { return "Only test result" }
        if testResult.iqScore > average {
            return "Above your average"
        } else if testResult.iqScore < average {
            return "Below your average"
        } else {
            return "Equal to your average"
        }
    }

    private var comparisonDifference: String {
        guard let average = userAverage else { return "" }
        let diff = abs(testResult.iqScore - average)
        if testResult.iqScore > average {
            return "+\(diff)"
        } else if testResult.iqScore < average {
            return "-\(diff)"
        } else {
            return "±0"
        }
    }

    private var performanceIcon: String {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return "star.circle.fill"
        case 75 ..< 90:
            return "hand.thumbsup.fill"
        case 60 ..< 75:
            return "checkmark.circle.fill"
        case 50 ..< 60:
            return "arrow.up.circle.fill"
        default:
            return "book.fill"
        }
    }

    private var performanceColor: Color {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return .green
        case 75 ..< 90:
            return .blue
        case 60 ..< 75:
            return .cyan
        case 50 ..< 60:
            return .orange
        default:
            return .red
        }
    }

    private var performanceTitle: String {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return "Outstanding Performance"
        case 75 ..< 90:
            return "Great Job"
        case 60 ..< 75:
            return "Good Effort"
        case 50 ..< 60:
            return "Keep Practicing"
        default:
            return "Room for Improvement"
        }
    }

    private var performanceDescription: String {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return "You've demonstrated excellent problem-solving abilities with this test. " +
                "Your performance shows strong cognitive skills."
        case 75 ..< 90:
            return "Your performance shows strong analytical skills. " +
                "You're doing well and demonstrating solid understanding."
        case 60 ..< 75:
            return "You're making good progress. " +
                "Consider reviewing the areas you found challenging to further improve."
        case 50 ..< 60:
            return "You're building your skills. " +
                "Regular practice and reviewing difficult concepts will help you improve."
        default:
            return "There's room to grow. " +
                "Focus on understanding the patterns and practicing regularly to build your skills."
        }
    }

    // MARK: - Helper Methods

    private func formatFullDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .long
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }

    private func formatAverageTime(_ totalSeconds: Int, questions: Int) -> String {
        let avgSeconds = Double(totalSeconds) / Double(questions)
        let minutes = Int(avgSeconds) / 60
        let seconds = Int(avgSeconds) % 60

        if minutes > 0 {
            return String(format: "%d:%02d per question", minutes, seconds)
        } else {
            return String(format: "%d sec per question", seconds)
        }
    }
}

// MARK: - Preview

#Preview("High Score") {
    NavigationStack {
        TestDetailView(
            testResult: TestResult(
                id: 1,
                testSessionId: 123,
                userId: 1,
                iqScore: 135,
                totalQuestions: 20,
                correctAnswers: 18,
                accuracyPercentage: 90.0,
                completionTimeSeconds: 1200,
                completedAt: Date()
            ),
            userAverage: 120
        )
    }
}

#Preview("Average Score") {
    NavigationStack {
        TestDetailView(
            testResult: TestResult(
                id: 2,
                testSessionId: 124,
                userId: 1,
                iqScore: 105,
                totalQuestions: 20,
                correctAnswers: 14,
                accuracyPercentage: 70.0,
                completionTimeSeconds: 1500,
                completedAt: Date().addingTimeInterval(-86400 * 7)
            ),
            userAverage: 110
        )
    }
}

#Preview("First Test (No Average)") {
    NavigationStack {
        TestDetailView(
            testResult: TestResult(
                id: 3,
                testSessionId: 125,
                userId: 1,
                iqScore: 115,
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
