import SwiftUI

/// A card view that displays a single question with appropriate styling
struct QuestionCardView: View {
    let question: Question
    let questionNumber: Int
    let totalQuestions: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // Question header with number and type
            questionHeader

            // Question text
            Text(question.questionText)
                .font(.title3)
                .fontWeight(.medium)
                .fixedSize(horizontal: false, vertical: true)
                .foregroundColor(.primary)
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionText)

            // Difficulty indicator
            DifficultyBadge(difficultyLevel: question.difficultyLevel)
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.1), radius: 8, x: 0, y: 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityQuestionLabel)
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionCard)
    }

    // MARK: - Accessibility

    private var accessibilityQuestionLabel: String {
        "question.card.question.accessibility".localized(
            with: questionNumber,
            totalQuestions,
            question.questionType.capitalized,
            question.difficultyLevel.capitalized,
            question.questionText
        )
    }

    private var questionHeader: some View {
        HStack {
            // Question number
            Text("question.card.question.of.format".localized(with: questionNumber, totalQuestions))
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)

            Spacer()

            // Question type badge
            HStack(spacing: 4) {
                Image(systemName: iconForQuestionType)
                    .font(.caption)
                Text(question.questionType.capitalized)
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(colorForQuestionType.opacity(0.15))
            .foregroundColor(colorForQuestionType)
            .cornerRadius(8)
        }
    }

    // MARK: - Helpers

    private var iconForQuestionType: String {
        switch question.questionTypeEnum {
        case .pattern: "grid.circle"
        case .logic: "brain.head.profile"
        case .spatial: "cube"
        case .math: "number.circle"
        case .verbal: "text.quote"
        case .memory: "lightbulb.circle"
        case nil: "questionmark.circle"
        }
    }

    private var colorForQuestionType: Color {
        switch question.questionTypeEnum {
        case .pattern: .blue
        case .logic: .purple
        case .spatial: .orange
        case .math: .green
        case .verbal: .pink
        case .memory: .indigo
        case nil: .gray
        }
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
            ),
            questionNumber: 1,
            totalQuestions: 20
        )
        .padding()

        QuestionCardView(
            question: MockDataFactory.makeQuestion(
                id: 2,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange",
                questionType: "logic",
                difficultyLevel: "easy"
            ),
            questionNumber: 2,
            totalQuestions: 20
        )
        .padding()
    }
}
