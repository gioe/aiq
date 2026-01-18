@testable import AIQ
import AIQAPIClient
import XCTest

/// Tests for the UI extension computed properties on OpenAPI-generated types.
/// These extensions live in the AIQAPIClient package and provide formatting,
/// display helpers, and accessibility properties for the generated models.
final class AIQAPIClientExtensionsTests: XCTestCase {
    // MARK: - TestResultResponse Extension Tests

    func testTestResultResponse_accuracy_convertsPercentageToDecimal() {
        let result = createTestResult(accuracyPercentage: 75.0)
        XCTAssertEqual(result.accuracy, 0.75, accuracy: 0.001)
    }

    func testTestResultResponse_accuracy_handles100Percent() {
        let result = createTestResult(accuracyPercentage: 100.0)
        XCTAssertEqual(result.accuracy, 1.0, accuracy: 0.001)
    }

    func testTestResultResponse_accuracy_handles0Percent() {
        let result = createTestResult(accuracyPercentage: 0.0)
        XCTAssertEqual(result.accuracy, 0.0, accuracy: 0.001)
    }

    func testTestResultResponse_accuracyFormatted_roundsToInteger() {
        let result = createTestResult(accuracyPercentage: 75.6)
        XCTAssertEqual(result.accuracyFormatted, "76%")
    }

    func testTestResultResponse_accuracyFormatted_handles100Percent() {
        let result = createTestResult(accuracyPercentage: 100.0)
        XCTAssertEqual(result.accuracyFormatted, "100%")
    }

    func testTestResultResponse_accuracyFormatted_handles0Percent() {
        let result = createTestResult(accuracyPercentage: 0.0)
        XCTAssertEqual(result.accuracyFormatted, "0%")
    }

    func testTestResultResponse_iqScoreFormatted() {
        let result = createTestResult(iqScore: 115)
        XCTAssertEqual(result.iqScoreFormatted, "115")
    }

    func testTestResultResponse_scoreRatio() {
        let result = createTestResult(totalQuestions: 20, correctAnswers: 18)
        XCTAssertEqual(result.scoreRatio, "18/20")
    }

    func testTestResultResponse_scoreRatio_perfectScore() {
        let result = createTestResult(totalQuestions: 20, correctAnswers: 20)
        XCTAssertEqual(result.scoreRatio, "20/20")
    }

    func testTestResultResponse_scoreRatio_zeroScore() {
        let result = createTestResult(totalQuestions: 20, correctAnswers: 0)
        XCTAssertEqual(result.scoreRatio, "0/20")
    }

    func testTestResultResponse_accessibilityDescription_containsAllInfo() {
        let result = createTestResult(
            iqScore: 110,
            totalQuestions: 20,
            correctAnswers: 18,
            accuracyPercentage: 90.0
        )
        let description = result.accessibilityDescription

        XCTAssertTrue(description.contains("110"), "Should contain IQ score")
        XCTAssertTrue(description.contains("18"), "Should contain correct answers")
        XCTAssertTrue(description.contains("20"), "Should contain total questions")
        XCTAssertTrue(description.contains("90%"), "Should contain accuracy")
    }

    // MARK: - ConfidenceIntervalSchema Extension Tests

    func testConfidenceInterval_rangeFormatted() {
        let ci = createConfidenceInterval(lower: 101, upper: 115)
        XCTAssertEqual(ci.rangeFormatted, "101-115")
    }

    func testConfidenceInterval_confidencePercentage() {
        let ci = createConfidenceInterval(confidenceLevel: 0.95)
        XCTAssertEqual(ci.confidencePercentage, 95)
    }

    func testConfidenceInterval_confidencePercentage_rounds() {
        let ci = createConfidenceInterval(confidenceLevel: 0.956)
        XCTAssertEqual(ci.confidencePercentage, 96)
    }

    func testConfidenceInterval_fullDescription() {
        let ci = createConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95)
        XCTAssertEqual(ci.fullDescription, "95% confidence interval: 101-115")
    }

    func testConfidenceInterval_accessibilityDescription() {
        let ci = createConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95)
        let description = ci.accessibilityDescription

        XCTAssertTrue(description.contains("101"), "Should contain lower bound")
        XCTAssertTrue(description.contains("115"), "Should contain upper bound")
        XCTAssertTrue(description.contains("95"), "Should contain confidence percentage")
    }

    func testConfidenceInterval_intervalWidth() {
        let ci = createConfidenceInterval(lower: 101, upper: 115)
        XCTAssertEqual(ci.intervalWidth, 14)
    }

    func testConfidenceInterval_intervalWidth_narrowInterval() {
        let ci = createConfidenceInterval(lower: 108, upper: 112)
        XCTAssertEqual(ci.intervalWidth, 4)
    }

    func testConfidenceInterval_standardErrorFormatted() {
        let ci = createConfidenceInterval(standardError: 4.5678)
        XCTAssertEqual(ci.standardErrorFormatted, "4.57")
    }

    func testConfidenceInterval_standardErrorFormatted_roundsCorrectly() {
        let ci = createConfidenceInterval(standardError: 4.556)
        XCTAssertEqual(ci.standardErrorFormatted, "4.56")
    }

    // MARK: - UserResponse Extension Tests

    func testUserResponse_fullName() {
        let user = createUser(firstName: "John", lastName: "Smith")
        XCTAssertEqual(user.fullName, "John Smith")
    }

    func testUserResponse_initials_normalNames() {
        let user = createUser(firstName: "John", lastName: "Smith")
        XCTAssertEqual(user.initials, "JS")
    }

    func testUserResponse_initials_lowercaseNames() {
        let user = createUser(firstName: "john", lastName: "smith")
        XCTAssertEqual(user.initials, "JS")
    }

    func testUserResponse_initials_emptyFirstName() {
        let user = createUser(firstName: "", lastName: "Smith")
        XCTAssertEqual(user.initials, "?S")
    }

    func testUserResponse_initials_emptyLastName() {
        let user = createUser(firstName: "John", lastName: "")
        XCTAssertEqual(user.initials, "J?")
    }

    func testUserResponse_initials_bothEmpty() {
        let user = createUser(firstName: "", lastName: "")
        XCTAssertEqual(user.initials, "??")
    }

    func testUserResponse_initials_whitespaceOnly() {
        let user = createUser(firstName: "   ", lastName: "   ")
        XCTAssertEqual(user.initials, "??")
    }

    func testUserResponse_notificationStatus_enabled() {
        let user = createUser(notificationEnabled: true)
        XCTAssertEqual(user.notificationStatus, "Notifications enabled")
    }

    func testUserResponse_notificationStatus_disabled() {
        let user = createUser(notificationEnabled: false)
        XCTAssertEqual(user.notificationStatus, "Notifications disabled")
    }

    func testUserResponse_accessibilityDescription() {
        let user = createUser(
            firstName: "John",
            lastName: "Smith",
            email: "john@example.com",
            notificationEnabled: true
        )
        let description = user.accessibilityDescription

        XCTAssertTrue(description.contains("John Smith"), "Should contain full name")
        XCTAssertTrue(description.contains("john@example.com"), "Should contain email")
        XCTAssertTrue(description.contains("Notifications enabled"), "Should contain status")
    }

    // MARK: - QuestionResponse Extension Tests

    func testQuestionResponse_questionTypeDisplay_capitalized() {
        let question = createQuestion(questionType: "pattern")
        XCTAssertEqual(question.questionTypeDisplay, "Pattern")
    }

    func testQuestionResponse_questionTypeFullName_pattern() {
        let question = createQuestion(questionType: "pattern")
        XCTAssertEqual(question.questionTypeFullName, "Pattern Recognition")
    }

    func testQuestionResponse_questionTypeFullName_logic() {
        let question = createQuestion(questionType: "logic")
        XCTAssertEqual(question.questionTypeFullName, "Logical Reasoning")
    }

    func testQuestionResponse_questionTypeFullName_spatial() {
        let question = createQuestion(questionType: "spatial")
        XCTAssertEqual(question.questionTypeFullName, "Spatial Reasoning")
    }

    func testQuestionResponse_questionTypeFullName_math() {
        let question = createQuestion(questionType: "math")
        XCTAssertEqual(question.questionTypeFullName, "Mathematical")
    }

    func testQuestionResponse_questionTypeFullName_verbal() {
        let question = createQuestion(questionType: "verbal")
        XCTAssertEqual(question.questionTypeFullName, "Verbal Reasoning")
    }

    func testQuestionResponse_questionTypeFullName_memory() {
        let question = createQuestion(questionType: "memory")
        XCTAssertEqual(question.questionTypeFullName, "Memory")
    }

    func testQuestionResponse_questionTypeFullName_unknownType() {
        let question = createQuestion(questionType: "unknown")
        XCTAssertEqual(question.questionTypeFullName, "Unknown")
    }

    func testQuestionResponse_difficultyDisplay_capitalized() {
        let question = createQuestion(difficultyLevel: "easy")
        XCTAssertEqual(question.difficultyDisplay, "Easy")
    }

    func testQuestionResponse_accessibilityDescription() {
        let question = createQuestion(
            id: 42,
            questionType: "pattern",
            difficultyLevel: "medium"
        )
        let description = question.accessibilityDescription

        XCTAssertTrue(description.contains("42"), "Should contain question ID")
        XCTAssertTrue(description.contains("Pattern Recognition"), "Should contain full type name")
        XCTAssertTrue(description.contains("Medium"), "Should contain formatted difficulty")
    }

    func testQuestionResponse_accessibilityHint() {
        let question = createQuestion(
            questionType: "logic",
            difficultyLevel: "hard"
        )
        let hint = question.accessibilityHint

        XCTAssertTrue(hint.contains("Hard"), "Should contain formatted difficulty")
        XCTAssertTrue(hint.contains("Logic"), "Should contain formatted type")
    }

    // MARK: - Test Helpers

    private func createTestResult(
        id: Int = 1,
        testSessionId: Int = 1,
        userId: Int = 1,
        iqScore: Int = 100,
        totalQuestions: Int = 20,
        correctAnswers: Int = 15,
        accuracyPercentage: Double = 75.0,
        completedAt: Date = Date()
    ) -> Components.Schemas.TestResultResponse {
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

    private func createConfidenceInterval(
        lower: Int = 95,
        upper: Int = 105,
        confidenceLevel: Double = 0.95,
        standardError: Double = 5.0
    ) -> Components.Schemas.ConfidenceIntervalSchema {
        Components.Schemas.ConfidenceIntervalSchema(
            confidenceLevel: confidenceLevel,
            lower: lower,
            standardError: standardError,
            upper: upper
        )
    }

    private func createUser(
        id: Int = 1,
        firstName: String = "Test",
        lastName: String = "User",
        email: String = "test@example.com",
        createdAt: Date = Date(),
        notificationEnabled: Bool = true
    ) -> Components.Schemas.UserResponse {
        Components.Schemas.UserResponse(
            createdAt: createdAt,
            email: email,
            firstName: firstName,
            id: id,
            lastName: lastName,
            notificationEnabled: notificationEnabled
        )
    }

    private func createQuestion(
        id: Int = 1,
        questionType: String = "pattern",
        difficultyLevel: String = "medium",
        questionText: String = "Test question?"
    ) -> Components.Schemas.QuestionResponse {
        Components.Schemas.QuestionResponse(
            difficultyLevel: difficultyLevel,
            id: id,
            questionText: questionText,
            questionType: questionType
        )
    }
}
