import SwiftUI

/// A card view that displays a single question with appropriate styling
struct QuestionCardView: View {
    let question: Question

    var body: some View {
        // The question text uses screenshotPrevented (UIViewRepresentable) to prevent
        // it from appearing in screen captures.  A VStack whose ONLY child is a
        // UIViewRepresentable cannot form a real accessibility container even with
        // .accessibilityElement(children: .contain) — iOS silently bypasses the
        // modifier, making the identifier invisible to XCUITest.
        //
        // Fix: attach questionCard as an overlay element instead of as a .contain
        // container.  Color.clear with .accessibilityElement(children: .ignore)
        // creates a pure-SwiftUI otherElement at the card's position that XCUITest
        // can query.  The inner screenshotPrevented Text retains its own
        // "questionText" identifier and is not affected by the overlay.
        VStack(alignment: .leading) {
            Text(question.questionText)
                .font(.title3)
                .fontWeight(.medium)
                .foregroundColor(.primary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .screenshotPrevented(
                    accessibilityIdentifier: AccessibilityIdentifiers.TestTakingView.questionText,
                    accessibilityLabel: question.questionText
                )
        }
        .padding(DesignSystem.Spacing.lg)
        .frame(maxWidth: .infinity)
        .background(Color(.systemBackground))
        .cornerRadius(DesignSystem.CornerRadius.lg)
        .shadowStyle(DesignSystem.Shadow.md)
        .overlay(
            Color.clear
                .accessibilityElement(children: .ignore)
                .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.questionCard)
        )
    }
}

#if DebugBuild

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
