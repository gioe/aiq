import SwiftUI

/// Card displaying the user's most recent test result on the Dashboard
struct DashboardLatestTestResultCard: View {
    let result: TestResult
    let dateFormatted: String?

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
            TestCardHeader(dateFormatted: dateFormatted)
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
    }
}

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
        dateFormatted: "March 2, 2026"
    )
    .padding()
}
