import SwiftUI

/// View for collecting user answers to questions
struct AnswerInputView: View {
    let question: Question
    @Binding var userAnswer: String
    var isDisabled: Bool = false
    @FocusState private var isTextFieldFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("answer.input.your.answer".localized)
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
            ForEach(Array((question.answerOptions ?? []).enumerated()), id: \.offset) { index, option in
                OptionButton(
                    option: option,
                    isSelected: userAnswer == option,
                    isDisabled: isDisabled,
                    accessibilityId: AccessibilityIdentifiers.TestTakingView.answerButton(at: index),
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
        VStack(alignment: .leading, spacing: 8) {
            TextField(placeholderText, text: $userAnswer)
                .font(.body)
                .keyboardType(keyboardType)
                .autocorrectionDisabled(shouldDisableAutocorrection)
                .textInputAutocapitalization(capitalizationType)
                .focused($isTextFieldFocused)
                .disabled(isDisabled)
                .padding()
                .background(isDisabled ? Color(.systemGray5) : Color(.systemGray6))
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(userAnswer.isEmpty ? Color.clear : Color.accentColor, lineWidth: 2)
                )
                .opacity(isDisabled ? 0.6 : 1.0)
                .accessibilityLabel("answer.input.field.label".localized)
                .accessibilityHint(isDisabled ? "answer.input.field.disabled".localized : accessibilityHint)
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.answerTextField)

            // Input hint based on question type
            if !inputHint.isEmpty {
                Text(inputHint)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .onAppear {
            // Auto-focus text field for better UX
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                isTextFieldFocused = true
            }
        }
    }

    // MARK: - Input Configuration

    private var keyboardType: UIKeyboardType {
        switch question.questionType {
        case .math:
            // Use decimal pad for math questions to allow numbers and decimals
            .decimalPad
        case .pattern where question.questionText.lowercased().contains("number"):
            // Pattern questions about numbers should use number pad
            .numberPad
        default:
            // Default to regular keyboard for text-based answers
            .default
        }
    }

    private var shouldDisableAutocorrection: Bool {
        // Disable autocorrection for math, pattern, and spatial questions
        switch question.questionType {
        case .math, .pattern, .spatial:
            true
        default:
            false
        }
    }

    private var capitalizationType: TextInputAutocapitalization {
        // Use sentence capitalization for verbal questions, none for others
        switch question.questionType {
        case .verbal:
            .sentences
        default:
            .never
        }
    }

    private var placeholderText: String {
        switch question.questionType {
        case .math:
            "answer.input.placeholder.math".localized
        case .pattern:
            if question.questionText.lowercased().contains("number") {
                "answer.input.placeholder.number".localized
            } else if question.questionText.lowercased().contains("letter") {
                "answer.input.placeholder.letter".localized
            } else {
                "answer.input.placeholder.default".localized
            }
        case .verbal:
            "answer.input.placeholder.default".localized
        case .spatial:
            "answer.input.placeholder.default".localized
        case .logic:
            "answer.input.placeholder.default".localized
        case .memory:
            "answer.input.placeholder.default".localized
        }
    }

    private var inputHint: String {
        switch question.questionType {
        case .math:
            "answer.input.hint.math".localized
        case .pattern where question.questionText.lowercased().contains("letter"):
            "answer.input.hint.letter".localized
        case .pattern where question.questionText.lowercased().contains("number"):
            "answer.input.hint.number".localized
        default:
            ""
        }
    }

    private var accessibilityHint: String {
        "answer.input.field.hint.default".localized(with: inputHint)
    }
}

// MARK: - Option Button

private struct OptionButton: View {
    let option: String
    let isSelected: Bool
    var isDisabled: Bool = false
    var accessibilityId: String?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Text(option)
                    .font(.body)
                    .foregroundColor(foregroundColor)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .multilineTextAlignment(.leading)

                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(isDisabled ? .gray : .white)
                }
            }
            .padding()
            .background(backgroundColor)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.clear : Color(.systemGray4), lineWidth: 1)
            )
            .opacity(isDisabled ? 0.6 : 1.0)
        }
        .buttonStyle(.plain)
        .disabled(isDisabled)
        .accessibilityLabel(option)
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
        .accessibilityHint(accessibilityHintText)
        .optionalAccessibilityIdentifier(accessibilityId)
    }

    private var foregroundColor: Color {
        if isDisabled {
            return isSelected ? .white.opacity(0.8) : .secondary
        }
        return isSelected ? .white : .primary
    }

    private var backgroundColor: Color {
        if isDisabled {
            return isSelected ? Color.accentColor.opacity(0.5) : Color(.systemGray5)
        }
        return isSelected ? Color.accentColor : Color(.systemGray6)
    }

    private var accessibilityHintText: String {
        if isDisabled {
            return "answer.input.field.disabled".localized
        }
        return isSelected ? "answer.input.option.selected".localized : "answer.input.option.select".localized
    }
}

// MARK: - Preview

#Preview("Multiple Choice") {
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
}

#Preview("Math Question") {
    AnswerInputView(
        question: Question(
            id: 2,
            questionText: "What is 15% of 200?",
            questionType: .math,
            difficultyLevel: .easy,
            answerOptions: nil,
            explanation: nil
        ),
        userAnswer: .constant("")
    )
    .padding()
}

#Preview("Pattern Question - Number") {
    AnswerInputView(
        question: Question(
            id: 3,
            questionText: "What number comes next in the sequence: 2, 4, 8, 16, ?",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        ),
        userAnswer: .constant("")
    )
    .padding()
}

#Preview("Pattern Question - Letter") {
    AnswerInputView(
        question: Question(
            id: 4,
            questionText: "What letter comes next: A, C, F, J, ?",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        ),
        userAnswer: .constant("")
    )
    .padding()
}

#Preview("Verbal Question") {
    AnswerInputView(
        question: Question(
            id: 5,
            questionText: "Complete the analogy: Dog is to puppy as cat is to ___",
            questionType: .verbal,
            difficultyLevel: .easy,
            answerOptions: nil,
            explanation: nil
        ),
        userAnswer: .constant("")
    )
    .padding()
}
