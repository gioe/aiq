import SwiftUI

/// Shared question display block used by both fixed-form and adaptive test views.
///
/// Handles the `isMemoryQuestion` branch: memory questions render as `MemoryQuestionView`
/// (two-phase stimulus → question), while standard questions render as `QuestionCardView`
/// + `AnswerInputView`.
struct QuestionContentView: View {
    let question: Question
    @Binding var currentAnswer: String
    let isDisabled: Bool
    let reduceMotion: Bool
    let questionNumber: Int
    let totalQuestions: Int
    /// Returns whether the stimulus for the current question has already been seen.
    let hasStimulusSeen: () -> Bool
    /// Marks the stimulus for the current question as seen.
    let markStimulusSeen: () -> Void

    var body: some View {
        if question.isMemoryQuestion {
            // Memory questions use a two-phase view (stimulus then question)
            MemoryQuestionView(
                question: question,
                questionNumber: questionNumber,
                totalQuestions: totalQuestions,
                userAnswer: $currentAnswer,
                showingStimulus: Binding(
                    get: { !hasStimulusSeen() },
                    set: { newValue in
                        if !newValue {
                            markStimulusSeen()
                        }
                    }
                ),
                isDisabled: isDisabled
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
                userAnswer: $currentAnswer,
                isDisabled: isDisabled
            )
            .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.95)))
        }
    }
}
