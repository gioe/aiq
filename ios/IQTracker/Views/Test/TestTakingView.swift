import SwiftUI

/// Main view for taking an IQ test
struct TestTakingView: View {
    @StateObject private var viewModel = TestTakingViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            if viewModel.testCompleted {
                testCompletedView
            } else {
                testContentView
            }

            // Loading overlay
            if viewModel.isSubmitting {
                LoadingOverlay(message: "Submitting your test...")
            }
        }
        .navigationTitle("IQ Test")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Exit") {
                    dismiss()
                }
            }
        }
        .task {
            await viewModel.startTest()
        }
    }

    // MARK: - Test Content

    private var testContentView: some View {
        VStack(spacing: 0) {
            // Progress at the top
            TestProgressView(
                currentQuestion: viewModel.currentQuestionIndex + 1,
                totalQuestions: viewModel.questions.count,
                answeredCount: viewModel.answeredCount
            )
            .padding()
            .background(Color(.systemBackground))
            .shadow(color: Color.black.opacity(0.05), radius: 4, y: 2)

            ScrollView {
                VStack(spacing: 24) {
                    if let question = viewModel.currentQuestion {
                        // Question card
                        QuestionCardView(
                            question: question,
                            questionNumber: viewModel.currentQuestionIndex + 1,
                            totalQuestions: viewModel.questions.count
                        )
                        .transition(.asymmetric(
                            insertion: .move(edge: .trailing).combined(with: .opacity),
                            removal: .move(edge: .leading).combined(with: .opacity)
                        ))

                        // Answer input
                        AnswerInputView(
                            question: question,
                            userAnswer: Binding(
                                get: { viewModel.currentAnswer },
                                set: { viewModel.currentAnswer = $0 }
                            )
                        )
                        .transition(.opacity.combined(with: .scale(scale: 0.95)))
                    }
                }
                .padding()
            }

            // Navigation controls
            navigationControls
                .padding()
                .background(Color(.systemBackground))
                .shadow(color: Color.black.opacity(0.05), radius: 4, y: -2)
        }
        .background(Color(.systemGroupedBackground))
    }

    private var navigationControls: some View {
        HStack(spacing: 12) {
            // Previous button
            Button {
                withAnimation(.spring(response: 0.3)) {
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

            // Next or Submit button
            if viewModel.isLastQuestion {
                submitButton
            } else {
                Button {
                    withAnimation(.spring(response: 0.3)) {
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
            }
        }
    }

    private var submitButton: some View {
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
        .disabled(!viewModel.allQuestionsAnswered)
    }

    // MARK: - Test Completed

    private var testCompletedView: some View {
        VStack(spacing: 24) {
            Spacer()

            // Success icon
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.green)

            VStack(spacing: 12) {
                Text("Test Completed!")
                    .font(.largeTitle)
                    .fontWeight(.bold)

                Text("Your answers have been submitted")
                    .font(.body)
                    .foregroundColor(.secondary)

                Text("You answered \(viewModel.answeredCount) out of \(viewModel.questions.count) questions")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Action buttons
            VStack(spacing: 12) {
                PrimaryButton(
                    title: "View Results",
                    action: {
                        // swiftlint:disable:next todo
                        // TODO: Navigate to results
                        dismiss()
                    },
                    isLoading: false
                )

                Button("Return to Dashboard") {
                    dismiss()
                }
                .buttonStyle(.bordered)
            }
            .padding(.horizontal)
        }
        .padding()
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        TestTakingView()
    }
}
