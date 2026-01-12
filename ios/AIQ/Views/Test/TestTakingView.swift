import SwiftUI

/// Main view for taking an IQ test
struct TestTakingView: View {
    @StateObject private var viewModel: TestTakingViewModel
    @StateObject private var timerManager = TestTimerManager()
    @Environment(\.appRouter) var router
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var showResumeAlert = false
    @State private var showExitConfirmation = false
    @State private var savedProgress: SavedTestProgress?
    @State private var activeSessionConflictId: Int?
    @State private var showTimeWarningBanner = false
    @State private var warningBannerDismissed = false
    @State private var showTimeExpiredAlert = false
    @State private var isAutoSubmitting = false

    init() {
        let vm = ViewModelFactory.makeTestTakingViewModel(container: ServiceContainer.shared)
        _viewModel = StateObject(wrappedValue: vm)
    }

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
                    .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.9)))
            }
        }
        .navigationTitle("IQ Test")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                TestTimerView(timerManager: timerManager)
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Exit") {
                    handleExit()
                }
                .frame(minWidth: 44, minHeight: 44)
                .accessibilityLabel("Exit test")
                .accessibilityHint("Exits the current test")
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.exitButton)
            }
        }
        .task {
            await checkForSavedProgress()
        }
        .onChange(of: timerManager.showWarning) { showWarning in
            // Show warning banner when timer hits 5 minutes (unless already dismissed)
            if showWarning && !warningBannerDismissed {
                showTimeWarningBanner = true
            }
        }
        .onChange(of: viewModel.testCompleted) { completed in
            // Stop timer when test is completed
            if completed {
                timerManager.stop()
            }
        }
        .alert("Resume Test?", isPresented: $showResumeAlert) {
            Button("Resume") {
                if let progress = savedProgress {
                    viewModel.restoreProgress(progress)
                    // Start timer with the original session start time
                    if let sessionStartedAt = progress.sessionStartedAt {
                        let timerStarted = timerManager.startWithSessionTime(sessionStartedAt)
                        if !timerStarted {
                            // Time expired while viewing the alert - trigger auto-submit
                            handleTimerExpiration()
                        }
                    } else {
                        // Fallback: no session start time saved, start fresh timer
                        // This handles legacy saved progress without sessionStartedAt
                        timerManager.start()
                    }
                }
            }
            Button("Start New") {
                viewModel.clearSavedProgress()
                Task {
                    await viewModel.startTest()
                    if let session = viewModel.testSession {
                        timerManager.startWithSessionTime(session.startedAt)
                    }
                }
            }
        } message: {
            Text("You have an incomplete test. Would you like to resume where you left off?")
        }
        .alert("Exit Test?", isPresented: $showExitConfirmation) {
            Button("Exit", role: .destructive) {
                Task {
                    await viewModel.abandonTest()
                    router.popToRoot()
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("You have \(viewModel.answeredCount) unsaved answers. Are you sure you want to exit?")
        }
        .alert("Test in Progress", isPresented: .constant(isActiveSessionConflict)) {
            if let sessionId = conflictingSessionId {
                Button("Resume Test") {
                    Task {
                        await viewModel.resumeActiveSession(sessionId: sessionId)
                        // Start timer using the session's original start time
                        if let session = viewModel.testSession {
                            let timerStarted = timerManager.startWithSessionTime(session.startedAt)
                            if !timerStarted {
                                // Time expired - trigger auto-submit
                                handleTimerExpiration()
                            }
                        }
                    }
                }
                Button("Abandon & Start New", role: .destructive) {
                    Task {
                        await viewModel.abandonAndStartNew(sessionId: sessionId)
                        // New session starts with fresh timer using new session's start time
                        if let session = viewModel.testSession {
                            timerManager.reset()
                            timerManager.startWithSessionTime(session.startedAt)
                        }
                    }
                }
                Button("Go Back", role: .cancel) {
                    viewModel.clearError()
                    router.pop()
                }
            }
        } message: {
            Text(
                """
                You have an in-progress test. Resume to continue where you left off, \
                or abandon it to start a fresh test.
                """
            )
        }
        .alert("Time's Up!", isPresented: $showTimeExpiredAlert) {
            Button("OK") {
                // Alert dismissed - auto-submit happens automatically
            }
        } message: {
            Text(
                """
                The 30-minute time limit has expired. \
                Your \(viewModel.answeredCount) answered question\(viewModel.answeredCount == 1 ? "" : "s") \
                will be submitted automatically.
                """
            )
        }
        .onChange(of: timerManager.hasExpired) { expired in
            // Handle timer expiration during test-taking
            if expired && !viewModel.testCompleted && !isAutoSubmitting {
                handleTimerExpiration()
            }
        }
    }

    private func checkForSavedProgress() async {
        if let progress = viewModel.loadSavedProgress() {
            // Check if test time has already expired
            if progress.isTimeExpired {
                // Time expired - restore progress and trigger auto-submit
                viewModel.restoreProgress(progress)
                handleTimerExpiration()
                return
            }
            savedProgress = progress
            showResumeAlert = true
        } else {
            await viewModel.startTest()
            // Start timer after test loads successfully using session start time
            if let session = viewModel.testSession {
                timerManager.startWithSessionTime(session.startedAt)
            }
        }
    }

    /// Handles timer expiration by locking answers, showing alert, and auto-submitting
    private func handleTimerExpiration() {
        // Prevent multiple auto-submits
        guard !isAutoSubmitting else { return }
        isAutoSubmitting = true

        // Immediately lock answers to prevent race conditions
        viewModel.lockAnswers()

        // Show the "Time's Up" alert
        showTimeExpiredAlert = true

        // Auto-submit the test
        Task {
            await viewModel.submitTestForTimeout()

            // Navigate to results after submission
            if let result = viewModel.testResult {
                router.push(.testResults(result: result, isFirstTest: viewModel.isFirstTest))
            }
        }
    }

    private func handleExit() {
        if viewModel.answeredCount > 0 && !viewModel.testCompleted {
            showExitConfirmation = true
        } else {
            router.pop()
        }
    }

    // MARK: - Test Content

    private var testContentView: some View {
        VStack(spacing: 0) {
            // Time warning banner (shown when 5 minutes remaining)
            if showTimeWarningBanner {
                TimeWarningBanner(
                    remainingTime: timerManager.formattedTime,
                    onDismiss: {
                        showTimeWarningBanner = false
                        warningBannerDismissed = true
                    }
                )
                .padding(.top, 8)
                .transition(reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity))
            }

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
                        withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
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
                        .transition(
                            reduceMotion ? .opacity : .asymmetric(
                                insertion: .move(edge: .trailing).combined(with: .opacity),
                                removal: .move(edge: .leading).combined(with: .opacity)
                            )
                        )

                        // Answer input
                        AnswerInputView(
                            question: question,
                            userAnswer: Binding(
                                get: { viewModel.currentAnswer },
                                set: { viewModel.currentAnswer = $0 }
                            ),
                            isDisabled: viewModel.isLocked
                        )
                        .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.95)))
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
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.submitButton)
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
                .scaleEffect(reduceMotion ? 1.0 : (showCompletionAnimation ? 1.0 : 0.5))
                .opacity(showCompletionAnimation ? 1.0 : 0.0)
                .rotationEffect(.degrees(reduceMotion ? 0 : (showCompletionAnimation ? 0 : -180)))

            VStack(spacing: 12) {
                Text("Test Completed!")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))

                Text("Your answers have been submitted")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))

                Text("You answered \(viewModel.answeredCount) out of \(viewModel.questions.count) questions")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))
            }
            .onAppear {
                // Staggered animations for text elements
                withAnimation(reduceMotion ? nil : .spring(response: 0.6, dampingFraction: 0.6)) {
                    showCompletionAnimation = true
                }
            }

            Spacer()

            // Action buttons
            VStack(spacing: 12) {
                PrimaryButton(
                    title: "View Results",
                    action: {
                        if let result = viewModel.testResult {
                            router.push(.testResults(result: result, isFirstTest: viewModel.isFirstTest))
                        }
                    },
                    isLoading: false
                )

                Button("Return to Dashboard") {
                    router.popToRoot()
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
