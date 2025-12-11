import Foundation

/// Mock data support for TestTakingViewModel
extension TestTakingViewModel {
    var sampleQuestions: [Question] {
        [
            Question(
                id: 1,
                questionText: "What number comes next in this sequence: 2, 4, 8, 16, ?",
                questionType: .pattern,
                difficultyLevel: .easy,
                answerOptions: nil,
                explanation: "The pattern is doubling: 2×2=4, 4×2=8, 8×2=16, 16×2=32"
            ),
            Question(
                id: 2,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange",
                questionType: .logic,
                difficultyLevel: .easy,
                answerOptions: ["Apple", "Banana", "Carrot", "Orange"],
                explanation: "Carrot is a vegetable, while the others are fruits"
            ),
            Question(
                id: 3,
                questionText: "If all roses are flowers and some flowers fade quickly, then:",
                questionType: .logic,
                difficultyLevel: .medium,
                answerOptions: [
                    "All roses fade quickly",
                    "Some roses might fade quickly",
                    "No roses fade quickly",
                    "Cannot be determined"
                ],
                explanation: "We can only conclude that some roses might fade quickly"
            ),
            Question(
                id: 4,
                questionText: "What is 15% of 200?",
                questionType: .math,
                difficultyLevel: .easy,
                answerOptions: nil,
                explanation: "15% of 200 = 0.15 × 200 = 30"
            ),
            Question(
                id: 5,
                questionText: "Find the missing letter in the sequence: A, C, F, J, O, ?",
                questionType: .pattern,
                difficultyLevel: .medium,
                answerOptions: nil,
                explanation: "The gaps increase by 1 each time: +1, +2, +3, +4, +5 → U"
            )
        ]
    }

    func loadMockQuestions(count: Int) {
        let mockQuestions = sampleQuestions

        // Repeat questions to reach desired count
        var allQuestions: [Question] = []
        while allQuestions.count < count {
            for question in mockQuestions {
                if allQuestions.count >= count { break }
                // Create a copy with a new ID
                let newQuestion = Question(
                    id: allQuestions.count + 1,
                    questionText: question.questionText,
                    questionType: question.questionType,
                    difficultyLevel: question.difficultyLevel,
                    answerOptions: question.answerOptions,
                    explanation: question.explanation
                )
                allQuestions.append(newQuestion)
            }
        }

        questions = allQuestions
        testSession = TestSession(
            id: 1,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: allQuestions,
            timeLimitExceeded: false
        )
    }
}
