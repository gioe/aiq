import AIQSharedKit
import SwiftUI

/// Compact single-line row for displaying a test result in the month-grouped history list
struct CompactTestRow: View {
    let testResult: TestResult

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.sm) {
            Text("\(testResult.iqScore)")
                .font(.body.weight(.bold).monospacedDigit())
                .foregroundColor(scoreColor)
                .frame(width: 44, alignment: .leading)

            Text(testResult.completedAt, style: .date)
                .font(.subheadline)
                .foregroundColor(.primary)

            Spacer()

            Text(String(format: "%.0f%%", testResult.accuracyPercentage))
                .font(.subheadline)
                .foregroundColor(.secondary)

            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundColor(Color(.tertiaryLabel))
        }
        .padding(.vertical, DesignSystem.Spacing.xs)
        .padding(.horizontal, DesignSystem.Spacing.sm)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "AIQ Score \(testResult.iqScore), accuracy \(String(format: "%.0f", testResult.accuracyPercentage)) percent"
        )
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

#if DebugBuild
    #Preview("High Score") {
        CompactTestRow(
            testResult: MockDataFactory.makeTestResult(
                id: 1,
                testSessionId: 1,
                userId: 1,
                iqScore: 135,
                totalQuestions: 20,
                correctAnswers: 17,
                accuracyPercentage: 85.0,
                completedAt: Date()
            )
        )
        .padding()
    }

    #Preview("Low Score") {
        CompactTestRow(
            testResult: MockDataFactory.makeTestResult(
                id: 2,
                testSessionId: 2,
                userId: 1,
                iqScore: 88,
                totalQuestions: 20,
                correctAnswers: 12,
                accuracyPercentage: 60.0,
                completedAt: Date()
            )
        )
        .padding()
    }
#endif
