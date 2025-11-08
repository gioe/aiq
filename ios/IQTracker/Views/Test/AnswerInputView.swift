import SwiftUI

/// View for collecting user answers to questions
struct AnswerInputView: View {
    let question: Question
    @Binding var userAnswer: String

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Your Answer")
                .font(.headline)
                .foregroundColor(.primary)

            if question.isMultipleChoice {
                // Multiple choice options
                multipleChoiceOptions
            } else {
                // Text input for open-ended questions
                textInputField
            }
        }
    }

    private var multipleChoiceOptions: some View {
        VStack(spacing: 12) {
            ForEach(question.answerOptions ?? [], id: \.self) { option in
                OptionButton(
                    option: option,
                    isSelected: userAnswer == option,
                    action: {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                            userAnswer = option
                        }
                    }
                )
            }
        }
    }

    private var textInputField: some View {
        TextField("Type your answer here", text: $userAnswer)
            .font(.body)
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(userAnswer.isEmpty ? Color.clear : Color.accentColor, lineWidth: 2)
            )
    }
}

// MARK: - Option Button

private struct OptionButton: View {
    let option: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Text(option)
                    .font(.body)
                    .foregroundColor(isSelected ? .white : .primary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.white)
                }
            }
            .padding()
            .background(isSelected ? Color.accentColor : Color(.systemGray6))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.clear : Color(.systemGray4), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 30) {
        // Multiple choice example
        AnswerInputView(
            question: Question(
                id: 1,
                questionText: "Which word doesn't belong?",
                questionType: .logic,
                difficultyLevel: .easy,
                answerOptions: ["Apple", "Banana", "Carrot", "Orange"],
                explanation: nil
            ),
            userAnswer: .constant("Carrot")
        )
        .padding()

        // Text input example
        AnswerInputView(
            question: Question(
                id: 2,
                questionText: "What number comes next?",
                questionType: .pattern,
                difficultyLevel: .medium,
                answerOptions: nil,
                explanation: nil
            ),
            userAnswer: .constant("32")
        )
        .padding()
    }
}
