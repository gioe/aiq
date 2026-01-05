import SwiftUI

struct TestResultsView: View {
    let result: SubmittedTestResult
    let onDismiss: () -> Void

    @State private var showAnimation = false
    @State private var showConfidenceIntervalInfo = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion

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

                    // Domain scores breakdown
                    if result.domainScores != nil {
                        DomainScoresBreakdownView(
                            domainScores: result.domainScores,
                            showAnimation: showAnimation,
                            strongestDomain: result.strongestDomain,
                            weakestDomain: result.weakestDomain
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
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestResultsView.doneButton)
                }
            }
            .onAppear {
                if reduceMotion {
                    showAnimation = true
                } else {
                    withAnimation(DesignSystem.Animation.smooth.delay(0.1)) {
                        showAnimation = true
                    }
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
                .scaleEffect(reduceMotion ? 1.0 : (showAnimation ? 1.0 : 0.5))
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
                    .scaleEffect(reduceMotion ? 1.0 : (showAnimation ? 1.0 : 0.8))
                    .opacity(showAnimation ? 1.0 : 0.0)
                    .accessibilityLabel(result.scoreAccessibilityDescription)
                    .accessibilityHint(iqRangeDescription)
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestResultsView.scoreLabel)

                // Confidence Interval display (when available)
                if let ci = result.confidenceInterval {
                    confidenceIntervalDisplay(ci)
                }
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

    // MARK: - Confidence Interval Display

    @ViewBuilder
    private func confidenceIntervalDisplay(_ ci: ConfidenceInterval) -> some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            HStack(spacing: DesignSystem.Spacing.xs) {
                Text("Range: \(ci.rangeFormatted)")
                    .font(Typography.bodyMedium)
                    .foregroundColor(ColorPalette.textSecondary)

                Button {
                    showConfidenceIntervalInfo = true
                } label: {
                    Image(systemName: "info.circle")
                        .font(.system(size: DesignSystem.IconSize.sm))
                        .foregroundColor(ColorPalette.primary)
                }
                .accessibilityLabel("Learn about score range")
                .accessibilityHint("Shows explanation of confidence interval")
            }
            .scaleEffect(reduceMotion ? 1.0 : (showAnimation ? 1.0 : 0.9))
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
        guard let ci = result.confidenceInterval else {
            return "No confidence interval available."
        }
        let confidenceText = "\(ci.confidencePercentage)% confidence"
        return """
        Your score of \(result.iqScore) represents our best estimate of your cognitive ability.

        Due to the nature of measurement, your true ability likely falls between \
        \(ci.lower) and \(ci.upper) (\(confidenceText)).

        This range accounts for normal variation in test performance.
        """
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
        .offset(y: reduceMotion ? 0 : (showAnimation ? 0 : 20))
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
        .offset(y: reduceMotion ? 0 : (showAnimation ? 0 : 20))
        .accessibilityIdentifier(AccessibilityIdentifiers.TestResultsView.performanceLabel)
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
        .offset(y: reduceMotion ? 0 : (showAnimation ? 0 : 20))
    }

    // MARK: - Computed Properties

    private var iqRangeDescription: String {
        IQScoreUtility.classify(result.iqScore).description
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

#Preview("Excellent Score - With CI") {
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
            completedAt: Date(),
            responseTimeFlags: nil,
            domainScores: [
                "pattern": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 97.5),
                "logic": DomainScore(correct: 3, total: 3, pct: 100.0, percentile: 95.0),
                "spatial": DomainScore(correct: 3, total: 3, pct: 100.0, percentile: 93.5),
                "math": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 96.0),
                "verbal": DomainScore(correct: 3, total: 3, pct: 100.0, percentile: 94.5),
                "memory": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 55.0)
            ],
            strongestDomain: "pattern",
            weakestDomain: "memory",
            confidenceInterval: ConfidenceInterval(
                lower: 135,
                upper: 149,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        ),
        onDismiss: {}
    )
}

#Preview("Average Score - With CI") {
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
            completedAt: Date(),
            responseTimeFlags: nil,
            domainScores: [
                "pattern": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 71.0),
                "logic": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 55.0),
                "spatial": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 52.0),
                "math": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 68.0),
                "verbal": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 48.0),
                "memory": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 50.0)
            ],
            strongestDomain: "pattern",
            weakestDomain: "verbal",
            confidenceInterval: ConfidenceInterval(
                lower: 98,
                upper: 112,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        ),
        onDismiss: {}
    )
}

#Preview("Low Score - With Wide CI") {
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
            completedAt: Date(),
            responseTimeFlags: nil,
            domainScores: [
                "pattern": DomainScore(correct: 1, total: 4, pct: 25.0, percentile: 12.0),
                "logic": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 45.0),
                "spatial": DomainScore(correct: 1, total: 3, pct: 33.3, percentile: 18.0),
                "math": DomainScore(correct: 2, total: 4, pct: 50.0, percentile: 32.0),
                "verbal": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 42.0),
                "memory": DomainScore(correct: 1, total: 3, pct: 33.3, percentile: 22.0)
            ],
            strongestDomain: "logic",
            weakestDomain: "pattern",
            confidenceInterval: ConfidenceInterval(
                lower: 75,
                upper: 101,
                confidenceLevel: 0.95,
                standardError: 6.7
            )
        ),
        onDismiss: {}
    )
}

#Preview("No CI - Legacy Data") {
    TestResultsView(
        result: SubmittedTestResult(
            id: 4,
            testSessionId: 126,
            userId: 1,
            iqScore: 100,
            percentileRank: 50.0,
            totalQuestions: 20,
            correctAnswers: 12,
            accuracyPercentage: 60.0,
            completionTimeSeconds: 900,
            completedAt: Date(),
            responseTimeFlags: nil,
            domainScores: [
                "pattern": DomainScore(correct: 2, total: 4, pct: 50.0, percentile: nil),
                "logic": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: nil),
                "spatial": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: nil),
                "math": DomainScore(correct: 2, total: 4, pct: 50.0, percentile: nil),
                "verbal": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: nil),
                "memory": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: nil)
            ],
            strongestDomain: nil,
            weakestDomain: nil,
            confidenceInterval: nil
        ),
        onDismiss: {}
    )
}

#Preview("No Domain Scores - With CI") {
    TestResultsView(
        result: SubmittedTestResult(
            id: 5,
            testSessionId: 127,
            userId: 1,
            iqScore: 100,
            percentileRank: 50.0,
            totalQuestions: 20,
            correctAnswers: 12,
            accuracyPercentage: 60.0,
            completionTimeSeconds: 900,
            completedAt: Date(),
            responseTimeFlags: nil,
            domainScores: nil,
            strongestDomain: nil,
            weakestDomain: nil,
            confidenceInterval: ConfidenceInterval(
                lower: 93,
                upper: 107,
                confidenceLevel: 0.95,
                standardError: 3.5
            )
        ),
        onDismiss: {}
    )
}
