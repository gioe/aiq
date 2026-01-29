import SwiftUI

/// A view for memory questions that implements two-phase rendering:
/// 1. **Stimulus Phase**: Shows the content to memorize with a Continue button
/// 2. **Question Phase**: Hides stimulus and shows the question with answer input
///
/// Memory questions test recall by presenting content (stimulus) first,
/// then hiding it and asking the user to recall what they saw.
struct MemoryQuestionView: View {
    let question: Question
    let questionNumber: Int
    let totalQuestions: Int
    @Binding var userAnswer: String
    /// Whether we're showing the stimulus (true) or the question (false)
    @Binding var showingStimulus: Bool
    var isDisabled: Bool = false

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        VStack(spacing: 24) {
            if showingStimulus {
                stimulusPhase
                    .transition(reduceMotion ? .opacity : .asymmetric(
                        insertion: .move(edge: .leading).combined(with: .opacity),
                        removal: .move(edge: .leading).combined(with: .opacity)
                    ))
            } else {
                questionPhase
                    .transition(reduceMotion ? .opacity : .asymmetric(
                        insertion: .move(edge: .trailing).combined(with: .opacity),
                        removal: .move(edge: .trailing).combined(with: .opacity)
                    ))
            }
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.MemoryQuestionView.container)
    }

    // MARK: - Stimulus Phase

    private var stimulusPhase: some View {
        VStack(spacing: 24) {
            // Stimulus card
            VStack(alignment: .leading, spacing: 20) {
                // Header
                HStack {
                    Text("question.card.question.of.format".localized(with: questionNumber, totalQuestions))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)

                    Spacer()

                    // Memory type badge
                    HStack(spacing: 4) {
                        Image(systemName: "lightbulb.circle")
                            .font(.caption)
                        Text("memory.question.memorize".localized)
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.indigo.opacity(0.15))
                    .foregroundColor(.indigo)
                    .cornerRadius(8)
                }

                // Instruction
                Text("memory.question.remember.content".localized)
                    .font(.headline)
                    .foregroundColor(.primary)

                // Stimulus content
                if let stimulus = question.stimulus {
                    Text(stimulus)
                        .font(.title3)
                        .fontWeight(.medium)
                        .fixedSize(horizontal: false, vertical: true)
                        .foregroundColor(.primary)
                        .accessibilityIdentifier(AccessibilityIdentifiers.MemoryQuestionView.stimulusText)
                }

                // Difficulty indicator
                DifficultyBadge(difficultyLevel: question.difficultyLevel)
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: Color.black.opacity(0.1), radius: 8, x: 0, y: 4)
            .accessibilityElement(children: .combine)
            .accessibilityLabel(stimulusAccessibilityLabel)
            .accessibilityIdentifier(AccessibilityIdentifiers.MemoryQuestionView.stimulusCard)

            // Continue button
            PrimaryButton(
                title: "memory.question.continue".localized,
                action: {
                    if reduceMotion {
                        showingStimulus = false
                    } else {
                        withAnimation(.easeInOut(duration: 0.3)) {
                            showingStimulus = false
                        }
                    }
                },
                isDisabled: isDisabled,
                accessibilityId: AccessibilityIdentifiers.MemoryQuestionView.continueButton
            )
        }
    }

    // MARK: - Question Phase

    private var questionPhase: some View {
        VStack(spacing: 24) {
            // Question card (reuse QuestionCardView pattern)
            QuestionCardView(
                question: question,
                questionNumber: questionNumber,
                totalQuestions: totalQuestions
            )

            // Answer input
            AnswerInputView(
                question: question,
                userAnswer: $userAnswer,
                isDisabled: isDisabled
            )
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.MemoryQuestionView.questionPhase)
    }

    // MARK: - Accessibility

    private var stimulusAccessibilityLabel: String {
        let stimulus = question.stimulus ?? ""
        return "memory.question.stimulus.accessibility".localized(with: stimulus)
    }
}

// MARK: - Preview

#Preview("Stimulus Phase") {
    ScrollView {
        MemoryQuestionView(
            question: MockDataFactory.makeMemoryQuestion(
                id: 1,
                stimulus: "Apple, Banana, Cherry, Date, Elderberry",
                questionText: "Which of the following fruits did you see in the list?",
                difficultyLevel: "medium",
                answerOptions: ["Apple", "Grape", "Mango", "Kiwi"]
            ),
            questionNumber: 5,
            totalQuestions: 20,
            userAnswer: .constant(""),
            showingStimulus: .constant(true)
        )
        .padding()
    }
}

#Preview("Question Phase") {
    // Note: In actual preview, you'd need to manipulate state
    ScrollView {
        VStack(spacing: 24) {
            QuestionCardView(
                question: MockDataFactory.makeMemoryQuestion(
                    id: 1,
                    stimulus: "Apple, Banana, Cherry",
                    questionText: "Which of the following fruits did you see in the list?",
                    difficultyLevel: "medium",
                    answerOptions: ["Apple", "Grape", "Mango", "Kiwi"]
                ),
                questionNumber: 5,
                totalQuestions: 20
            )

            AnswerInputView(
                question: MockDataFactory.makeMemoryQuestion(
                    id: 1,
                    stimulus: "Apple, Banana, Cherry",
                    questionText: "Which of the following fruits did you see in the list?",
                    difficultyLevel: "medium",
                    answerOptions: ["Apple", "Grape", "Mango", "Kiwi"]
                ),
                userAnswer: .constant("")
            )
        }
        .padding()
    }
}
