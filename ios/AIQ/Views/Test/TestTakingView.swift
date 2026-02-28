import SwiftUI

// swiftlint:disable type_body_length

/// Main view for taking an IQ test
struct TestTakingView: View {
    @StateObject private var viewModel: TestTakingViewModel
    @StateObject private var timerManager = TestTimerManager()
    @EnvironmentObject var router: AppRouter
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var showResumeAlert = false
    @State private var showExitConfirmation = false
    @State private var savedProgress: SavedTestProgress?
    @State private var activeSessionConflictId: Int?
    @State private var showQuestionGrid = false
    @State private var showTimeWarningBanner = false
    @State private var warningBannerDismissed = false
    @State private var showTimeExpiredAlert = false
    @State private var isAutoSubmitting = false

    /// The session ID to resume (if any)
    private let sessionId: Int?

    /// Creates a TestTakingView with the specified service container
    /// - Parameters:
    ///   - sessionId: Optional session ID to resume an existing test session
    ///   - serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///     Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(sessionId: Int? = nil, serviceContainer: ServiceContainer = .shared) {
        self.sessionId = sessionId
        let vm = ViewModelFactory.makeTestTakingViewModel(container: serviceContainer)
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

    /// True when startTest failed and the full-page error state should be shown
    private var shouldShowLoadFailure: Bool {
        !viewModel.isLoading && viewModel.questions.isEmpty && viewModel.error != nil && !isActiveSessionConflict
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
            if viewModel.isTestCompleted {
                testCompletedView
            } else if shouldShowLoadFailure {
                loadFailureView
            } else {
                testContentView
            }

            // Loading overlay for initial test fetch
            if viewModel.isLoading && viewModel.questions.isEmpty {
                LoadingOverlay(message: "Preparing your test...")
                    .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.9)))
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.loadingOverlay)
            }

            // Loading overlay for test submission
            if viewModel.isSubmitting {
                LoadingOverlay(message: "Submitting your test...")
                    .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.9)))
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.loadingOverlay)
            }
        }
        .navigationTitle("IQ Test")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .tabBar)
        .navigationBarBackButtonHidden(true)
        .toolbar {
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
            if let sessionId {
                // Deep link resume: use the provided session ID
                await resumeSessionFromDeepLink(sessionId: sessionId)
            } else {
                // Normal flow: check for saved progress
                await checkForSavedProgress()
            }
        }
        .onChange(of: timerManager.showWarning) { showWarning in
            // Show warning banner when timer hits 5 minutes (unless already dismissed)
            if showWarning && !warningBannerDismissed {
                showTimeWarningBanner = true
            }
        }
        .onChange(of: viewModel.isTestCompleted) { completed in
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
            if expired && !viewModel.isTestCompleted && !isAutoSubmitting {
                handleTimerExpiration()
            }
        }
    }

    private func checkForSavedProgress() async {
        #if DEBUG
            print("[TestTakingView] checkForSavedProgress called")
        #endif
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
            #if DEBUG
                print("[TestTakingView] No saved progress, calling startTest")
            #endif
            await viewModel.startTest()
            #if DEBUG
                let qCount = viewModel.questions.count
                print("[TestTakingView] After startTest: questions.count=\(qCount), isLoading=\(viewModel.isLoading)")
            #endif
            // Start timer after test loads successfully using session start time
            if let session = viewModel.testSession {
                timerManager.startWithSessionTime(session.startedAt)
            }
        }
    }

    /// Resume a test session from a deep link
    /// - Parameter sessionId: The ID of the session to resume
    private func resumeSessionFromDeepLink(sessionId: Int) async {
        #if DEBUG
            print("[TestTakingView] resumeSessionFromDeepLink called with sessionId: \(sessionId)")
        #endif
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
        if viewModel.answeredCount > 0 && !viewModel.isTestCompleted {
            showExitConfirmation = true
        } else {
            router.pop()
        }
    }

    // MARK: - Test Content

    private var loadFailureView: some View {
        VStack(spacing: 16) {
            if let error = viewModel.error {
                ErrorView(
                    error: error,
                    retryAction: viewModel.canRetry ? {
                        Task {
                            await viewModel.retry()
                            if let session = viewModel.testSession {
                                let timerStarted = timerManager.startWithSessionTime(session.startedAt)
                                if !timerStarted {
                                    handleTimerExpiration()
                                }
                            }
                        }
                    } : nil
                )
            }
            if !viewModel.canRetry {
                Button("Go Back") {
                    router.pop()
                }
                .buttonStyle(.bordered)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemGroupedBackground))
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.loadFailureOverlay)
    }

    private var testContentView: some View {
        VStack(spacing: 0) {
            #if DEBUG
                // Debug indicator for test mode - shows question count and loading state
                HStack {
                    let qCount = viewModel.questions.count
                    let loadState = viewModel.isLoading ? "Y" : "N"
                    let mockState = MockModeDetector.isMockMode ? "Y" : "N"
                    Text("Q:\(qCount) L:\(loadState) M:\(mockState)")
                        .font(.caption)
                        .padding(4)
                        .background(viewModel.questions.isEmpty ? Color.red.opacity(0.3) : Color.green.opacity(0.3))
                        .cornerRadius(4)
                        .accessibilityIdentifier("testTakingView.debugState")
                }
            #endif
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

            // Compact header: timer, progress, and grid toggle
            compactHeader

            // Collapsible question navigation grid
            if showQuestionGrid {
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
                .padding(.horizontal)
                .padding(.bottom, 8)
                .transition(reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity))
            }

            ScrollView {
                VStack(spacing: 24) {
                    if let question = viewModel.currentQuestion {
                        if question.isMemoryQuestion {
                            // Memory questions use a two-phase view (stimulus then question)
                            MemoryQuestionView(
                                question: question,
                                questionNumber: viewModel.currentQuestionIndex + 1,
                                totalQuestions: viewModel.questions.count,
                                userAnswer: Binding(
                                    get: { viewModel.currentAnswer },
                                    set: { viewModel.currentAnswer = $0 }
                                ),
                                showingStimulus: Binding(
                                    get: { !viewModel.hasStimulusSeen(for: question.id) },
                                    set: { newValue in
                                        if !newValue {
                                            viewModel.markStimulusSeen(for: question.id)
                                        }
                                    }
                                ),
                                isDisabled: viewModel.isLocked
                            )
                            .transition(
                                reduceMotion ? .opacity : .asymmetric(
                                    insertion: .move(edge: .trailing).combined(with: .opacity),
                                    removal: .move(edge: .leading).combined(with: .opacity)
                                )
                            )
                        } else {
                            // Standard questions: show question card and answer input separately
                            QuestionCardView(question: question)
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

    // MARK: - Compact Header

    private var compactHeader: some View {
        VStack(spacing: 6) {
            HStack {
                TestTimerView(timerManager: timerManager)
                Spacer()
                Text("\(viewModel.currentQuestionIndex + 1)/\(viewModel.questions.count)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.progressLabel)
                Text("·").foregroundColor(.secondary)
                Text("\(viewModel.answeredCount) answered")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
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

            let allAnswered = viewModel.answeredCount == viewModel.questions.count && !viewModel.questions.isEmpty
            ProgressView(
                value: Double(viewModel.answeredCount),
                total: Double(max(viewModel.questions.count, 1))
            )
            .tint(allAnswered ? .green : .accentColor)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(.systemBackground))
        .shadow(color: Color.black.opacity(0.05), radius: 2, y: 1)
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

                Text("You answered \(viewModel.answeredCount) out of \(viewModel.questions.count) questions")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.successAnswerCount)
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
                    isLoading: false,
                    accessibilityId: AccessibilityIdentifiers.TestTakingView.viewResultsButton
                )

                Button("Return to Dashboard") {
                    router.popToRoot()
                }
                .buttonStyle(.bordered)
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.returnToDashboardButton)
            }
            .padding(.horizontal)
        }
        .padding()
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.successOverlay)
    }
}

// swiftlint:enable type_body_length

// MARK: - Preview

#Preview {
    NavigationStack {
        TestTakingView()
    }
}

#Preview("Large Text") {
    NavigationStack {
        TestTakingView()
    }
    .environment(\.sizeCategory, .accessibilityLarge)
}
