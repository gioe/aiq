import SwiftUI

/// List item component for displaying a single test result in history
struct TestHistoryListItem: View {
    let testResult: TestResult

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with IQ Score and Date
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("IQ Score")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Text("\(testResult.iqScore)")
                        .font(.system(size: 32, weight: .bold, design: .rounded))
                        .foregroundColor(scoreColor)

                    // Percentile badge (if available)
                    if let percentileText = testResult.percentileFormatted {
                        Text(percentileText)
                            .font(.caption.weight(.semibold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(
                                LinearGradient(
                                    colors: [Color.blue, Color.purple],
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .cornerRadius(6)
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text(testResult.completedAt, style: .date)
                        .font(.subheadline)
                        .foregroundColor(.primary)

                    Text(testResult.completedAt, style: .time)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            // Metrics Grid
            HStack(spacing: 16) {
                MetricView(
                    label: "Accuracy",
                    value: String(format: "%.0f%%", testResult.accuracyPercentage),
                    icon: "target"
                )

                MetricView(
                    label: "Correct",
                    value: "\(testResult.correctAnswers)/\(testResult.totalQuestions)",
                    icon: "checkmark.circle.fill"
                )

                MetricView(
                    label: "Time",
                    value: testResult.completionTimeFormatted,
                    icon: "clock.fill"
                )
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 4, x: 0, y: 2)
    }

    private var scoreColor: Color {
        switch testResult.iqScore {
        case 130...:
            .green
        case 120 ..< 130:
            .blue
        case 110 ..< 120:
            .cyan
        case 90 ..< 110:
            .orange
        default:
            .red
        }
    }
}

/// Small metric display component
private struct MetricView: View {
    let label: String
    let value: String
    let icon: String

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(.secondary)

            Text(value)
                .font(.subheadline.weight(.semibold))
                .foregroundColor(.primary)

            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

#Preview {
    let sampleResult = TestResult(
        id: 1,
        testSessionId: 1,
        userId: 1,
        iqScore: 125,
        percentileRank: 84.0,
        totalQuestions: 20,
        correctAnswers: 17,
        accuracyPercentage: 85.0,
        completionTimeSeconds: 1200,
        completedAt: Date()
    )

    return TestHistoryListItem(testResult: sampleResult)
        .padding()
}
