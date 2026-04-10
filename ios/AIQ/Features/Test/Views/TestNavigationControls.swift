import AIQSharedKit
import SwiftUI

/// Shared navigation controls for the test-taking flow.
///
/// Renders a Previous button on the left and either a Next or Submit button on the right,
/// depending on whether the current question is the last one. Both `TestTakingView` and
/// `GuestTestContainerView` use this component.
struct TestNavigationControls: View {
    /// The view model driving test state.
    @ObservedObject var viewModel: TestTakingViewModel

    /// Whether the user has enabled reduced motion.
    let reduceMotion: Bool

    var body: some View {
        HStack(spacing: 12) {
            // Previous button
            Button {
                withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
                    viewModel.goToPrevious()
                }
            } label: {
                HStack {
                    Image(systemName: "chevron.left")
                    Text("Previous")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(!viewModel.canGoPrevious)
            .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.previousButton)

            // Next or Submit button
            if viewModel.isLastQuestion {
                submitButton
            } else {
                Button {
                    withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
                        viewModel.goToNext()
                    }
                } label: {
                    HStack {
                        Text("Next")
                        Image(systemName: "chevron.right")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.currentAnswer.isEmpty)
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.nextButton)
            }
        }
    }

    // MARK: - Submit Button

    private var submitButton: some View {
        let isDisabled = !viewModel.allQuestionsAnswered || viewModel.shouldShowSubmitErrorBanner
        let unansweredCount = viewModel.totalQuestionCount - viewModel.answeredCount

        return VStack(spacing: 6) {
            Button {
                Task {
                    await viewModel.submitTest()
                }
            } label: {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                    Text("Submit Test")
                }
                .frame(maxWidth: .infinity)
                .fontWeight(.semibold)
            }
            .buttonStyle(.borderedProminent)
            .disabled(isDisabled)
            .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.submitButton)
            .accessibilityLabel(submitAccessibilityLabel(
                isDisabled: isDisabled,
                unansweredCount: unansweredCount
            ))

            if !viewModel.allQuestionsAnswered {
                Text("Answer all \(viewModel.totalQuestionCount) questions to submit (\(unansweredCount) remaining)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.submitDisabledHint)
            }
        }
    }

    private func submitAccessibilityLabel(
        isDisabled: Bool,
        unansweredCount: Int
    ) -> String {
        guard isDisabled, unansweredCount > 0 else { return "Submit Test" }
        let plural = unansweredCount == 1 ? "" : "s"
        return "Submit Test, disabled. Answer \(unansweredCount) more question\(plural) to submit."
    }
}
