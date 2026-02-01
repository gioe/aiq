import SwiftUI

/// A card view that displays a single question with appropriate styling
struct QuestionCardView: View {
    let question: Question

    var body: some View {
        Text(question.questionText)
            .font(.title3)
            .fontWeight(.medium)
            .fixedSize(horizontal: false, vertical: true)
            .foregroundColor(.primary)
            .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionText)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(24)
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: Color.black.opacity(0.1), radius: 8, x: 0, y: 4)
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
