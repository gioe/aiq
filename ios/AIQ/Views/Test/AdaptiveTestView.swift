import SwiftUI

/// Main view for taking an adaptive (CAT) test
///
/// Key differences from fixed-form TestTakingView:
/// - No question grid navigation (can't jump around)
/// - No Previous button (can't go back)
/// - Submit action fetches next question instead of navigating
/// - Loading state between questions
/// - Test completion is determined by CAT engine
struct AdaptiveTestView: View {
    @StateObject private var viewModel: TestTakingViewModel
    @StateObject private var timerManager = TestTimerManager()
    @EnvironmentObject var router: AppRouter
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    @State private var showExitConfirmation = false
    @State private var showTimeWarningBanner = false
    @State private var warningBannerDismissed = false
    @State private var showTimeExpiredAlert = false
    @State private var isAutoSubmitting = false
    @State private var cachedAdministeredDomains: Set<QuestionType> = []

    /// Creates an AdaptiveTestView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeTestTakingViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        ZStack {
            if viewModel.isTestCompleted {
                testCompletedView
            } else {
                testContentView
            }

            // Loading overlay for initial test fetch
            if viewModel.isLoading && viewModel.questions.isEmpty {
                LoadingOverlay(message: "Preparing your adaptive test...")
                    .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.9)))
                    .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.loadingOverlay)
            }

            // Loading overlay for test submission
            if viewModel.isSubmitting {
                LoadingOverlay(message: "Submitting your test...")
                    .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.9)))
            }
        }
        .navigationTitle("Adaptive IQ Test")
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
                .accessibilityHint("Exits the current adaptive test")
                .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.exitButton)
            }
        }
        .task {
            await startAdaptiveTest()
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
        .alert("Exit Test?", isPresented: $showExitConfirmation) {
            Button("Exit", role: .destructive) {
                Task {
                    await viewModel.abandonTest()
                    router.popToRoot()
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            let count = viewModel.answeredCount
            let suffix = count == 1 ? "" : "s"
            Text(
                "You have completed \(count) question\(suffix). " +
                    "Exiting will end your test. Are you sure?"
            )
        }
        .alert("Time's Up!", isPresented: $showTimeExpiredAlert) {
            Button("OK") {
                // Navigate to results when user dismisses the alert
                if let result = viewModel.testResult {
                    router.push(.testResults(result: result, isFirstTest: viewModel.isFirstTest))
                }
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
        .onChange(of: viewModel.questions.count) { _ in
            // Incrementally add the latest question's domain to the cache.
            // In adaptive mode, questions are always appended one at a time
            // via submitAnswerAndGetNext(), so checking only the last item is safe.
            if let lastQuestion = viewModel.questions.last,
               let domain = lastQuestion.questionTypeEnum {
                cachedAdministeredDomains.insert(domain)
            }
        }
        .onDisappear {
            timerManager.stop()
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.container)
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

            // Adaptive progress header
            AdaptiveProgressHeader(
                timerManager: timerManager,
                itemsAdministered: viewModel.itemsAdministered,
                estimatedTotal: Constants.Test.maxAdaptiveItems,
                progress: viewModel.progress,
                administeredDomains: cachedAdministeredDomains
            )

            ScrollView {
                VStack(spacing: 24) {
                    if viewModel.isLoadingNextQuestion {
                        // Loading indicator between questions
                        loadingNextQuestionView
                    } else if let question = viewModel.currentQuestion {
                        if question.isMemoryQuestion {
                            // Memory questions use a two-phase view (stimulus then question)
                            MemoryQuestionView(
                                question: question,
                                questionNumber: viewModel.itemsAdministered,
                                totalQuestions: Constants.Test.maxAdaptiveItems,
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

            // Submit & Continue button
            submitBar
                .padding()
                .background(Color(.systemBackground))
                .shadow(color: Color.black.opacity(0.05), radius: 4, y: -2)
        }
        .background(Color(.systemGroupedBackground))
    }

    // MARK: - Loading Next Question

    private var loadingNextQuestionView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)
                .progressViewStyle(CircularProgressViewStyle(tint: .accentColor))

            Text("Loading next question...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 60)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Loading next question")
        .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.loadingNextQuestion)
    }

    // MARK: - Submit Bar

    private var submitBar: some View {
        VStack(spacing: 8) {
            // Error display when API call fails
            if let error = viewModel.error {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    Text(error.localizedDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                    Spacer()
                    if viewModel.canRetry {
                        Button("Retry") {
                            Task { await viewModel.retry() }
                        }
                        .font(.caption)
                        .fontWeight(.semibold)
                    }
                    Button {
                        viewModel.clearError()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .frame(minWidth: 44, minHeight: 44)
                }
                .padding(.horizontal)
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Error: \(error.localizedDescription)")
            }

            PrimaryButton(
                title: "Submit & Continue",
                action: {
                    Task {
                        await submitAnswerAndGetNext()
                    }
                },
                isLoading: viewModel.isLoadingNextQuestion,
                isDisabled: viewModel.currentAnswer.isEmpty
                    || viewModel.isLocked
                    || isAutoSubmitting
                    || viewModel.isLoadingNextQuestion,
                accessibilityId: AccessibilityIdentifiers.AdaptiveTestView.submitAndContinueButton
            )
        }
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

                Text("Your adaptive test has been submitted")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .opacity(showCompletionAnimation ? 1.0 : 0.0)
                    .offset(y: reduceMotion ? 0 : (showCompletionAnimation ? 0 : 20))

                Text("You answered \(viewModel.answeredCount) question\(viewModel.answeredCount == 1 ? "" : "s")")
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

    // MARK: - Private Methods

    private func startAdaptiveTest() async {
        await viewModel.startAdaptiveTest()

        // Start timer after test loads successfully using session start time
        if let session = viewModel.testSession {
            timerManager.startWithSessionTime(session.startedAt)
        }
    }

    private func submitAnswerAndGetNext() async {
        // Guard against concurrent submissions: prevents race condition between
        // user-initiated submit and timer-triggered auto-submit
        guard !isAutoSubmitting, !viewModel.isSubmitting else { return }
        await viewModel.submitAnswerAndGetNext()
    }

    /// Handles timer expiration by locking answers, auto-submitting, then showing alert
    private func handleTimerExpiration() {
        // Prevent multiple auto-submits
        guard !isAutoSubmitting else { return }
        isAutoSubmitting = true

        // Immediately lock answers to prevent race conditions
        viewModel.lockAnswers()

        // Auto-submit first, then show alert (navigation happens on alert dismissal)
        Task {
            await viewModel.submitTestForTimeout()

            // Show alert after submission completes; navigation is handled by the alert's OK action
            showTimeExpiredAlert = true
        }
    }

    private func handleExit() {
        if viewModel.answeredCount > 0 && !viewModel.isTestCompleted {
            showExitConfirmation = true
        } else {
            router.pop()
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        AdaptiveTestView()
    }
}
