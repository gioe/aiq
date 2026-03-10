import SwiftUI

/// Compact header bar displayed during test-taking: timer, question position,
/// answered count, grid toggle, and progress bar.
struct TestProgressHeader: View {
    let timerManager: TestTimerManager
    let currentQuestionIndex: Int
    let totalQuestions: Int
    let answeredCount: Int
    let reduceMotion: Bool
    @Binding var showQuestionGrid: Bool

    var body: some View {
        VStack(spacing: 6) {
            HStack {
                TestTimerView(timerManager: timerManager)
                Spacer()
                Text("\(currentQuestionIndex + 1)/\(totalQuestions)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.progressLabel)
                Text("·").foregroundColor(.secondary)
                Text("\(answeredCount) answered")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                Button {
                    withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
                        showQuestionGrid.toggle()
                    }
                } label: {
                    Image(systemName: showQuestionGrid ? "square.grid.3x3.fill" : "square.grid.3x3")
                        .font(.body)
                        .foregroundColor(.accentColor)
                        .frame(minWidth: 44, minHeight: 44)
                }
                .accessibilityLabel(showQuestionGrid ? "Hide question grid" : "Show question grid")
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionNavigationGrid)
            }

            let allAnswered = answeredCount == totalQuestions && totalQuestions > 0
            ProgressView(
                value: Double(answeredCount),
                total: Double(max(totalQuestions, 1))
            )
            .tint(allAnswered ? .green : .accentColor)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(.systemBackground))
        .shadowStyle(DesignSystem.Shadow.header)
    }
}
