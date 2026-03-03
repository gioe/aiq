import SwiftUI

/// Card displaying the user's most recent test result on the Dashboard
struct DashboardLatestTestResultCard: View {
    let result: TestResult
    let dateFormatted: String?

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
            // Hidden from VoiceOver: the container VStack already exposes the full
            // "Latest Result, <date>" label via .accessibilityLabel above, so surfacing
            // TestCardHeader's own .combine label would cause a double-read.
            TestCardHeader(dateFormatted: dateFormatted)
                .accessibilityHidden(true)
            TestCardScores(result: result)
            TestCardProgress(result: result)
        }
        .padding(DesignSystem.Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .fill(ColorPalette.backgroundSecondary)
                .shadow(
                    color: Color.black.opacity(0.1),
                    radius: DesignSystem.Shadow.lg.radius,
                    x: 0,
                    y: DesignSystem.Shadow.lg.y
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .strokeBorder(Color.gray.opacity(0.1), lineWidth: 1)
        )
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Latest Result" + (dateFormatted.map { ", \($0)" } ?? ""))
        .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.latestTestCard)
    }
}

#if DEBUG
    #Preview {
        DashboardLatestTestResultCard(
            result: MockDataFactory.makeTestResult(
                id: 1,
                testSessionId: 1,
                userId: 1,
                iqScore: 115,
                totalQuestions: 20,
                correctAnswers: 16,
                accuracyPercentage: 80.0,
                completedAt: Date()
            ),
            dateFormatted: "Jan 15, 2025"
        )
        .padding()
    }
#endif
