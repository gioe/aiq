import SwiftUI

struct TestResultsView: View {
    let result: SubmittedTestResult
    let onDismiss: () -> Void

    @State private var showAnimation = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 32) {
                    // IQ Score - Main highlight
                    iqScoreCard

                    // Performance metrics
                    metricsGrid

                    // Performance message
                    performanceMessage

                    // Action buttons
                    actionButtons
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Test Results")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        onDismiss()
                    }
                    .accessibilityLabel("Done")
                    .accessibilityHint("Return to dashboard")
                }
            }
            .onAppear {
                withAnimation(.spring(response: 0.6, dampingFraction: 0.7).delay(0.1)) {
                    showAnimation = true
                }
            }
        }
    }

    // MARK: - IQ Score Card

    private var iqScoreCard: some View {
        VStack(spacing: 16) {
            // Trophy icon
            Image(systemName: "trophy.fill")
                .font(.system(size: 50))
                .foregroundStyle(
                    LinearGradient(
                        colors: [.yellow, .orange],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .scaleEffect(showAnimation ? 1.0 : 0.5)
                .opacity(showAnimation ? 1.0 : 0.0)
                .accessibilityHidden(true) // Decorative icon

            // IQ Score
            VStack(spacing: 4) {
                Text("Your IQ Score")
                    .font(.headline)
                    .foregroundColor(.secondary)
                    .accessibilityHidden(true) // Redundant with full label below

                Text("\(result.iqScore)")
                    .font(.system(size: 72, weight: .bold, design: .rounded))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [.blue, .purple],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .scaleEffect(showAnimation ? 1.0 : 0.8)
                    .opacity(showAnimation ? 1.0 : 0.0)
                    .accessibilityLabel("Your IQ Score is \(result.iqScore)")
                    .accessibilityHint(iqRangeDescription)
            }

            // IQ Range context
            Text(iqRangeDescription)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
                .opacity(showAnimation ? 1.0 : 0.0)
                .accessibilityHidden(true) // Already included in hint above
        }
        .padding(24)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 8, x: 0, y: 2)
        .accessibilityElement(children: .combine)
    }

    // MARK: - Metrics Grid

    private var metricsGrid: some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                metricCard(
                    icon: "percent",
                    title: "Accuracy",
                    value: String(format: "%.1f%%", result.accuracyPercentage),
                    color: .green
                )

                metricCard(
                    icon: "checkmark.circle.fill",
                    title: "Correct",
                    value: "\(result.correctAnswers)/\(result.totalQuestions)",
                    color: .blue
                )
            }

            HStack(spacing: 12) {
                metricCard(
                    icon: "clock.fill",
                    title: "Time",
                    value: result.completionTimeFormatted,
                    color: .orange
                )

                metricCard(
                    icon: "calendar",
                    title: "Completed",
                    value: formatDate(result.completedAt),
                    color: .purple
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
                .accessibilityHidden(true) // Decorative icon

            VStack(spacing: 4) {
                Text(value)
                    .font(.title3)
                    .fontWeight(.semibold)
                    .accessibilityHidden(true)

                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .accessibilityHidden(true)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 1)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value)")
    }

    // MARK: - Performance Message

    private var performanceMessage: some View {
        VStack(spacing: 12) {
            Text(performanceTitle)
                .font(.headline)

            Text(performanceDescription)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(performanceBackgroundColor.opacity(0.1))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(performanceBackgroundColor.opacity(0.3), lineWidth: 1)
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        VStack(spacing: 12) {
            Button {
                // swiftlint:disable:next todo
                // TODO: Navigate to detailed breakdown (future feature)
                print("View detailed breakdown")
            } label: {
                HStack {
                    Image(systemName: "chart.bar.fill")
                    Text("View Detailed Breakdown")
                }
                .frame(maxWidth: .infinity)
                .fontWeight(.semibold)
            }
            .buttonStyle(.bordered)
            .accessibilityLabel("View Detailed Breakdown")
            .accessibilityHint("See question-by-question analysis of your test performance")

            Button {
                onDismiss()
            } label: {
                Text("Return to Dashboard")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .accessibilityLabel("Return to Dashboard")
            .accessibilityHint("Go back to the main dashboard")
        }
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    // MARK: - Computed Properties

    private var iqRangeDescription: String {
        switch result.iqScore {
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

    private var performanceTitle: String {
        let accuracy = result.accuracyPercentage

        switch accuracy {
        case 90...:
            return "Outstanding Performance! 🌟"
        case 75 ..< 90:
            return "Great Job! 👏"
        case 60 ..< 75:
            return "Good Effort! 👍"
        case 50 ..< 60:
            return "Keep Practicing! 💪"
        default:
            return "Room for Improvement! 📚"
        }
    }

    private var performanceDescription: String {
        let accuracy = result.accuracyPercentage

        switch accuracy {
        case 90...:
            return "You've demonstrated excellent problem-solving abilities. Keep challenging yourself!"
        case 75 ..< 90:
            return "Your performance shows strong analytical skills. You're doing well!"
        case 60 ..< 75:
            return "You're making good progress. Consider reviewing the areas you found challenging."
        case 50 ..< 60:
            return "You're building your skills. Regular practice will help you improve."
        default:
            return "Everyone starts somewhere. Focus on understanding the patterns and keep practicing."
        }
    }

    private var performanceBackgroundColor: Color {
        let accuracy = result.accuracyPercentage

        switch accuracy {
        case 90...:
            return .green
        case 75 ..< 90:
            return .blue
        case 60 ..< 75:
            return .orange
        default:
            return .red
        }
    }

    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

// MARK: - Preview

#Preview("Excellent Score") {
    TestResultsView(
        result: SubmittedTestResult(
            id: 1,
            testSessionId: 123,
            userId: 1,
            iqScore: 142,
            totalQuestions: 20,
            correctAnswers: 19,
            accuracyPercentage: 95.0,
            completionTimeSeconds: 842,
            completedAt: Date()
        ),
        onDismiss: {}
    )
}

#Preview("Average Score") {
    TestResultsView(
        result: SubmittedTestResult(
            id: 2,
            testSessionId: 124,
            userId: 1,
            iqScore: 105,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completionTimeSeconds: 1023,
            completedAt: Date()
        ),
        onDismiss: {}
    )
}

#Preview("Low Score") {
    TestResultsView(
        result: SubmittedTestResult(
            id: 3,
            testSessionId: 125,
            userId: 1,
            iqScore: 88,
            totalQuestions: 20,
            correctAnswers: 9,
            accuracyPercentage: 45.0,
            completionTimeSeconds: 1523,
            completedAt: Date()
        ),
        onDismiss: {}
    )
}
