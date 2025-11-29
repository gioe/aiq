import SwiftUI

/// Main view for taking an IQ test
struct TestTakingView: View {
    @StateObject private var viewModel = TestTakingViewModel()
    @Environment(\.dismiss) private var dismiss
    @State private var showResumeAlert = false
    @State private var showExitConfirmation = false
    @State private var savedProgress: SavedTestProgress?
    @State private var showResultsView = false
    @State private var activeSessionConflictId: Int?

    /// Check if the current error is an active session conflict
    private var isActiveSessionConflict: Bool {
        if let contextualError = viewModel.error as? ContextualError,
           case .activeSessionConflict = contextualError.underlyingError {
            return true
        }
        return false
    }

    /// Extract session ID from active session conflict error
    private var conflictingSessionId: Int? {
        if let contextualError = viewModel.error as? ContextualError,
           case let .activeSessionConflict(sessionId, _) = contextualError.underlyingError {
            return sessionId
        }
        return nil
    }

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
                    handleExit()
                }
            }
        }
        .task {
            await checkForSavedProgress()
        }
        .alert("Resume Test?", isPresented: $showResumeAlert) {
            Button("Resume") {
                if let progress = savedProgress {
                    viewModel.restoreProgress(progress)
                }
            }
            Button("Start New") {
                viewModel.clearSavedProgress()
                Task {
                    await viewModel.startTest()
                }
            }
        } message: {
            Text("You have an incomplete test. Would you like to resume where you left off?")
        }
        .alert("Exit Test?", isPresented: $showExitConfirmation) {
            Button("Exit", role: .destructive) {
                Task {
                    await viewModel.abandonTest()
                    dismiss()
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("You have \(viewModel.answeredCount) unsaved answers. Are you sure you want to exit?")
        }
        .sheet(isPresented: $showResultsView) {
            if let result = viewModel.testResult {
                TestResultsView(result: result) {
                    showResultsView = false
                    dismiss()
                }
            }
        }
        .alert("Active Test Session", isPresented: .constant(isActiveSessionConflict)) {
            if let sessionId = conflictingSessionId {
                Button("Abandon & Start New", role: .destructive) {
                    Task {
                        await viewModel.abandonAndStartNew(sessionId: sessionId)
                    }
                }
                Button("Cancel", role: .cancel) {
                    viewModel.clearError()
                    dismiss()
                }
            }
        } message: {
            Text(
                """
                You have an active test session. Please abandon it to start a new test, \
                or return to the dashboard to resume from there.
                """
            )
        }
    }

    private func checkForSavedProgress() async {
        if let progress = viewModel.loadSavedProgress() {
            savedProgress = progress
            showResumeAlert = true
        } else {
            await viewModel.startTest()
        }
    }

    private func handleExit() {
        if viewModel.answeredCount > 0 && !viewModel.testCompleted {
            showExitConfirmation = true
        } else {
            dismiss()
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
                    answeredQuestionIndices: viewModel.answeredQuestionIndices,
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

    // MARK: - Navigation Controls

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
                        showResultsView = true
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
