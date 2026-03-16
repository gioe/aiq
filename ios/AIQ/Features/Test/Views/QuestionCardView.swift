import SwiftUI

/// A card view that displays a single question with appropriate styling
struct QuestionCardView: View {
    let question: Question

    var body: some View {
        // ScrollView with .accessibilityElement(children: .contain) is intentional:
        // it forces an `otherElement` container in XCTest so that
        // `app.otherElements["testTakingView.questionCard"]` finds the card AND
        // `app.staticTexts["testTakingView.questionText"]` finds the inner Text.
        // Without .accessibilityElement(children: .contain), the container is transparent
        // and iOS promotes the outer identifier down to the child Text, overriding
        // the inner identifier and making both queries fail.
        // The ScrollView also allows long question text to scroll within the height cap
        // so AnswerInputView remains visible on small devices.
        ScrollView {
            VStack(alignment: .leading) {
                Text(question.questionText)
                    .font(.title3)
                    .fontWeight(.medium)
                    .fixedSize(horizontal: false, vertical: true)
                    .foregroundColor(.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .screenshotPrevented(
                        accessibilityIdentifier: AccessibilityIdentifiers.TestTakingView.questionText
                    )
            }
            .padding(DesignSystem.Spacing.lg)
        }
        .frame(maxWidth: .infinity, maxHeight: 240)
        .background(Color(.systemBackground))
        .cornerRadius(DesignSystem.CornerRadius.lg)
        .shadowStyle(DesignSystem.Shadow.md)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionCard)
    }
}

#if DEBUG

    // MARK: - Preview

    #Preview {
        VStack {
            QuestionCardView(
                question: MockDataFactory.makeQuestion(
                    id: 1,
                    questionText: "What number comes next in this sequence: 2, 4, 8, 16, ?",
                    questionType: "pattern",
                    difficultyLevel: "medium"
                )
            )
            .padding()

            QuestionCardView(
                question: MockDataFactory.makeQuestion(
                    id: 2,
                    questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange",
                    questionType: "logic",
                    difficultyLevel: "easy"
                )
            )
            .padding()
        }
    }
#endif
