import SwiftUI

/// A card view that displays a single question with appropriate styling
struct QuestionCardView: View {
    let question: Question

    var body: some View {
        // VStack with .accessibilityElement(children: .contain) is intentional:
        // it forces an `otherElement` container in XCTest so that
        // `app.otherElements["testTakingView.questionCard"]` finds the card AND
        // `app.staticTexts["testTakingView.questionText"]` finds the inner Text.
        // Without .accessibilityElement(children: .contain), the VStack is transparent
        // and iOS promotes the outer identifier down to the child Text, overriding
        // the inner identifier and making both queries fail.
        VStack(alignment: .leading) {
            Text(question.questionText)
                .font(.title3)
                .fontWeight(.medium)
                .fixedSize(horizontal: false, vertical: true)
                .foregroundColor(.primary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionText)
        }
        .padding(24)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.1), radius: 8, x: 0, y: 4)
        // .accessibilityElement(children: .contain) forces the VStack to be a real
        // otherElement container in XCTest rather than being transparent (accessibility-
        // transparent VStacks promote their identifier to the child, overriding the child's
        // own identifier). With .contain, app.otherElements["questionCard"] finds the card
        // and app.staticTexts["questionText"] finds the inner Text.
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionCard)
    }
}

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
