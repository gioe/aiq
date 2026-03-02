import SwiftUI

struct TestResultsView: View {
    let result: SubmittedTestResult
    let onDismiss: () -> Void
    let isFirstTest: Bool

    @State private var showAnimation = false
    @State private var showConfidenceIntervalInfo = false
    @State private var showNotificationSoftPrompt = false
    @State private var hasDismissed = false
    @ObservedObject private var notificationManager: NotificationManager = {
        let resolved = ServiceContainer.shared.resolve(NotificationManagerProtocol.self)
        guard let manager = resolved as? NotificationManager else {
            // In mock/test environments the registered type may not be NotificationManager.
            // Fall back to a fresh instance that uses whatever services are in the container.
            return NotificationManager()
        }
        return manager
    }()

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                // IQ Score - Main highlight
                iqScoreCard

                // Percentile ranking (if available)
                if result.percentileRank != nil {
                    PercentileCard(
                        percentileRank: result.percentileRank,
                        showAnimation: showAnimation
                    )
                }

                // Domain scores breakdown
                if result.domainScoresConverted != nil {
                    DomainScoresBreakdownView(
                        domainScores: result.domainScoresConverted,
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
                    handleDismiss()
                }
                .accessibilityLabel("Done")
                .accessibilityHint("Return to dashboard")
                .accessibilityIdentifier(AccessibilityIdentifiers.TestResultsView.doneButton)
            }
        }
        .onAppear {
            // Trigger success haptic when results are displayed
            ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.success)

            if reduceMotion {
                showAnimation = true
            } else {
                withAnimation(DesignSystem.Animation.smooth.delay(0.1)) {
                    showAnimation = true
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
                    .scoreDisplayFont()
                    .foregroundStyle(ColorPalette.scoreGradient)
                    .scaleEffect(reduceMotion ? 1.0 : (showAnimation ? 1.0 : 0.8))
                    .opacity(showAnimation ? 1.0 : 0.0)
                    .accessibilityLabel(result.scoreAccessibilityDescription)
                    .accessibilityHint(iqRangeDescription)

                // Confidence Interval display (when available)
                if let ci = result.confidenceIntervalConverted {
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
        guard let ci = result.confidenceIntervalConverted else {
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
                handleDismiss()
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
        date.toCompactString()
    }
}

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
