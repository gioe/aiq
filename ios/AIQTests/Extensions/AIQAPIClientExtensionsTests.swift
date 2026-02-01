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
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 101, standardError: 5.0, upper: 115)
        XCTAssertEqual(ci.rangeFormatted, "101-115")
    }

    func testConfidenceInterval_confidencePercentage() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 95, standardError: 5.0, upper: 105)
        XCTAssertEqual(ci.confidencePercentage, 95)
    }

    func testConfidenceInterval_confidencePercentage_rounds() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.956, lower: 95, standardError: 5.0, upper: 105)
        XCTAssertEqual(ci.confidencePercentage, 96)
    }

    func testConfidenceInterval_fullDescription() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 101, standardError: 5.0, upper: 115)
        XCTAssertEqual(ci.fullDescription, "95% confidence interval: 101-115")
    }

    func testConfidenceInterval_accessibilityDescription() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 101, standardError: 5.0, upper: 115)
        let description = ci.accessibilityDescription

        XCTAssertTrue(description.contains("101"), "Should contain lower bound")
        XCTAssertTrue(description.contains("115"), "Should contain upper bound")
        XCTAssertTrue(description.contains("95"), "Should contain confidence percentage")
    }

    func testConfidenceInterval_intervalWidth() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 101, standardError: 5.0, upper: 115)
        XCTAssertEqual(ci.intervalWidth, 14)
    }

    func testConfidenceInterval_intervalWidth_narrowInterval() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 108, standardError: 5.0, upper: 112)
        XCTAssertEqual(ci.intervalWidth, 4)
    }

    func testConfidenceInterval_standardErrorFormatted() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 95, standardError: 4.5678, upper: 105)
        XCTAssertEqual(ci.standardErrorFormatted, "4.57")
    }

    func testConfidenceInterval_standardErrorFormatted_roundsCorrectly() {
        let ci: AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema = createConfidenceInterval(confidenceLevel: 0.95, lower: 95, standardError: 4.556, upper: 105)
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

    // MARK: - TestResultResponse Optional Property Tests

    func testTestResultResponse_percentileRankFormatted_1st() {
        let result = createTestResult(percentileRank: 1)
        XCTAssertEqual(result.percentileRankFormatted, "1st percentile")
    }

    func testTestResultResponse_percentileRankFormatted_2nd() {
        let result = createTestResult(percentileRank: 2)
        XCTAssertEqual(result.percentileRankFormatted, "2nd percentile")
    }

    func testTestResultResponse_percentileRankFormatted_3rd() {
        let result = createTestResult(percentileRank: 3)
        XCTAssertEqual(result.percentileRankFormatted, "3rd percentile")
    }

    func testTestResultResponse_percentileRankFormatted_4th() {
        let result = createTestResult(percentileRank: 4)
        XCTAssertEqual(result.percentileRankFormatted, "4th percentile")
    }

    func testTestResultResponse_percentileRankFormatted_11th() {
        let result = createTestResult(percentileRank: 11)
        XCTAssertEqual(result.percentileRankFormatted, "11th percentile")
    }

    func testTestResultResponse_percentileRankFormatted_12th() {
        let result = createTestResult(percentileRank: 12)
        XCTAssertEqual(result.percentileRankFormatted, "12th percentile")
    }

    func testTestResultResponse_percentileRankFormatted_13th() {
        let result = createTestResult(percentileRank: 13)
        XCTAssertEqual(result.percentileRankFormatted, "13th percentile")
    }

    func testTestResultResponse_percentileRankFormatted_21st() {
        let result = createTestResult(percentileRank: 21)
        XCTAssertEqual(result.percentileRankFormatted, "21st percentile")
    }

    func testTestResultResponse_percentileRankFormatted_85th() {
        let result = createTestResult(percentileRank: 85)
        XCTAssertEqual(result.percentileRankFormatted, "85th percentile")
    }

    func testTestResultResponse_percentileRankFormatted_roundsDecimal() {
        let result = createTestResult(percentileRank: 85.7)
        XCTAssertEqual(result.percentileRankFormatted, "86th percentile")
    }

    func testTestResultResponse_percentileRankFormatted_nil() {
        let result = createTestResult(percentileRank: nil)
        XCTAssertNil(result.percentileRankFormatted)
    }

    func testTestResultResponse_completionTimeFormatted_secondsOnly() {
        let result = createTestResult(completionTimeSeconds: 45)
        XCTAssertEqual(result.completionTimeFormatted, "0:45")
    }

    func testTestResultResponse_completionTimeFormatted_minutesOnly() {
        let result = createTestResult(completionTimeSeconds: 120)
        XCTAssertEqual(result.completionTimeFormatted, "2:00")
    }

    func testTestResultResponse_completionTimeFormatted_minutesAndSeconds() {
        let result = createTestResult(completionTimeSeconds: 330)
        XCTAssertEqual(result.completionTimeFormatted, "5:30")
    }

    func testTestResultResponse_completionTimeFormatted_nil() {
        let result = createTestResult(completionTimeSeconds: nil)
        XCTAssertNil(result.completionTimeFormatted)
    }

    func testTestResultResponse_strongestDomainDisplay_present() {
        let result = createTestResult(strongestDomain: "pattern")
        XCTAssertEqual(result.strongestDomainDisplay, "pattern")
    }

    func testTestResultResponse_strongestDomainDisplay_nil() {
        let result = createTestResult(strongestDomain: nil)
        XCTAssertNil(result.strongestDomainDisplay)
    }

    func testTestResultResponse_weakestDomainDisplay_present() {
        let result = createTestResult(weakestDomain: "math")
        XCTAssertEqual(result.weakestDomainDisplay, "math")
    }

    func testTestResultResponse_weakestDomainDisplay_nil() {
        let result = createTestResult(weakestDomain: nil)
        XCTAssertNil(result.weakestDomainDisplay)
    }

    // MARK: - UserResponse Optional Property Tests

    func testUserResponse_approximateAge_present() {
        let currentYear = Calendar.current.component(.year, from: Date())
        let user = createUser(birthYear: 1990)
        XCTAssertEqual(user.approximateAge, currentYear - 1990)
    }

    func testUserResponse_approximateAge_nil() {
        let user = createUser(birthYear: nil)
        XCTAssertNil(user.approximateAge)
    }

    func testUserResponse_locationDisplay_bothPresent() {
        let user = createUser(country: "United States", region: "California")
        XCTAssertEqual(user.locationDisplay, "California, United States")
    }

    func testUserResponse_locationDisplay_countryOnly() {
        let user = createUser(country: "Canada", region: nil)
        XCTAssertEqual(user.locationDisplay, "Canada")
    }

    func testUserResponse_locationDisplay_regionOnly() {
        let user = createUser(country: nil, region: "Ontario")
        XCTAssertEqual(user.locationDisplay, "Ontario")
    }

    func testUserResponse_locationDisplay_neitherPresent() {
        let user = createUser(country: nil, region: nil)
        XCTAssertNil(user.locationDisplay)
    }

    func testUserResponse_educationLevelDisplay_highSchool() {
        let user = createUser(educationLevel: .highSchool)
        XCTAssertEqual(user.educationLevelDisplay, "High School")
    }

    func testUserResponse_educationLevelDisplay_someCollege() {
        let user = createUser(educationLevel: .someCollege)
        XCTAssertEqual(user.educationLevelDisplay, "Some College")
    }

    func testUserResponse_educationLevelDisplay_associates() {
        let user = createUser(educationLevel: .associates)
        XCTAssertEqual(user.educationLevelDisplay, "Associate's Degree")
    }

    func testUserResponse_educationLevelDisplay_bachelors() {
        let user = createUser(educationLevel: .bachelors)
        XCTAssertEqual(user.educationLevelDisplay, "Bachelor's Degree")
    }

    func testUserResponse_educationLevelDisplay_masters() {
        let user = createUser(educationLevel: .masters)
        XCTAssertEqual(user.educationLevelDisplay, "Master's Degree")
    }

    func testUserResponse_educationLevelDisplay_doctorate() {
        let user = createUser(educationLevel: .doctorate)
        XCTAssertEqual(user.educationLevelDisplay, "Doctorate")
    }

    func testUserResponse_educationLevelDisplay_preferNotToSay() {
        let user = createUser(educationLevel: .preferNotToSay)
        XCTAssertEqual(user.educationLevelDisplay, "Prefer Not to Say")
    }

    func testUserResponse_educationLevelDisplay_nil() {
        let user = createUser(educationLevel: nil)
        XCTAssertNil(user.educationLevelDisplay)
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
        completedAt: Date = Date(),
        completionTimeSeconds: Int? = nil,
        percentileRank: Double? = nil,
        strongestDomain: String? = nil,
        weakestDomain: String? = nil
    ) -> Components.Schemas.TestResultResponse {
        Components.Schemas.TestResultResponse(
            accuracyPercentage: accuracyPercentage,
            completedAt: completedAt,
            completionTimeSeconds: completionTimeSeconds,
            correctAnswers: correctAnswers,
            id: id,
            iqScore: iqScore,
            percentileRank: percentileRank,
            strongestDomain: strongestDomain,
            testSessionId: testSessionId,
            totalQuestions: totalQuestions,
            userId: userId,
            weakestDomain: weakestDomain
        )
    }

    private func createConfidenceInterval(
        confidenceLevel: Double = 0.95,
        lower: Int = 95,
        standardError: Double = 5.0,
        upper: Int = 105
    ) -> AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema {
        AIQAPIClient.Components.Schemas.ConfidenceIntervalSchema(
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
        notificationEnabled: Bool = true,
        birthYear: Int? = nil,
        country: String? = nil,
        region: String? = nil,
        educationLevel: Components.Schemas.EducationLevelSchema? = nil
    ) -> Components.Schemas.UserResponse {
        var educationPayload: Components.Schemas.UserResponse.EducationLevelPayload?
        if let level = educationLevel {
            educationPayload = Components.Schemas.UserResponse.EducationLevelPayload(value1: level)
        }
        return Components.Schemas.UserResponse(
            birthYear: birthYear,
            country: country,
            createdAt: createdAt,
            educationLevel: educationPayload,
            email: email,
            firstName: firstName,
            id: id,
            lastName: lastName,
            notificationEnabled: notificationEnabled,
            region: region
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
