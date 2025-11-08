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

            // Loading overlay with transition
            if viewModel.isSubmitting {
                LoadingOverlay(message: "Submitting your test...")
                    .transition(.opacity.combined(with: .scale(scale: 0.9)))
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
            // Progress section at the top
            VStack(spacing: 12) {
                // Enhanced progress bar with stats
                TestProgressView(
                    currentQuestion: viewModel.currentQuestionIndex + 1,
                    totalQuestions: viewModel.questions.count,
                    answeredCount: viewModel.answeredCount
                )

                // Question navigation grid
                QuestionNavigationGrid(
                    totalQuestions: viewModel.questions.count,
                    currentQuestionIndex: viewModel.currentQuestionIndex,
                    answeredQuestionIndices: answeredQuestionIndices,
                    onQuestionTap: { index in
                        withAnimation(.spring(response: 0.3)) {
                            viewModel.goToQuestion(at: index)
                        }
                    }
                )
            }
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

    // MARK: - Computed Properties

    private var answeredQuestionIndices: Set<Int> {
        var indices = Set<Int>()
        for (index, question) in viewModel.questions.enumerated() {
            if let answer = viewModel.userAnswers[question.id], !answer.isEmpty {
                indices.insert(index)
            }
        }
        return indices
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

    @State private var showCompletionAnimation = false

    private var testCompletedView: some View {
        VStack(spacing: 24) {
            Spacer()

            // Success icon with celebratory animation
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.green)
                .scaleEffect(showCompletionAnimation ? 1.0 : 0.5)
                .opacity(showCompletionAnimation ? 1.0 : 0.0)
                .rotationEffect(.degrees(showCompletionAnimation ? 0 : -180))

            VStack(spacing: 12) {
                Text("Test Completed!")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: showCompletionAnimation ? 0 : 20)

                Text("Your answers have been submitted")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: showCompletionAnimation ? 0 : 20)

                Text("You answered \(viewModel.answeredCount) out of \(viewModel.questions.count) questions")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: showCompletionAnimation ? 0 : 20)
            }
            .onAppear {
                // Staggered animations for text elements
                withAnimation(.spring(response: 0.6, dampingFraction: 0.6)) {
                    showCompletionAnimation = true
                }
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
