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
            difficultyBadge
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
        """
        Question \(questionNumber) of \(totalQuestions). \
        \(question.questionType.rawValue.capitalized) question. \
        Difficulty: \(question.difficultyLevel.rawValue.capitalized). \
        \(question.questionText)
        """
    }

    private var questionHeader: some View {
        HStack {
            // Question number
            Text("Question \(questionNumber) of \(totalQuestions)")
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)

            Spacer()

            // Question type badge
            HStack(spacing: 4) {
                Image(systemName: iconForQuestionType)
                    .font(.caption)
                Text(question.questionType.rawValue.capitalized)
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

    private var difficultyBadge: some View {
        HStack(spacing: 4) {
            ForEach(0 ..< 3) { index in
                Circle()
                    .fill(index < difficultyCircles ? colorForDifficulty : Color.gray.opacity(0.2))
                    .frame(width: 8, height: 8)
            }

            Text(question.difficultyLevel.rawValue.capitalized)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
        }
    }

    // MARK: - Helpers

    private var iconForQuestionType: String {
        switch question.questionType {
        case .pattern: "grid.circle"
        case .logic: "brain.head.profile"
        case .spatial: "cube"
        case .math: "number.circle"
        case .verbal: "text.quote"
        case .memory: "lightbulb.circle"
        }
    }

    private var colorForQuestionType: Color {
        switch question.questionType {
        case .pattern: .blue
        case .logic: .purple
        case .spatial: .orange
        case .math: .green
        case .verbal: .pink
        case .memory: .indigo
        }
    }

    private var difficultyCircles: Int {
        switch question.difficultyLevel {
        case .easy: 1
        case .medium: 2
        case .hard: 3
        }
    }

    private var colorForDifficulty: Color {
        switch question.difficultyLevel {
        case .easy: .green
        case .medium: .orange
        case .hard: .red
        }
    }
}

// MARK: - Preview

#Preview {
    VStack {
        QuestionCardView(
            question: Question(
                id: 1,
                questionText: "What number comes next in this sequence: 2, 4, 8, 16, ?",
                questionType: .pattern,
                difficultyLevel: .medium,
                answerOptions: nil,
                explanation: nil
            ),
            questionNumber: 1,
            totalQuestions: 20
        )
        .padding()

        QuestionCardView(
            question: Question(
                id: 2,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange",
                questionType: .logic,
                difficultyLevel: .easy,
                answerOptions: ["Apple", "Banana", "Carrot", "Orange"],
                explanation: nil
            ),
            questionNumber: 2,
            totalQuestions: 20
        )
        .padding()
    }
}
