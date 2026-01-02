import SwiftUI

/// Compact grid showing all questions with their status, allowing tap-to-navigate
struct QuestionNavigationGrid: View {
    let totalQuestions: Int
    let currentQuestionIndex: Int
    let answeredQuestionIndices: Set<Int>
    let onQuestionTap: (Int) -> Void

    private let columns = [
        GridItem(.adaptive(minimum: 44, maximum: 60), spacing: 8)
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "square.grid.3x3.fill")
                    .foregroundColor(.secondary)
                    .font(.caption)
                Text("question.navigator.title".localized)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .textCase(.uppercase)

                Spacer()

                // Legend
                HStack(spacing: 12) {
                    legendItem(color: .accentColor, label: "question.navigator.legend.current".localized)
                    legendItem(color: .green, label: "question.navigator.legend.answered".localized)
                    legendItem(color: Color(.systemGray4), label: "question.navigator.legend.unanswered".localized)
                }
                .font(.caption2)
            }

            // Grid
            LazyVGrid(columns: columns, spacing: 8) {
                ForEach(0 ..< totalQuestions, id: \.self) { index in
                    questionCell(for: index)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 8, x: 0, y: 2)
    }

    @ViewBuilder
    private func questionCell(for index: Int) -> some View {
        let isCurrent = index == currentQuestionIndex
        let isAnswered = answeredQuestionIndices.contains(index)

        Button {
            onQuestionTap(index)
        } label: {
            questionCellContent(index: index, isCurrent: isCurrent, isAnswered: isAnswered)
        }
        .buttonStyle(ScaleButtonStyle())
        .accessibilityLabel("question.navigator.accessibility.question".localized(with: index + 1))
        .accessibilityHint(accessibilityHintText(isCurrent: isCurrent, isAnswered: isAnswered))
    }

    @ViewBuilder
    private func questionCellContent(index: Int, isCurrent: Bool, isAnswered: Bool) -> some View {
        ZStack {
            // Background
            RoundedRectangle(cornerRadius: 8)
                .fill(cellBackgroundColor(isCurrent: isCurrent, isAnswered: isAnswered))

            // Border for current question
            if isCurrent {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(Color.accentColor, lineWidth: 2)
            }

            // Number
            Text("\(index + 1)")
                .font(.subheadline)
                .fontWeight(isCurrent ? .bold : .medium)
                .foregroundColor(cellTextColor(isCurrent: isCurrent, isAnswered: isAnswered))

            // Checkmark for answered
            if isAnswered && !isCurrent {
                VStack {
                    HStack {
                        Spacer()
                        Image(systemName: "checkmark.circle.fill")
                            .font(.caption2)
                            .foregroundColor(.white)
                            .padding(2)
                    }
                    Spacer()
                }
            }
        }
        .frame(minWidth: 44, minHeight: 44)
        .contentShape(Rectangle())
    }

    private func accessibilityHintText(isCurrent: Bool, isAnswered: Bool) -> String {
        if isCurrent {
            "question.navigator.accessibility.current".localized
        } else if isAnswered {
            "question.navigator.accessibility.answered".localized
        } else {
            "question.navigator.accessibility.not.answered".localized
        }
    }

    private func cellBackgroundColor(isCurrent: Bool, isAnswered: Bool) -> Color {
        if isCurrent {
            Color.accentColor.opacity(0.2)
        } else if isAnswered {
            Color.green.opacity(0.8)
        } else {
            Color(.systemGray5)
        }
    }

    private func cellTextColor(isCurrent: Bool, isAnswered: Bool) -> Color {
        if isCurrent {
            .accentColor
        } else if isAnswered {
            .white
        } else {
            .secondary
        }
    }

    private func legendItem(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Button Style

/// Button style that scales down on press for tactile feedback
struct ScaleButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(reduceMotion ? 1.0 : (configuration.isPressed ? 0.95 : 1.0))
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.1), value: configuration.isPressed)
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 30) {
        // Example: Early in test
        QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 2,
            answeredQuestionIndices: [0, 1],
            onQuestionTap: { _ in }
        )

        // Example: Mid test with some unanswered
        QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 10,
            answeredQuestionIndices: [0, 1, 2, 3, 5, 7, 8, 9],
            onQuestionTap: { _ in }
        )

        // Example: Near completion
        QuestionNavigationGrid(
            totalQuestions: 20,
            currentQuestionIndex: 18,
            answeredQuestionIndices: Set(0 ..< 18),
            onQuestionTap: { _ in }
        )
    }
    .padding()
    .background(Color(.systemGroupedBackground))
}
