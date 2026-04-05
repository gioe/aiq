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
    @Binding var userAnswer: String
    /// Whether we're showing the stimulus (true) or the question (false)
    @Binding var showingStimulus: Bool
    var isDisabled: Bool = false

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        VStack(spacing: 24) {
            if showingStimulus {
                stimulusPhase
                    .questionCardTransition(reduceMotion: reduceMotion)
            } else {
                questionPhase
                    .questionCardTransition(reduceMotion: reduceMotion)
            }
        }
        // .contain prevents iOS from promoting the "container" identifier down to a child
        // and overriding that child's own identifier (the same pattern used in QuestionCardView).
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.MemoryQuestionView.container)
    }

    // MARK: - Stimulus Phase

    private var stimulusPhase: some View {
        VStack(spacing: 24) {
            // Stimulus card
            VStack(alignment: .leading, spacing: 20) {
                // Instruction
                Text("memory.question.remember.content".localized)
                    .font(.headline)
                    .foregroundColor(.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                // Stimulus content
                if let stimulus = question.stimulus {
                    Text(stimulus)
                        .font(.title3)
                        .fontWeight(.medium)
                        .fixedSize(horizontal: false, vertical: true)
                        .foregroundColor(.primary)
                        // Supply an identifier so ScreenshotContainerView.isAccessibilityElement
                        // returns true — making it a leaf in the UIKit accessibility tree.
                        // Without an identifier (isAccessibilityElement = false), UIKit traverses
                        // into the secure canvas and the inner UIHostingController, creating a
                        // second SwiftUI accessibility context that breaks the parent VStack's
                        // .contain modifier.
                        .screenshotPrevented(
                            accessibilityIdentifier: AccessibilityIdentifiers.MemoryQuestionView.stimulusText
                        )
                }
            }
            .padding(DesignSystem.Spacing.xxl)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.systemBackground))
            .cornerRadius(DesignSystem.CornerRadius.lg)
            .shadowStyle(DesignSystem.Shadow.md)
            // .contain makes the VStack a real otherElement container in XCUITest.
            // This works here because the VStack has native SwiftUI children (HStack, Text)
            // alongside the UIViewRepresentable — .contain requires at least one native
            // SwiftUI accessible child to form a real container.
            .accessibilityElement(children: .contain)
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
            QuestionCardView(question: question, questionNumber: questionNumber)

            // Answer input
            AnswerInputView(
                question: question,
                userAnswer: $userAnswer,
                isDisabled: isDisabled
            )
        }
        // .contain prevents iOS from promoting the "questionPhase" identifier down to QuestionCardView,
        // which would override QuestionCardView's own "questionCard" identifier (same pattern as stimulusCard).
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.MemoryQuestionView.questionPhase)
    }

    // MARK: - Accessibility

    private var stimulusAccessibilityLabel: String {
        let stimulus = question.stimulus ?? ""
        return "memory.question.stimulus.accessibility".localized(with: stimulus)
    }
}

#if DebugBuild

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
                    questionNumber: 1
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
#endif
