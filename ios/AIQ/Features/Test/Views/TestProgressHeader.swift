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
                if totalQuestions > 0 {
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
                }
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
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionNavigationGridToggle)
            }

            let allAnswered = answeredCount == totalQuestions && totalQuestions > 0
            // Wrap ProgressView in a container so XCUITest can find it via app.otherElements[id].
            // .accessibilityElement(children: .contain) must precede .accessibilityIdentifier;
            // without it, SwiftUI leaves isAccessibilityElement=false and XCUITest never surfaces
            // the element.
            VStack {
                ProgressView(
                    value: Double(answeredCount),
                    total: Double(max(totalQuestions, 1))
                )
                .tint(allAnswered ? .green : .accentColor)
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.progressBar)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(.systemBackground))
        .shadowStyle(DesignSystem.Shadow.header)
    }
}
