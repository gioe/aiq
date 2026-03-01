import SwiftUI

/// Celebration view shown after a test is completed.
/// Displays staggered icon/text animations and two action buttons.
struct TestCompletionView: View {
    let answeredCount: Int
    let totalQuestions: Int
    let onViewResults: () -> Void
    let onReturnToDashboard: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var showCompletionAnimation = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // Success icon with celebratory animation
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.green)
                .scaleEffect(reduceMotion ? 1.0 : (showCompletionAnimation ? 1.0 : 0.5))
                .opacity(showCompletionAnimation ? 1.0 : 0.0)
                .rotationEffect(.degrees(reduceMotion ? 0 : (showCompletionAnimation ? 0 : -180)))
                .accessibilityHidden(true)

            VStack(spacing: 12) {
                Text("Test Completed!")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.successTitle)

                Text("Your answers have been submitted")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.successSubtitle)

                Text("You answered \(answeredCount) out of \(totalQuestions) questions")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.successAnswerCount)
            }
            .onAppear {
                withAnimation(reduceMotion ? nil : .spring(response: 0.6, dampingFraction: 0.6)) {
                    showCompletionAnimation = true
                }
            }

            Spacer()

            VStack(spacing: 12) {
                PrimaryButton(
                    title: "View Results",
                    action: onViewResults,
                    isLoading: false,
                    accessibilityId: AccessibilityIdentifiers.TestTakingView.viewResultsButton
                )

                Button("Return to Dashboard", action: onReturnToDashboard)
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.returnToDashboardButton)
            }
            .padding(.horizontal)
        }
        .padding()
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.successOverlay)
    }
}

// MARK: - Preview

#Preview {
    TestCompletionView(
        answeredCount: 20,
        totalQuestions: 20,
        onViewResults: {},
        onReturnToDashboard: {}
    )
}
