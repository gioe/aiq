import AIQAPIClient
import Foundation

// MARK: - Mock Data Factory

/// Factory for creating mock data objects for SwiftUI previews.
///
/// The generated OpenAPI types have limited initializers and don't include optional properties.
/// This factory provides convenience methods for creating mock instances for preview purposes.
///
/// **Note:** This file is for preview/testing only and should not be used in production code.
enum MockDataFactory {
    // MARK: - TestResult Mock Data

    // Creates a mock TestResult for previews.
    //
    // The generated TestResultResponse only includes required properties. Optional properties
    // like percentileRank, completionTimeSeconds, domainScores, and confidenceInterval are not
    // available due to OpenAPI generator limitations.
    // swiftlint:disable:next function_parameter_count
    static func makeTestResult(
        id: Int,
        testSessionId: Int,
        userId: Int,
        iqScore: Int,
        totalQuestions: Int,
        correctAnswers: Int,
        accuracyPercentage: Double,
        completedAt: Date
    ) -> TestResult {
        Components.Schemas.TestResultResponse(
            accuracyPercentage: accuracyPercentage,
            completedAt: completedAt,
            correctAnswers: correctAnswers,
            id: id,
            iqScore: iqScore,
            testSessionId: testSessionId,
            totalQuestions: totalQuestions,
            userId: userId
        )
    }

    // MARK: - TestSession Mock Data

    /// Creates a mock TestSession for previews.
    static func makeTestSession(
        id: Int,
        userId: Int,
        status: String,
        startedAt: Date,
        completedAt: Date? = nil,
        timeLimitExceeded: Bool = false
    ) -> TestSession {
        Components.Schemas.TestSessionResponse(
            completedAt: status == "completed"
                ? (completedAt ?? startedAt.addingTimeInterval(TimeInterval(Constants.Timing.totalTestTimeSeconds)))
                : nil,
            id: id,
            startedAt: startedAt,
            status: status,
            timeLimitExceeded: timeLimitExceeded,
            userId: userId
        )
    }

    /// Creates an in-progress test session for previews.
    static func makeInProgressSession(
        id: Int = 123,
        userId: Int = 1,
        startedAt: Date = Date().addingTimeInterval(-3600)
    ) -> TestSession {
        makeTestSession(
            id: id,
            userId: userId,
            status: "in_progress",
            startedAt: startedAt
        )
    }

    // MARK: - Question Mock Data

    /// Creates a mock Question for previews.
    ///
    /// - Parameters:
    ///   - id: Question ID
    ///   - questionText: The question text
    ///   - questionType: Type of question (pattern, logic, math, verbal, spatial, memory)
    ///   - difficultyLevel: Difficulty level (easy, medium, hard)
    ///   - answerOptions: Optional array of answer options for multiple choice questions
    ///   - explanation: Optional explanation for the correct answer
    ///   - stimulus: Optional stimulus content for memory questions
    static func makeQuestion(
        id: Int,
        questionText: String,
        questionType: String,
        difficultyLevel: String,
        answerOptions: [String]? = nil,
        explanation: String? = nil,
        stimulus: String? = nil
    ) -> Question {
        Components.Schemas.QuestionResponse(
            answerOptions: answerOptions,
            difficultyLevel: difficultyLevel,
            explanation: explanation,
            id: id,
            questionText: questionText,
            questionType: questionType,
            stimulus: stimulus
        )
    }

    /// Creates a mock memory Question for previews.
    ///
    /// Memory questions have a stimulus field that contains content to memorize
    /// before answering the question.
    ///
    /// - Parameters:
    ///   - id: Question ID
    ///   - stimulus: Content to memorize before answering
    ///   - questionText: The question text (asked after hiding stimulus)
    ///   - difficultyLevel: Difficulty level (easy, medium, hard)
    ///   - answerOptions: Optional array of answer options for multiple choice questions
    ///   - explanation: Optional explanation for the correct answer
    static func makeMemoryQuestion(
        id: Int,
        stimulus: String,
        questionText: String,
        difficultyLevel: String,
        answerOptions: [String]? = nil,
        explanation: String? = nil
    ) -> Question {
        makeQuestion(
            id: id,
            questionText: questionText,
            questionType: "memory",
            difficultyLevel: difficultyLevel,
            answerOptions: answerOptions,
            explanation: explanation,
            stimulus: stimulus
        )
    }

    // MARK: - Sample Data Collections

    /// Sample test history for chart previews.
    static var sampleTestHistory: [TestResult] {
        [
            makeTestResult(
                id: 1,
                testSessionId: 1,
                userId: 1,
                iqScore: 105,
                totalQuestions: 20,
                correctAnswers: 13,
                accuracyPercentage: 65.0,
                completedAt: Date().addingTimeInterval(-30 * 24 * 60 * 60)
            ),
            makeTestResult(
                id: 2,
                testSessionId: 2,
                userId: 1,
                iqScore: 112,
                totalQuestions: 20,
                correctAnswers: 15,
                accuracyPercentage: 75.0,
                completedAt: Date().addingTimeInterval(-20 * 24 * 60 * 60)
            ),
            makeTestResult(
                id: 3,
                testSessionId: 3,
                userId: 1,
                iqScore: 118,
                totalQuestions: 20,
                correctAnswers: 17,
                accuracyPercentage: 85.0,
                completedAt: Date().addingTimeInterval(-10 * 24 * 60 * 60)
            ),
            makeTestResult(
                id: 4,
                testSessionId: 4,
                userId: 1,
                iqScore: 125,
                totalQuestions: 20,
                correctAnswers: 18,
                accuracyPercentage: 90.0,
                completedAt: Date()
            )
        ]
    }

    /// Sample test result with high score for result screen previews.
    static var highScoreResult: TestResult {
        makeTestResult(
            id: 1,
            testSessionId: 1,
            userId: 1,
            iqScore: 128,
            totalQuestions: 20,
            correctAnswers: 18,
            accuracyPercentage: 90.0,
            completedAt: Date()
        )
    }

    /// Sample test result with average score for result screen previews.
    static var averageScoreResult: TestResult {
        makeTestResult(
            id: 2,
            testSessionId: 2,
            userId: 1,
            iqScore: 102,
            totalQuestions: 20,
            correctAnswers: 11,
            accuracyPercentage: 55.0,
            completedAt: Date()
        )
    }

    /// Sample questions for test-taking previews.
    static var sampleQuestions: [Question] {
        [
            makeQuestion(
                id: 1,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange?",
                questionType: "logic",
                difficultyLevel: "easy",
                answerOptions: ["Apple", "Banana", "Carrot", "Orange"],
                explanation: "Carrot is a vegetable, while the others are fruits."
            ),
            makeQuestion(
                id: 2,
                questionText: "What is 15% of 200?",
                questionType: "math",
                difficultyLevel: "easy",
                explanation: "15% of 200 = 0.15 × 200 = 30"
            ),
            makeQuestion(
                id: 3,
                questionText: "What number comes next: 2, 4, 8, 16, ?",
                questionType: "pattern",
                difficultyLevel: "medium",
                explanation: "Each number doubles the previous one. 16 × 2 = 32"
            ),
            makeMemoryQuestion(
                id: 4,
                stimulus: "The sequence is: Red, Blue, Green, Yellow, Purple",
                questionText: "What was the third color in the sequence?",
                difficultyLevel: "easy",
                answerOptions: ["Blue", "Green", "Yellow", "Red"],
                explanation: "The third color in the sequence was Green."
            )
        ]
    }

    /// Sample memory questions for memory question previews and tests.
    static var sampleMemoryQuestions: [Question] {
        [
            makeMemoryQuestion(
                id: 101,
                stimulus: "The sequence is: Red, Blue, Green, Yellow, Purple",
                questionText: "What was the third color in the sequence?",
                difficultyLevel: "easy",
                answerOptions: ["Blue", "Green", "Yellow", "Red"],
                explanation: "The third color in the sequence was Green."
            ),
            makeMemoryQuestion(
                id: 102,
                stimulus: "Remember these numbers: 7, 3, 9, 2, 5, 8",
                questionText: "What was the fourth number in the list?",
                difficultyLevel: "medium",
                answerOptions: ["3", "9", "2", "5"],
                explanation: "The fourth number in the list was 2."
            ),
            makeMemoryQuestion(
                id: 103,
                // swiftlint:disable:next line_length
                stimulus: "The meeting schedule:\n• Monday: Team sync at 9am\n• Tuesday: Design review at 2pm\n• Wednesday: Sprint planning at 10am\n• Thursday: Client call at 3pm",
                questionText: "What day was the Design review scheduled?",
                difficultyLevel: "medium",
                answerOptions: ["Monday", "Tuesday", "Wednesday", "Thursday"],
                explanation: "The Design review was scheduled for Tuesday at 2pm."
            ),
            makeMemoryQuestion(
                id: 104,
                stimulus: "The code sequence is: A5-B2-C9-D1-E7-F4-G8-H3",
                questionText: "What letter was paired with the number 7?",
                difficultyLevel: "hard",
                answerOptions: ["D", "E", "F", "G"],
                explanation: "E was paired with 7 in the sequence E7."
            )
        ]
    }

    // MARK: - Extended Mock Data for Complex Previews

    /// Creates a sample PerformanceInsights object for previews showing an improving trend.
    static var improvingPerformanceInsights: PerformanceInsights {
        PerformanceInsights(from: [
            makeTestResult(
                id: 1,
                testSessionId: 1,
                userId: 1,
                iqScore: 105,
                totalQuestions: 20,
                correctAnswers: 14,
                accuracyPercentage: 70.0,
                completedAt: Date().addingTimeInterval(-86400 * 180)
            ),
            makeTestResult(
                id: 2,
                testSessionId: 2,
                userId: 1,
                iqScore: 110,
                totalQuestions: 20,
                correctAnswers: 15,
                accuracyPercentage: 75.0,
                completedAt: Date().addingTimeInterval(-86400 * 90)
            ),
            makeTestResult(
                id: 3,
                testSessionId: 3,
                userId: 1,
                iqScore: 118,
                totalQuestions: 20,
                correctAnswers: 17,
                accuracyPercentage: 85.0,
                completedAt: Date()
            )
        ])
    }

    /// Creates a sample PerformanceInsights object for previews showing stable performance.
    static var stablePerformanceInsights: PerformanceInsights {
        PerformanceInsights(from: [
            makeTestResult(
                id: 1,
                testSessionId: 1,
                userId: 1,
                iqScore: 115,
                totalQuestions: 20,
                correctAnswers: 16,
                accuracyPercentage: 80.0,
                completedAt: Date().addingTimeInterval(-86400 * 180)
            ),
            makeTestResult(
                id: 2,
                testSessionId: 2,
                userId: 1,
                iqScore: 113,
                totalQuestions: 20,
                correctAnswers: 16,
                accuracyPercentage: 80.0,
                completedAt: Date().addingTimeInterval(-86400 * 90)
            ),
            makeTestResult(
                id: 3,
                testSessionId: 3,
                userId: 1,
                iqScore: 117,
                totalQuestions: 20,
                correctAnswers: 17,
                accuracyPercentage: 85.0,
                completedAt: Date()
            )
        ])
    }
}
