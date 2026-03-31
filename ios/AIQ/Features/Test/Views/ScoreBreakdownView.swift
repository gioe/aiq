import SwiftUI

/// Detailed score breakdown view for a completed test result.
///
/// Displays a summary card with key statistics and a full domain-by-domain
/// breakdown when domain scores are available. Navigated to from
/// `TestResultsView` via the "View Detailed Breakdown" button.
struct ScoreBreakdownView: View {
    let result: SubmittedTestResult

    @State private var showAnimation = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // Summary card with key stats
                summaryCard

                // Domain scores breakdown (or empty state)
                if let domainScores = result.domainScoresConverted {
                    DomainScoresBreakdownView(
                        domainScores: domainScores,
                        showAnimation: showAnimation,
                        strongestDomain: result.strongestDomain,
                        weakestDomain: result.weakestDomain
                    )
                } else {
                    domainBreakdownUnavailableCard
                }
            }
            .padding(DesignSystem.Spacing.lg)
        }
        .background(theme.colors.backgroundGrouped)
        .navigationTitle("Score Breakdown")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if reduceMotion {
                showAnimation = true
            } else {
                withAnimation(theme.animations.smooth.delay(0.1)) {
                    showAnimation = true
                }
            }
        }
    }

    // MARK: - Summary Card

    private var summaryCard: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Row 1: AIQ Score and Accuracy
            HStack(spacing: DesignSystem.Spacing.md) {
                summaryMetricCard(
                    title: "AIQ Score",
                    value: "\(result.iqScore)",
                    color: theme.colors.primary
                )

                summaryMetricCard(
                    title: "Accuracy",
                    value: String(format: "%.1f%%", result.accuracyPercentage),
                    color: theme.colors.statGreen
                )
            }

            // Row 2: Correct count and Percentile (or Time as fallback)
            HStack(spacing: DesignSystem.Spacing.md) {
                summaryMetricCard(
                    title: "Correct",
                    value: "\(result.correctAnswers)/\(result.totalQuestions)",
                    color: theme.colors.statBlue
                )

                if let percentile = result.percentileRankFormatted {
                    summaryMetricCard(
                        title: "Percentile",
                        value: percentile,
                        color: theme.colors.statPurple
                    )
                } else {
                    summaryMetricCard(
                        title: "Time",
                        value: result.completionTimeFormatted ?? "N/A",
                        color: theme.colors.statOrange
                    )
                }
            }
        }
        .padding(DesignSystem.Spacing.lg)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.lg,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: theme.colors.background
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: reduceMotion ? 0 : (showAnimation ? 0 : 20))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Score summary")
    }

    private func summaryMetricCard(title: String, value: String, color: Color) -> some View {
        VStack(spacing: DesignSystem.Spacing.xs) {
            Text(value)
                .font(theme.typography.h3)
                .foregroundColor(color)
                .accessibilityHidden(true)

            Text(title)
                .font(theme.typography.captionMedium)
                .foregroundColor(theme.colors.textSecondary)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DesignSystem.Spacing.xl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: theme.colors.backgroundSecondary
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value)")
    }

    // MARK: - Domain Breakdown Unavailable Card

    private var domainBreakdownUnavailableCard: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            Image(systemName: "chart.bar.xaxis")
                .font(.system(size: theme.iconSizes.lg))
                .foregroundColor(theme.colors.textTertiary)
                .accessibilityHidden(true)

            Text("Domain breakdown not available")
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.textTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(DesignSystem.Spacing.xxl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: theme.colors.background
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .accessibilityLabel("Domain breakdown not available")
    }
}

#if DEBUG

    // MARK: - Previews

    #Preview("No Domain Scores (High Score)") {
        NavigationStack {
            ScoreBreakdownView(
                result: MockDataFactory.makeTestResult(
                    id: 1,
                    testSessionId: 123,
                    userId: 1,
                    iqScore: 128,
                    totalQuestions: 20,
                    correctAnswers: 17,
                    accuracyPercentage: 85.0,
                    completedAt: Date()
                )
            )
        }
    }

    #Preview("Without Domain Scores") {
        NavigationStack {
            ScoreBreakdownView(
                result: MockDataFactory.makeTestResult(
                    id: 2,
                    testSessionId: 124,
                    userId: 1,
                    iqScore: 105,
                    totalQuestions: 20,
                    correctAnswers: 14,
                    accuracyPercentage: 70.0,
                    completedAt: Date()
                )
            )
        }
    }

    #Preview("High Score") {
        NavigationStack {
            ScoreBreakdownView(
                result: MockDataFactory.makeTestResult(
                    id: 3,
                    testSessionId: 125,
                    userId: 1,
                    iqScore: 145,
                    totalQuestions: 20,
                    correctAnswers: 19,
                    accuracyPercentage: 95.0,
                    completedAt: Date()
                )
            )
        }
    }

    #Preview("With Domain Scores") {
        NavigationStack {
            ScoreBreakdownView(
                result: MockDataFactory.makeTestResult(
                    id: 100,
                    testSessionId: 200,
                    userId: 1,
                    iqScore: 118,
                    totalQuestions: 20,
                    correctAnswers: 15,
                    accuracyPercentage: 75.0,
                    completedAt: Date(),
                    domainScores: MockDataFactory.makeDomainScoresPayload([
                        "pattern": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 92.0),
                        "logic": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 68.0),
                        "spatial": DomainScore(correct: 2, total: 4, pct: 50.0, percentile: 45.0),
                        "math": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 72.0),
                        "verbal": DomainScore(correct: 2, total: 2, pct: 100.0, percentile: 88.0),
                        "memory": DomainScore(correct: 1, total: 2, pct: 50.0, percentile: 40.0)
                    ])
                )
            )
        }
    }

#endif
