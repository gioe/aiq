import Foundation

/// Mock data support for TestTakingViewModel
extension TestTakingViewModel {
    var sampleQuestions: [Question] {
        [
            MockDataFactory.makeQuestion(
                id: 1,
                questionText: "What number comes next in this sequence: 2, 4, 8, 16, ?",
                questionType: "pattern",
                difficultyLevel: "easy"
            ),
            MockDataFactory.makeQuestion(
                id: 2,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange",
                questionType: "logic",
                difficultyLevel: "easy"
            ),
            MockDataFactory.makeQuestion(
                id: 3,
                questionText: "If all roses are flowers and some flowers fade quickly, then:",
                questionType: "logic",
                difficultyLevel: "medium"
            ),
            MockDataFactory.makeQuestion(
                id: 4,
                questionText: "What is 15% of 200?",
                questionType: "math",
                difficultyLevel: "easy"
            ),
            MockDataFactory.makeQuestion(
                id: 5,
                questionText: "Find the missing letter in the sequence: A, C, F, J, O, ?",
                questionType: "pattern",
                difficultyLevel: "medium"
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
                let newQuestion = MockDataFactory.makeQuestion(
                    id: allQuestions.count + 1,
                    questionText: question.questionText,
                    questionType: question.questionType,
                    difficultyLevel: question.difficultyLevel
                )
                allQuestions.append(newQuestion)
            }
        }

        questions = allQuestions
        testSession = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: TestStatus.inProgress.rawValue,
            startedAt: Date()
        )
    }
}
