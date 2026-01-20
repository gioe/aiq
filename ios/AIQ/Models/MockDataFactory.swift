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
            completedAt: status == "completed" ? (completedAt ?? startedAt.addingTimeInterval(1800)) : nil,
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
    static func makeQuestion(
        id: Int,
        questionText: String,
        questionType: String,
        difficultyLevel: String
    ) -> Question {
        Components.Schemas.QuestionResponse(
            difficultyLevel: difficultyLevel,
            id: id,
            questionText: questionText,
            questionType: questionType
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
                difficultyLevel: "easy"
            ),
            makeQuestion(
                id: 2,
                questionText: "What is 15% of 200?",
                questionType: "math",
                difficultyLevel: "easy"
            ),
            makeQuestion(
                id: 3,
                questionText: "What number comes next: 2, 4, 8, 16, ?",
                questionType: "pattern",
                difficultyLevel: "medium"
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
