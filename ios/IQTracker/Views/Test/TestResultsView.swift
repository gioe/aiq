import SwiftUI

struct TestResultsView: View {
    let result: SubmittedTestResult
    let onDismiss: () -> Void

    @State private var showAnimation = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: DesignSystem.Spacing.xxxl) {
                    // IQ Score - Main highlight
                    iqScoreCard

                    // Percentile ranking (if available)
                    if result.percentileRank != nil {
                        percentileCard(
                            percentileRank: result.percentileRank,
                            showAnimation: showAnimation
                        )
                    }

                    // Performance metrics
                    metricsGrid

                    // Performance message
                    performanceMessage

                    // Action buttons
                    actionButtons
                }
                .padding(DesignSystem.Spacing.lg)
            }
            .background(ColorPalette.backgroundGrouped)
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
                withAnimation(DesignSystem.Animation.smooth.delay(0.1)) {
                    showAnimation = true
                }
            }
        }
    }

    // MARK: - IQ Score Card

    private var iqScoreCard: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            // Trophy icon
            Image(systemName: "trophy.fill")
                .font(.system(size: DesignSystem.IconSize.xl))
                .foregroundStyle(ColorPalette.trophyGradient)
                .scaleEffect(showAnimation ? 1.0 : 0.5)
                .opacity(showAnimation ? 1.0 : 0.0)
                .accessibilityHidden(true) // Decorative icon

            // IQ Score
            VStack(spacing: DesignSystem.Spacing.xs) {
                Text("Your IQ Score")
                    .font(Typography.h3)
                    .foregroundColor(ColorPalette.textSecondary)
                    .accessibilityHidden(true) // Redundant with full label below

                Text("\(result.iqScore)")
                    .font(Typography.scoreDisplay)
                    .foregroundStyle(ColorPalette.scoreGradient)
                    .scaleEffect(showAnimation ? 1.0 : 0.8)
                    .opacity(showAnimation ? 1.0 : 0.0)
                    .accessibilityLabel("Your IQ Score is \(result.iqScore)")
                    .accessibilityHint(iqRangeDescription)
            }

            // IQ Range context
            Text(iqRangeDescription)
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignSystem.Spacing.lg)
                .opacity(showAnimation ? 1.0 : 0.0)
                .accessibilityHidden(true) // Already included in hint above

            // Disclaimer
            Text("This is a cognitive performance assessment for personal insight, not a clinical IQ test.")
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textTertiary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignSystem.Spacing.lg)
                .padding(.top, DesignSystem.Spacing.sm)
                .opacity(showAnimation ? 1.0 : 0.0)
        }
        .padding(DesignSystem.Spacing.xxl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.lg,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: ColorPalette.background
        )
        .accessibilityElement(children: .combine)
    }

    // MARK: - Metrics Grid

    private var metricsGrid: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            HStack(spacing: DesignSystem.Spacing.md) {
                metricCard(
                    icon: "percent",
                    title: "Accuracy",
                    value: String(format: "%.1f%%", result.accuracyPercentage),
                    color: ColorPalette.statGreen
                )

                metricCard(
                    icon: "checkmark.circle.fill",
                    title: "Correct",
                    value: "\(result.correctAnswers)/\(result.totalQuestions)",
                    color: ColorPalette.statBlue
                )
            }

            HStack(spacing: DesignSystem.Spacing.md) {
                metricCard(
                    icon: "clock.fill",
                    title: "Time",
                    value: result.completionTimeFormatted,
                    color: ColorPalette.statOrange
                )

                metricCard(
                    icon: "calendar",
                    title: "Completed",
                    value: formatDate(result.completedAt),
                    color: ColorPalette.statPurple
                )
            }
        }
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    private func metricCard(icon: String, title: String, value: String, color: Color) -> some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.md))
                .foregroundColor(color)
                .accessibilityHidden(true) // Decorative icon

            VStack(spacing: DesignSystem.Spacing.xs) {
                Text(value)
                    .font(Typography.h3)
                    .foregroundColor(ColorPalette.textPrimary)
                    .accessibilityHidden(true)

                Text(title)
                    .font(Typography.captionMedium)
                    .foregroundColor(ColorPalette.textSecondary)
                    .accessibilityHidden(true)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DesignSystem.Spacing.xl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: ColorPalette.background
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value)")
    }

    // MARK: - Performance Message

    private var performanceMessage: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            Text(performanceTitle)
                .font(Typography.h3)

            Text(performanceDescription)
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(DesignSystem.Spacing.lg)
        .frame(maxWidth: .infinity)
        .background(performanceBackgroundColor.opacity(0.1))
        .cornerRadius(DesignSystem.CornerRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                .stroke(performanceBackgroundColor.opacity(0.3), lineWidth: 1)
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
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
                .font(Typography.button)
            }
            .buttonStyle(.bordered)
            .accessibilityLabel("View Detailed Breakdown")
            .accessibilityHint("See question-by-question analysis of your test performance")

            Button {
                onDismiss()
            } label: {
                Text("Return to Dashboard")
                    .font(Typography.button)
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
            percentileRank: 98.5,
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
            percentileRank: 63.2,
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
            percentileRank: 21.8,
            totalQuestions: 20,
            correctAnswers: 9,
            accuracyPercentage: 45.0,
            completionTimeSeconds: 1523,
            completedAt: Date()
        ),
        onDismiss: {}
    )
}
