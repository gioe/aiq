import AIQSharedKit
import SwiftUI

struct TestResultsView: View {
    let result: SubmittedTestResult
    let onDismiss: () -> Void
    let isFirstTest: Bool

    @State private var showScore = false
    @State private var showPercentile = false
    @State private var showMetrics = false
    @State private var showDomains = false
    @State private var showConfidenceIntervalInfo = false
    @State private var showNotificationSoftPrompt = false
    @State private var hasDismissed = false
    @ObservedObject private var notificationManager: NotificationManager = {
        let resolved: NotificationManagerProtocol = ServiceContainer.shared.resolve()
        guard let manager = resolved as? NotificationManager else {
            // In mock/test environments the registered type may not be NotificationManager.
            // Fall back to a fresh instance that uses whatever services are in the container.
            return NotificationManager()
        }
        return manager
    }()

    @EnvironmentObject private var router: AppRouter
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // IQ Score - Main highlight
                iqScoreCard

                // Percentile ranking (if available)
                if result.percentileRank != nil {
                    PercentileCard(
                        percentileRank: result.percentileRank,
                        showAnimation: showPercentile
                    )
                }

                // Performance metrics
                metricsGrid

                // Domain scores breakdown (at bottom for detailed review)
                if result.domainScoresConverted != nil {
                    DomainScoresBreakdownView(
                        domainScores: result.domainScoresConverted,
                        showAnimation: showDomains,
                        strongestDomain: result.strongestDomain,
                        weakestDomain: result.weakestDomain
                    )
                }

                // Model performance breakdown
                if let vendorGroups = result.vendorGroupedScores {
                    ModelPerformanceBreakdownView(
                        vendorGroups: vendorGroups,
                        showAnimation: showDomains
                    )
                }
            }
            .padding(DesignSystem.Spacing.lg)
        }
        .background(theme.colors.backgroundGrouped)
        .navigationTitle("Test Results")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Done") {
                    handleDismiss()
                }
                .accessibilityLabel("Done")
                .accessibilityHint("Return to dashboard")
                .accessibilityIdentifier(AccessibilityIdentifiers.TestResultsView.doneButton)
            }
        }
        .onAppear {
            // Trigger success haptic when results are displayed
            ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.success)

            if reduceMotion {
                showScore = true
                showPercentile = true
                showMetrics = true
                showDomains = true
            } else {
                withAnimation(theme.animations.smooth.delay(0.1)) {
                    showScore = true
                }
                withAnimation(theme.animations.smooth.delay(0.4)) {
                    showPercentile = true
                }
                withAnimation(theme.animations.smooth.delay(0.7)) {
                    showMetrics = true
                }
                withAnimation(theme.animations.smooth.delay(1.0)) {
                    showDomains = true
                }
            }
        }
        .sheet(isPresented: $showNotificationSoftPrompt) {
            NotificationSoftPromptView(
                onEnableReminders: {
                    Task {
                        await notificationManager.requestAuthorization()
                    }
                },
                onDismiss: {
                    // User declined - just dismiss
                }
            )
        }
        .onChange(of: showNotificationSoftPrompt) { isShowing in
            // When the soft prompt is dismissed, call the original onDismiss
            // Guard against double dismissal
            if !isShowing && !hasDismissed {
                hasDismissed = true
                onDismiss()
            }
        }
    }

    // MARK: - Helper Methods

    /// Handles dismissal of the results view, potentially showing the notification soft prompt
    private func handleDismiss() {
        // Guard against double dismissal
        guard !hasDismissed else { return }

        // Check if we should show the notification soft prompt
        if shouldShowNotificationPrompt() {
            showNotificationSoftPrompt = true
        } else {
            hasDismissed = true
            onDismiss()
        }
    }

    /// Determines if the notification soft prompt should be shown
    /// - Returns: True if this is the first test and permission hasn't been requested
    private func shouldShowNotificationPrompt() -> Bool {
        // Only show on first test
        guard isFirstTest else { return false }

        // Don't show if permission already requested
        guard !notificationManager.hasRequestedNotificationPermission else { return false }

        // Don't show if permission already granted
        guard notificationManager.authorizationStatus != .authorized else { return false }

        return true
    }

    // MARK: - IQ Score Card

    private var iqScoreCard: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            // Trophy icon
            Image(systemName: "trophy.fill")
                .font(.system(size: theme.iconSizes.xl))
                .foregroundStyle(theme.gradients.trophyGradient)
                .scaleEffect(reduceMotion ? 1.0 : (showScore ? 1.0 : 0.5))
                .opacity(showScore ? 1.0 : 0.0)
                .accessibilityHidden(true) // Decorative icon

            // IQ Score
            VStack(spacing: DesignSystem.Spacing.xs) {
                Text("Estimated AIQ Score")
                    .font(theme.typography.h3)
                    .foregroundColor(theme.colors.textSecondary)
                    .accessibilityHidden(true) // Redundant with full label below

                Text("\(result.iqScore)")
                    .scoreDisplayFont()
                    .foregroundStyle(theme.gradients.scoreGradient)
                    .scaleEffect(reduceMotion ? 1.0 : (showScore ? 1.0 : 0.8))
                    .opacity(showScore ? 1.0 : 0.0)
                    .accessibilityLabel(result.scoreAccessibilityDescription)
                    .accessibilityHint(iqRangeDescription)

                // Confidence Interval display (when available)
                if let ci = result.confidenceIntervalConverted {
                    confidenceIntervalDisplay(ci)
                }
            }

            // IQ Range context
            Text(iqRangeDescription)
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignSystem.Spacing.lg)
                .opacity(showScore ? 1.0 : 0.0)
                .accessibilityHidden(true) // Already included in hint above

            // Disclaimer
            Text("Scores are estimates based on a brief assessment and may vary between sessions.")
                .font(theme.typography.captionMedium)
                .foregroundColor(theme.colors.textTertiary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignSystem.Spacing.lg)
                .padding(.top, DesignSystem.Spacing.sm)
                .opacity(showScore ? 1.0 : 0.0)
        }
        .padding(DesignSystem.Spacing.xxl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.lg,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: theme.colors.background
        )
        // .accessibilityElement(children: .contain) forces the VStack to be a real
        // otherElement container in XCTest so that app.otherElements["testResultsView.scoreLabel"]
        // finds the card. With .combine the element becomes staticText when no interactive
        // children (e.g. no confidence-interval button) are present.
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.TestResultsView.scoreLabel)
    }

    // MARK: - Confidence Interval Display

    private func confidenceIntervalDisplay(_ ci: ConfidenceInterval) -> some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            HStack(spacing: DesignSystem.Spacing.xs) {
                Text("Range: \(ci.rangeFormatted)")
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)

                Button {
                    showConfidenceIntervalInfo = true
                } label: {
                    Image(systemName: "info.circle")
                        .font(.system(size: theme.iconSizes.sm))
                        .foregroundColor(theme.colors.primary)
                }
                .accessibilityLabel("Learn about score range")
                .accessibilityHint("Shows explanation of confidence interval")
            }
            .scaleEffect(reduceMotion ? 1.0 : (showScore ? 1.0 : 0.9))
            .opacity(showScore ? 1.0 : 0.0)
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
        guard let ci = result.confidenceIntervalConverted else {
            return "No confidence interval available."
        }
        let confidenceText = "\(ci.confidencePercentage)% confidence"
        return """
        Your estimated score of \(result.iqScore) reflects your performance on this assessment.

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
                    color: theme.colors.statGreen
                )

                metricCard(
                    icon: "checkmark.circle.fill",
                    title: "Correct",
                    value: "\(result.correctAnswers)/\(result.totalQuestions)",
                    color: theme.colors.statBlue
                )
            }

            HStack(spacing: DesignSystem.Spacing.md) {
                metricCard(
                    icon: "clock.fill",
                    title: "Time",
                    value: result.completionTimeFormatted ?? "N/A",
                    color: theme.colors.statOrange
                )

                metricCard(
                    icon: "calendar",
                    title: "Completed",
                    value: formatDate(result.completedAt),
                    color: theme.colors.statPurple
                )
            }
        }
        .opacity(showMetrics ? 1.0 : 0.0)
        .offset(y: reduceMotion ? 0 : (showMetrics ? 0 : 20))
    }

    private func metricCard(icon: String, title: String, value: String, color: Color) -> some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            Image(systemName: icon)
                .font(.system(size: theme.iconSizes.md))
                .foregroundColor(color)
                .accessibilityHidden(true) // Decorative icon

            VStack(spacing: DesignSystem.Spacing.xs) {
                Text(value)
                    .font(theme.typography.h3)
                    .foregroundColor(theme.colors.textPrimary)
                    .accessibilityHidden(true)

                Text(title)
                    .font(theme.typography.captionMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .accessibilityHidden(true)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DesignSystem.Spacing.xl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: theme.colors.background
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value)")
    }

    // MARK: - Computed Properties

    private var iqRangeDescription: String {
        IQScoreUtility.classify(result.iqScore).description
    }

    private func formatDate(_ date: Date) -> String {
        date.toCompactString()
    }
}

#if DebugBuild

    // MARK: - Preview

    #Preview("Excellent Score") {
        TestResultsView(
            result: MockDataFactory.makeTestResult(
                id: 1,
                testSessionId: 123,
                userId: 1,
                iqScore: 142,
                totalQuestions: 20,
                correctAnswers: 19,
                accuracyPercentage: 95.0,
                completedAt: Date()
            ),
            onDismiss: {},
            isFirstTest: false
        )
    }

    #Preview("Average Score") {
        TestResultsView(
            result: MockDataFactory.makeTestResult(
                id: 2,
                testSessionId: 124,
                userId: 1,
                iqScore: 105,
                totalQuestions: 20,
                correctAnswers: 14,
                accuracyPercentage: 70.0,
                completedAt: Date()
            ),
            onDismiss: {},
            isFirstTest: false
        )
    }

    #Preview("Low Score") {
        TestResultsView(
            result: MockDataFactory.makeTestResult(
                id: 3,
                testSessionId: 125,
                userId: 1,
                iqScore: 88,
                totalQuestions: 20,
                correctAnswers: 9,
                accuracyPercentage: 45.0,
                completedAt: Date()
            ),
            onDismiss: {},
            isFirstTest: false
        )
    }

    #Preview("Average IQ") {
        TestResultsView(
            result: MockDataFactory.makeTestResult(
                id: 4,
                testSessionId: 126,
                userId: 1,
                iqScore: 100,
                totalQuestions: 20,
                correctAnswers: 12,
                accuracyPercentage: 60.0,
                completedAt: Date()
            ),
            onDismiss: {},
            isFirstTest: false
        )
    }

    #Preview("First Test") {
        TestResultsView(
            result: MockDataFactory.makeTestResult(
                id: 5,
                testSessionId: 127,
                userId: 1,
                iqScore: 115,
                totalQuestions: 20,
                correctAnswers: 16,
                accuracyPercentage: 80.0,
                completedAt: Date()
            ),
            onDismiss: {},
            isFirstTest: true
        )
    }
#endif
