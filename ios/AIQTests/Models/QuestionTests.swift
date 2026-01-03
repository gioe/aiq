import XCTest

@testable import AIQ

final class QuestionTests: XCTestCase {
    // MARK: - QuestionType Tests

    func testQuestionTypeRawValues() {
        XCTAssertEqual(QuestionType.pattern.rawValue, "pattern")
        XCTAssertEqual(QuestionType.logic.rawValue, "logic")
        XCTAssertEqual(QuestionType.spatial.rawValue, "spatial")
        XCTAssertEqual(QuestionType.math.rawValue, "math")
        XCTAssertEqual(QuestionType.verbal.rawValue, "verbal")
        XCTAssertEqual(QuestionType.memory.rawValue, "memory")
    }

    func testQuestionTypeDecoding() throws {
        let json = """
        "logic"
        """

        let data = json.data(using: .utf8)!
        let questionType = try JSONDecoder().decode(QuestionType.self, from: data)

        XCTAssertEqual(questionType, .logic)
    }

    func testQuestionTypeDecodingAllCases() throws {
        let testCases: [(String, QuestionType)] = [
            ("pattern", .pattern),
            ("logic", .logic),
            ("spatial", .spatial),
            ("math", .math),
            ("verbal", .verbal),
            ("memory", .memory)
        ]

        for (rawValue, expectedType) in testCases {
            let json = "\"\(rawValue)\""
            let data = json.data(using: .utf8)!
            let questionType = try JSONDecoder().decode(QuestionType.self, from: data)

            XCTAssertEqual(
                questionType,
                expectedType,
                "Failed to decode question type: \(rawValue)"
            )
        }
    }

    func testQuestionTypeEquality() {
        XCTAssertEqual(QuestionType.pattern, QuestionType.pattern)
        XCTAssertEqual(QuestionType.logic, QuestionType.logic)
        XCTAssertNotEqual(QuestionType.pattern, QuestionType.logic)
    }

    // MARK: - DifficultyLevel Tests

    func testDifficultyLevelRawValues() {
        XCTAssertEqual(DifficultyLevel.easy.rawValue, "easy")
        XCTAssertEqual(DifficultyLevel.medium.rawValue, "medium")
        XCTAssertEqual(DifficultyLevel.hard.rawValue, "hard")
    }

    func testDifficultyLevelDecoding() throws {
        let json = """
        "medium"
        """

        let data = json.data(using: .utf8)!
        let difficultyLevel = try JSONDecoder().decode(DifficultyLevel.self, from: data)

        XCTAssertEqual(difficultyLevel, .medium)
    }

    func testDifficultyLevelDecodingAllCases() throws {
        let testCases: [(String, DifficultyLevel)] = [
            ("easy", .easy),
            ("medium", .medium),
            ("hard", .hard)
        ]

        for (rawValue, expectedLevel) in testCases {
            let json = "\"\(rawValue)\""
            let data = json.data(using: .utf8)!
            let difficultyLevel = try JSONDecoder().decode(DifficultyLevel.self, from: data)

            XCTAssertEqual(
                difficultyLevel,
                expectedLevel,
                "Failed to decode difficulty level: \(rawValue)"
            )
        }
    }

    func testDifficultyLevelEquality() {
        XCTAssertEqual(DifficultyLevel.easy, DifficultyLevel.easy)
        XCTAssertEqual(DifficultyLevel.medium, DifficultyLevel.medium)
        XCTAssertNotEqual(DifficultyLevel.easy, DifficultyLevel.hard)
    }

    // MARK: - Question Decoding Tests

    func testQuestionDecodingWithAllFields() throws {
        let json = """
        {
            "id": 1,
            "question_text": "What is the next number in the sequence: 2, 4, 8, 16, ?",
            "question_type": "pattern",
            "difficulty_level": "medium",
            "answer_options": ["24", "32", "64", "128"],
            "explanation": "Each number is double the previous number."
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertEqual(question.id, 1)
        XCTAssertEqual(question.questionText, "What is the next number in the sequence: 2, 4, 8, 16, ?")
        XCTAssertEqual(question.questionType, .pattern)
        XCTAssertEqual(question.difficultyLevel, .medium)
        XCTAssertEqual(question.answerOptions, ["24", "32", "64", "128"])
        XCTAssertEqual(question.explanation, "Each number is double the previous number.")
    }

    func testQuestionDecodingWithRequiredFieldsOnly() throws {
        let json = """
        {
            "id": 2,
            "question_text": "Solve for x: 2x + 5 = 15",
            "question_type": "math",
            "difficulty_level": "easy"
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertEqual(question.id, 2)
        XCTAssertEqual(question.questionText, "Solve for x: 2x + 5 = 15")
        XCTAssertEqual(question.questionType, .math)
        XCTAssertEqual(question.difficultyLevel, .easy)
        XCTAssertNil(question.answerOptions)
        XCTAssertNil(question.explanation)
    }

    func testQuestionDecodingWithNullOptionalFields() throws {
        let json = """
        {
            "id": 3,
            "question_text": "What is the capital of France?",
            "question_type": "verbal",
            "difficulty_level": "easy",
            "answer_options": null,
            "explanation": null
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertEqual(question.id, 3)
        XCTAssertNil(question.answerOptions)
        XCTAssertNil(question.explanation)
    }

    func testQuestionDecodingCodingKeysMapping() throws {
        let json = """
        {
            "id": 4,
            "question_text": "Test question",
            "question_type": "logic",
            "difficulty_level": "hard",
            "answer_options": ["A", "B", "C"],
            "explanation": "Test explanation"
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        // Verify snake_case fields are properly mapped to camelCase
        XCTAssertEqual(question.questionText, "Test question")
        XCTAssertEqual(question.questionType, .logic)
        XCTAssertEqual(question.difficultyLevel, .hard)
        XCTAssertEqual(question.answerOptions, ["A", "B", "C"])
        XCTAssertEqual(question.explanation, "Test explanation")
    }

    func testQuestionDecodingWithAllQuestionTypes() throws {
        let questionTypes: [(String, QuestionType)] = [
            ("pattern", .pattern),
            ("logic", .logic),
            ("spatial", .spatial),
            ("math", .math),
            ("verbal", .verbal),
            ("memory", .memory)
        ]

        for (rawValue, expectedType) in questionTypes {
            let json = """
            {
                "id": 1,
                "question_text": "Test question",
                "question_type": "\(rawValue)",
                "difficulty_level": "medium"
            }
            """

            let data = json.data(using: .utf8)!
            let question = try JSONDecoder().decode(Question.self, from: data)

            XCTAssertEqual(
                question.questionType,
                expectedType,
                "Failed to decode question type: \(rawValue)"
            )
        }
    }

    func testQuestionDecodingWithAllDifficultyLevels() throws {
        let difficultyLevels: [(String, DifficultyLevel)] = [
            ("easy", .easy),
            ("medium", .medium),
            ("hard", .hard)
        ]

        for (rawValue, expectedLevel) in difficultyLevels {
            let json = """
            {
                "id": 1,
                "question_text": "Test question",
                "question_type": "pattern",
                "difficulty_level": "\(rawValue)"
            }
            """

            let data = json.data(using: .utf8)!
            let question = try JSONDecoder().decode(Question.self, from: data)

            XCTAssertEqual(
                question.difficultyLevel,
                expectedLevel,
                "Failed to decode difficulty level: \(rawValue)"
            )
        }
    }

    // MARK: - Question Computed Properties Tests

    func testIsMultipleChoiceWithOptions() {
        let question = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: ["A", "B", "C", "D"],
            explanation: nil
        )

        XCTAssertTrue(question.isMultipleChoice)
    }

    func testIsMultipleChoiceWithoutOptions() {
        let question = Question(
            id: 1,
            questionText: "Test question",
            questionType: .math,
            difficultyLevel: .easy,
            answerOptions: nil,
            explanation: nil
        )

        XCTAssertFalse(question.isMultipleChoice)
    }

    func testIsMultipleChoiceWithEmptyOptions() {
        let question = Question(
            id: 1,
            questionText: "Test question",
            questionType: .logic,
            difficultyLevel: .hard,
            answerOptions: [],
            explanation: nil
        )

        XCTAssertFalse(question.isMultipleChoice)
    }

    func testHasOptionsWithOptions() {
        let question = Question(
            id: 1,
            questionText: "Test question",
            questionType: .verbal,
            difficultyLevel: .easy,
            answerOptions: ["Option 1", "Option 2"],
            explanation: nil
        )

        XCTAssertTrue(question.hasOptions)
    }

    func testHasOptionsWithoutOptions() {
        let question = Question(
            id: 1,
            questionText: "Test question",
            questionType: .spatial,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        )

        XCTAssertFalse(question.hasOptions)
    }

    func testHasOptionsWithEmptyOptions() {
        let question = Question(
            id: 1,
            questionText: "Test question",
            questionType: .memory,
            difficultyLevel: .hard,
            answerOptions: [],
            explanation: nil
        )

        XCTAssertFalse(question.hasOptions)
    }

    // MARK: - Question Equatable Tests

    func testQuestionEquality() {
        let question1 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: ["A", "B", "C"],
            explanation: "Test explanation"
        )

        let question2 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: ["A", "B", "C"],
            explanation: "Test explanation"
        )

        XCTAssertEqual(question1, question2)
    }

    func testQuestionInequalityDifferentId() {
        let question1 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        )

        let question2 = Question(
            id: 2,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        )

        XCTAssertNotEqual(question1, question2)
    }

    func testQuestionInequalityDifferentQuestionText() {
        let question1 = Question(
            id: 1,
            questionText: "Question 1",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        )

        let question2 = Question(
            id: 1,
            questionText: "Question 2",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        )

        XCTAssertNotEqual(question1, question2)
    }

    func testQuestionInequalityDifferentQuestionType() {
        let question1 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        )

        let question2 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .logic,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: nil
        )

        XCTAssertNotEqual(question1, question2)
    }

    func testQuestionInequalityDifferentDifficultyLevel() {
        let question1 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .easy,
            answerOptions: nil,
            explanation: nil
        )

        let question2 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .hard,
            answerOptions: nil,
            explanation: nil
        )

        XCTAssertNotEqual(question1, question2)
    }

    func testQuestionInequalityDifferentAnswerOptions() {
        let question1 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: ["A", "B"],
            explanation: nil
        )

        let question2 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: ["C", "D"],
            explanation: nil
        )

        XCTAssertNotEqual(question1, question2)
    }

    func testQuestionInequalityDifferentExplanation() {
        let question1 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: "Explanation 1"
        )

        let question2 = Question(
            id: 1,
            questionText: "Test question",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: nil,
            explanation: "Explanation 2"
        )

        XCTAssertNotEqual(question1, question2)
    }

    // MARK: - Question Encoding Tests

    func testQuestionEncodingRoundTrip() throws {
        let question = Question(
            id: 123,
            questionText: "What is 2 + 2?",
            questionType: .math,
            difficultyLevel: .easy,
            answerOptions: ["3", "4", "5", "6"],
            explanation: "Basic addition"
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(question)

        let decoder = JSONDecoder()
        let decodedQuestion = try decoder.decode(Question.self, from: data)

        XCTAssertEqual(question.id, decodedQuestion.id)
        XCTAssertEqual(question.questionText, decodedQuestion.questionText)
        XCTAssertEqual(question.questionType, decodedQuestion.questionType)
        XCTAssertEqual(question.difficultyLevel, decodedQuestion.difficultyLevel)
        XCTAssertEqual(question.answerOptions, decodedQuestion.answerOptions)
        XCTAssertEqual(question.explanation, decodedQuestion.explanation)
    }

    func testQuestionEncodingUsesSnakeCase() throws {
        let question = Question(
            id: 1,
            questionText: "Test",
            questionType: .pattern,
            difficultyLevel: .medium,
            answerOptions: ["A"],
            explanation: "Explanation"
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(question)
        let jsonString = String(data: data, encoding: .utf8)!

        // Verify snake_case keys are used in JSON
        XCTAssertTrue(jsonString.contains("question_text"))
        XCTAssertTrue(jsonString.contains("question_type"))
        XCTAssertTrue(jsonString.contains("difficulty_level"))
        XCTAssertTrue(jsonString.contains("answer_options"))

        // Verify camelCase keys are NOT in JSON
        XCTAssertFalse(jsonString.contains("questionText"))
        XCTAssertFalse(jsonString.contains("questionType"))
        XCTAssertFalse(jsonString.contains("difficultyLevel"))
        XCTAssertFalse(jsonString.contains("answerOptions"))
    }

    // MARK: - Question Identifiable Tests

    func testQuestionIdentifiable() {
        let question = Question(
            id: 42,
            questionText: "Test question",
            questionType: .logic,
            difficultyLevel: .hard,
            answerOptions: nil,
            explanation: nil
        )

        XCTAssertEqual(question.id, 42)
    }

    // MARK: - QuestionResponse Tests

    func testQuestionResponseInitialization() {
        let response = QuestionResponse(
            questionId: 1,
            userAnswer: "42",
            timeSpentSeconds: 30
        )

        XCTAssertEqual(response.questionId, 1)
        XCTAssertEqual(response.userAnswer, "42")
        XCTAssertEqual(response.timeSpentSeconds, 30)
    }

    func testQuestionResponseInitializationWithoutTimeSpent() {
        let response = QuestionResponse(
            questionId: 2,
            userAnswer: "Answer"
        )

        XCTAssertEqual(response.questionId, 2)
        XCTAssertEqual(response.userAnswer, "Answer")
        XCTAssertNil(response.timeSpentSeconds)
    }

    func testQuestionResponseDecoding() throws {
        let json = """
        {
            "question_id": 5,
            "user_answer": "Paris",
            "time_spent_seconds": 45
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(QuestionResponse.self, from: data)

        XCTAssertEqual(response.questionId, 5)
        XCTAssertEqual(response.userAnswer, "Paris")
        XCTAssertEqual(response.timeSpentSeconds, 45)
    }

    func testQuestionResponseDecodingWithoutTimeSpent() throws {
        let json = """
        {
            "question_id": 6,
            "user_answer": "Blue"
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(QuestionResponse.self, from: data)

        XCTAssertEqual(response.questionId, 6)
        XCTAssertEqual(response.userAnswer, "Blue")
        XCTAssertNil(response.timeSpentSeconds)
    }

    func testQuestionResponseDecodingWithNullTimeSpent() throws {
        let json = """
        {
            "question_id": 7,
            "user_answer": "Test answer",
            "time_spent_seconds": null
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(QuestionResponse.self, from: data)

        XCTAssertEqual(response.questionId, 7)
        XCTAssertEqual(response.userAnswer, "Test answer")
        XCTAssertNil(response.timeSpentSeconds)
    }

    func testQuestionResponseCodingKeysMapping() throws {
        let json = """
        {
            "question_id": 10,
            "user_answer": "Sample answer",
            "time_spent_seconds": 120
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(QuestionResponse.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(response.questionId, 10)
        XCTAssertEqual(response.userAnswer, "Sample answer")
        XCTAssertEqual(response.timeSpentSeconds, 120)
    }

    func testQuestionResponseEncodingRoundTrip() throws {
        let response = QuestionResponse(
            questionId: 15,
            userAnswer: "Round trip test",
            timeSpentSeconds: 60
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(response)

        let decoder = JSONDecoder()
        let decodedResponse = try decoder.decode(QuestionResponse.self, from: data)

        XCTAssertEqual(response.questionId, decodedResponse.questionId)
        XCTAssertEqual(response.userAnswer, decodedResponse.userAnswer)
        XCTAssertEqual(response.timeSpentSeconds, decodedResponse.timeSpentSeconds)
    }

    func testQuestionResponseEncodingUsesSnakeCase() throws {
        let response = QuestionResponse(
            questionId: 20,
            userAnswer: "Test",
            timeSpentSeconds: 90
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(response)
        let jsonString = String(data: data, encoding: .utf8)!

        // Verify snake_case keys are used in JSON
        XCTAssertTrue(jsonString.contains("question_id"))
        XCTAssertTrue(jsonString.contains("user_answer"))
        XCTAssertTrue(jsonString.contains("time_spent_seconds"))

        // Verify camelCase keys are NOT in JSON
        XCTAssertFalse(jsonString.contains("questionId"))
        XCTAssertFalse(jsonString.contains("userAnswer"))
        XCTAssertFalse(jsonString.contains("timeSpentSeconds"))
    }

    func testQuestionResponseEquality() {
        let response1 = QuestionResponse(
            questionId: 1,
            userAnswer: "Answer",
            timeSpentSeconds: 30
        )

        let response2 = QuestionResponse(
            questionId: 1,
            userAnswer: "Answer",
            timeSpentSeconds: 30
        )

        XCTAssertEqual(response1, response2)
    }

    func testQuestionResponseInequality() {
        let response1 = QuestionResponse(
            questionId: 1,
            userAnswer: "Answer",
            timeSpentSeconds: 30
        )

        // Different question ID
        let response2 = QuestionResponse(
            questionId: 2,
            userAnswer: "Answer",
            timeSpentSeconds: 30
        )
        XCTAssertNotEqual(response1, response2)

        // Different user answer
        let response3 = QuestionResponse(
            questionId: 1,
            userAnswer: "Different",
            timeSpentSeconds: 30
        )
        XCTAssertNotEqual(response1, response3)

        // Different time spent
        let response4 = QuestionResponse(
            questionId: 1,
            userAnswer: "Answer",
            timeSpentSeconds: 60
        )
        XCTAssertNotEqual(response1, response4)
    }

    // MARK: - Edge Cases and Validation Tests

    func testQuestionDecodingWithEmptyStrings() throws {
        let json = """
        {
            "id": 1,
            "question_text": "",
            "question_type": "pattern",
            "difficulty_level": "easy",
            "explanation": ""
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertEqual(question.questionText, "")
        XCTAssertEqual(question.explanation, "")
    }

    func testQuestionDecodingWithSpecialCharacters() throws {
        let json = """
        {
            "id": 1,
            "question_text": "What is the value of π (pi)? Choose the closest approximation.",
            "question_type": "math",
            "difficulty_level": "medium",
            "answer_options": ["3.14159", "2.71828", "1.61803"],
            "explanation": "π is approximately 3.14159... It's an irrational number."
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertTrue(question.questionText.contains("π"))
        XCTAssertTrue(question.explanation?.contains("π") ?? false)
    }

    func testQuestionDecodingWithUnicodeCharacters() throws {
        let json = """
        {
            "id": 1,
            "question_text": "Quelle est la capitale de la France? 你好",
            "question_type": "verbal",
            "difficulty_level": "easy",
            "answer_options": ["París", "London", "Berlin"],
            "explanation": "La réponse est París"
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertTrue(question.questionText.contains("你好"))
        XCTAssertEqual(question.answerOptions?[0], "París")
    }

    func testQuestionDecodingWithLongText() throws {
        let longText = String(repeating: "A", count: 1000)
        let json = """
        {
            "id": 1,
            "question_text": "\(longText)",
            "question_type": "verbal",
            "difficulty_level": "hard"
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertEqual(question.questionText.count, 1000)
    }

    func testQuestionDecodingWithManyAnswerOptions() throws {
        let options = (1 ... 10).map { "Option \($0)" }
        let optionsJSON = options.map { "\"\($0)\"" }.joined(separator: ", ")

        let json = """
        {
            "id": 1,
            "question_text": "Test question",
            "question_type": "logic",
            "difficulty_level": "hard",
            "answer_options": [\(optionsJSON)]
        }
        """

        let data = json.data(using: .utf8)!
        let question = try JSONDecoder().decode(Question.self, from: data)

        XCTAssertEqual(question.answerOptions?.count, 10)
        XCTAssertEqual(question.answerOptions?[0], "Option 1")
        XCTAssertEqual(question.answerOptions?[9], "Option 10")
    }

    func testQuestionDecodingFailsWithMissingId() {
        let json = """
        {
            "question_text": "Test question",
            "question_type": "pattern",
            "difficulty_level": "medium"
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(Question.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing id")
        }
    }

    func testQuestionDecodingFailsWithMissingQuestionText() {
        let json = """
        {
            "id": 1,
            "question_type": "pattern",
            "difficulty_level": "medium"
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(Question.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing question_text")
        }
    }

    func testQuestionDecodingFailsWithMissingQuestionType() {
        let json = """
        {
            "id": 1,
            "question_text": "Test question",
            "difficulty_level": "medium"
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(Question.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing question_type")
        }
    }

    func testQuestionDecodingFailsWithMissingDifficultyLevel() {
        let json = """
        {
            "id": 1,
            "question_text": "Test question",
            "question_type": "pattern"
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(Question.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing difficulty_level")
        }
    }

    func testQuestionDecodingFailsWithInvalidQuestionType() {
        let json = """
        {
            "id": 1,
            "question_text": "Test question",
            "question_type": "invalid_type",
            "difficulty_level": "medium"
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(Question.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for invalid question type")
        }
    }

    func testQuestionDecodingFailsWithInvalidDifficultyLevel() {
        let json = """
        {
            "id": 1,
            "question_text": "Test question",
            "question_type": "pattern",
            "difficulty_level": "impossible"
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(Question.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for invalid difficulty level")
        }
    }

    func testQuestionResponseDecodingFailsWithMissingQuestionId() {
        let json = """
        {
            "user_answer": "Answer"
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(QuestionResponse.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing question_id")
        }
    }

    func testQuestionResponseDecodingFailsWithMissingUserAnswer() {
        let json = """
        {
            "question_id": 1
        }
        """

        let data = json.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(QuestionResponse.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing user_answer")
        }
    }

    func testQuestionResponseWithEmptyUserAnswer() throws {
        let response = QuestionResponse(
            questionId: 1,
            userAnswer: "",
            timeSpentSeconds: 10
        )

        XCTAssertEqual(response.userAnswer, "")
    }

    func testQuestionResponseWithZeroTimeSpent() throws {
        let response = QuestionResponse(
            questionId: 1,
            userAnswer: "Quick answer",
            timeSpentSeconds: 0
        )

        XCTAssertEqual(response.timeSpentSeconds, 0)
    }

    func testQuestionResponseWithNegativeTimeSpent() throws {
        // While not ideal, the model should handle negative values
        let response = QuestionResponse(
            questionId: 1,
            userAnswer: "Answer",
            timeSpentSeconds: -5
        )

        XCTAssertEqual(response.timeSpentSeconds, -5)
    }

    func testQuestionResponseWithLargeTimeSpent() throws {
        let response = QuestionResponse(
            questionId: 1,
            userAnswer: "Answer",
            timeSpentSeconds: 3600 // 1 hour
        )

        XCTAssertEqual(response.timeSpentSeconds, 3600)
    }
}
