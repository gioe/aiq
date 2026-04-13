import AIQSharedKit
import SwiftUI

/// Shared content layout for the test-taking flow.
///
/// Composes the time-warning banner, submit-error banner, progress header,
/// question scroll area with grid overlay, and navigation controls into the
/// standard vertical layout used by both `TestTakingView` and
/// `GuestTestContainerView`.
///
/// The component includes a guard so it renders nothing until questions are
/// loaded; the parent's loading overlay handles the empty-state presentation.
struct TestContentLayout: View {
    /// The view model driving test state.
    @ObservedObject var viewModel: TestTakingViewModel

    /// The timer manager providing formatted time and expiry state.
    @ObservedObject var timerManager: TestTimerManager

    /// Controls visibility of the collapsible question navigation grid.
    @Binding var showQuestionGrid: Bool

    /// Controls visibility of the five-minute time-warning banner.
    @Binding var showTimeWarningBanner: Bool

    /// Tracks whether the user has manually dismissed the time-warning banner.
    @Binding var warningBannerDismissed: Bool

    /// Whether the user has enabled reduced motion.
    let reduceMotion: Bool

    var body: some View {
        if !viewModel.navigationState.questions.isEmpty {
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
                    .bannerSlideTransition(reduceMotion: reduceMotion)
                }

                // Inline error banner for post-load failures (e.g. submission errors).
                // Only shown when questions are already visible; full-page errors are handled
                // by the parent's load-failure view instead.
                if viewModel.shouldShowSubmitErrorBanner, let error = viewModel.error {
                    ErrorBanner(
                        message: error.localizedDescription,
                        onDismiss: { viewModel.clearError() },
                        retryAction: viewModel.canRetry ? {
                            Task { await viewModel.retry() }
                        } : nil,
                        dismissHint: viewModel.canRetry ? nil : "error.banner.submit.dismiss.hint".localized
                    )
                    .padding(.horizontal)
                    .padding(.top, 8)
                    .bannerSlideTransition(reduceMotion: reduceMotion)
                    .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.submitErrorBanner)
                }

                // Compact header: timer, progress, and grid toggle
                TestProgressHeader(
                    timerManager: timerManager,
                    currentQuestionIndex: viewModel.navigationState.currentQuestionIndex,
                    totalQuestions: viewModel.navigationState.questions.count,
                    answeredCount: viewModel.answeredCount,
                    reduceMotion: reduceMotion,
                    showQuestionGrid: $showQuestionGrid
                )

                ZStack(alignment: .top) {
                    ScrollView {
                        VStack(spacing: 24) {
                            if let question = viewModel.currentQuestion {
                                QuestionContentView(
                                    question: question,
                                    currentAnswer: Binding(
                                        get: { viewModel.currentAnswer },
                                        set: { viewModel.currentAnswer = $0 }
                                    ),
                                    isDisabled: viewModel.isLocked,
                                    questionNumber: viewModel.navigationState.currentQuestionIndex + 1,
                                    hasStimulusSeen: { viewModel.hasStimulusSeen(for: question.id) },
                                    markStimulusSeen: { viewModel.markStimulusSeen(for: question.id) }
                                )
                            }
                        }
                        .padding()
                    }

                    // Collapsible question navigation grid (overlay)
                    if showQuestionGrid {
                        QuestionNavigationGrid(
                            totalQuestions: viewModel.navigationState.questions.count,
                            currentQuestionIndex: viewModel.navigationState.currentQuestionIndex,
                            answeredQuestionIndices: viewModel.navigationState.answeredQuestionIndices,
                            onQuestionTap: { index in
                                withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
                                    viewModel.goToQuestion(at: index)
                                }
                            }
                        )
                        .padding(.horizontal)
                        .padding(.top, 8)
                        .bannerSlideTransition(reduceMotion: reduceMotion)
                    }
                }
                .clipped()

                // Navigation controls
                TestNavigationControls(viewModel: viewModel, reduceMotion: reduceMotion)
                    .padding()
                    .background(Color(.systemBackground))
                    .shadow(
                        color: DesignSystem.Shadow.sm.color,
                        radius: DesignSystem.Shadow.sm.radius,
                        x: 0,
                        y: -DesignSystem.Shadow.sm.y
                    )
            }
            .background(Color(.systemGroupedBackground))
        }
    }
}
