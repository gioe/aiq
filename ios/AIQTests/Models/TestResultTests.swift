import XCTest

@testable import AIQ

final class TestResultTests: XCTestCase {
    // MARK: - DomainScore Tests

    func testDomainScoreDecoding() throws {
        let json = """
        {
            "correct": 3,
            "total": 4,
            "pct": 75.0
        }
        """

        let data = json.data(using: .utf8)!
        let domainScore = try JSONDecoder().decode(DomainScore.self, from: data)

        XCTAssertEqual(domainScore.correct, 3)
        XCTAssertEqual(domainScore.total, 4)
        XCTAssertEqual(domainScore.pct, 75.0)
    }

    func testDomainScoreDecodingWithNullPct() throws {
        let json = """
        {
            "correct": 0,
            "total": 0,
            "pct": null
        }
        """

        let data = json.data(using: .utf8)!
        let domainScore = try JSONDecoder().decode(DomainScore.self, from: data)

        XCTAssertEqual(domainScore.correct, 0)
        XCTAssertEqual(domainScore.total, 0)
        XCTAssertNil(domainScore.pct)
    }

    func testDomainScorePercentageFormatted() {
        let scoreWithPct = DomainScore(correct: 3, total: 4, pct: 75.5, percentile: nil)
        XCTAssertEqual(scoreWithPct.percentageFormatted, "76%")

        let scoreWithNullPct = DomainScore(correct: 0, total: 0, pct: nil, percentile: nil)
        XCTAssertEqual(scoreWithNullPct.percentageFormatted, "N/A")
    }

    func testDomainScoreAccuracy() {
        let scoreWithPct = DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil)
        XCTAssertEqual(scoreWithPct.accuracy, 0.75)

        let scoreWithNullPct = DomainScore(correct: 0, total: 0, pct: nil, percentile: nil)
        XCTAssertNil(scoreWithNullPct.accuracy)
    }

    // MARK: - TestResult Domain Scores Decoding Tests

    func testTestResultDecodingWithDomainScores() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 100,
            "iq_score": 115,
            "percentile_rank": 84.0,
            "total_questions": 20,
            "correct_answers": 14,
            "accuracy_percentage": 70.0,
            "completion_time_seconds": 1200,
            "completed_at": "2025-12-13T10:00:00Z",
            "domain_scores": {
                "pattern": {"correct": 3, "total": 4, "pct": 75.0},
                "logic": {"correct": 2, "total": 3, "pct": 66.67},
                "spatial": {"correct": 2, "total": 3, "pct": 66.67},
                "math": {"correct": 3, "total": 4, "pct": 75.0},
                "verbal": {"correct": 3, "total": 3, "pct": 100.0},
                "memory": {"correct": 1, "total": 3, "pct": 33.33}
            }
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let result = try decoder.decode(TestResult.self, from: data)

        XCTAssertEqual(result.id, 1)
        XCTAssertEqual(result.iqScore, 115)
        XCTAssertNotNil(result.domainScores)
        XCTAssertEqual(result.domainScores?.count, 6)

        // Verify individual domain scores
        XCTAssertEqual(result.domainScores?["pattern"]?.correct, 3)
        XCTAssertEqual(result.domainScores?["pattern"]?.total, 4)
        XCTAssertEqual(result.domainScores?["pattern"]?.pct, 75.0)

        XCTAssertEqual(result.domainScores?["verbal"]?.pct, 100.0)
        XCTAssertEqual(result.domainScores?["memory"]?.pct, 33.33)
    }

    func testTestResultDecodingWithNullDomainScores() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 100,
            "iq_score": 115,
            "percentile_rank": null,
            "total_questions": 20,
            "correct_answers": 14,
            "accuracy_percentage": 70.0,
            "completion_time_seconds": null,
            "completed_at": "2025-12-13T10:00:00Z",
            "domain_scores": null
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let result = try decoder.decode(TestResult.self, from: data)

        XCTAssertNil(result.domainScores)
        XCTAssertNil(result.percentileRank)
        XCTAssertNil(result.completionTimeSeconds)
    }

    func testTestResultDecodingWithoutDomainScoresField() throws {
        // Test backward compatibility when domain_scores field is not present
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 100,
            "iq_score": 115,
            "total_questions": 20,
            "correct_answers": 14,
            "accuracy_percentage": 70.0,
            "completed_at": "2025-12-13T10:00:00Z"
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let result = try decoder.decode(TestResult.self, from: data)

        XCTAssertNil(result.domainScores)
    }

    // MARK: - CognitiveDomain Tests

    func testCognitiveDomainDisplayNames() {
        XCTAssertEqual(TestResult.CognitiveDomain.pattern.displayName, "Pattern Recognition")
        XCTAssertEqual(TestResult.CognitiveDomain.logic.displayName, "Logical Reasoning")
        XCTAssertEqual(TestResult.CognitiveDomain.spatial.displayName, "Spatial Reasoning")
        XCTAssertEqual(TestResult.CognitiveDomain.math.displayName, "Mathematical")
        XCTAssertEqual(TestResult.CognitiveDomain.verbal.displayName, "Verbal Reasoning")
        XCTAssertEqual(TestResult.CognitiveDomain.memory.displayName, "Memory")
    }

    func testCognitiveDomainRawValues() {
        XCTAssertEqual(TestResult.CognitiveDomain.pattern.rawValue, "pattern")
        XCTAssertEqual(TestResult.CognitiveDomain.logic.rawValue, "logic")
        XCTAssertEqual(TestResult.CognitiveDomain.spatial.rawValue, "spatial")
        XCTAssertEqual(TestResult.CognitiveDomain.math.rawValue, "math")
        XCTAssertEqual(TestResult.CognitiveDomain.verbal.rawValue, "verbal")
        XCTAssertEqual(TestResult.CognitiveDomain.memory.rawValue, "memory")
    }

    // MARK: - Domain Score Helper Tests

    func testSortedDomainScores() {
        let result = createTestResultWithDomainScores()

        let sorted = result.sortedDomainScores
        XCTAssertNotNil(sorted)
        XCTAssertEqual(sorted?.count, 6)

        // Verify order matches CognitiveDomain.allCases
        XCTAssertEqual(sorted?[0].domain, .pattern)
        XCTAssertEqual(sorted?[1].domain, .logic)
        XCTAssertEqual(sorted?[2].domain, .spatial)
        XCTAssertEqual(sorted?[3].domain, .math)
        XCTAssertEqual(sorted?[4].domain, .verbal)
        XCTAssertEqual(sorted?[5].domain, .memory)
    }

    func testSortedDomainScoresReturnsNilWhenNoDomainScores() {
        let result = createTestResultWithoutDomainScores()

        XCTAssertNil(result.sortedDomainScores)
    }

    func testStrongestDomain() {
        let result = createTestResultWithDomainScores()

        let strongest = result.strongestDomain
        XCTAssertNotNil(strongest)
        XCTAssertEqual(strongest?.domain, .verbal) // 100%
        XCTAssertEqual(strongest?.score.pct, 100.0)
    }

    func testWeakestDomain() {
        let result = createTestResultWithDomainScores()

        let weakest = result.weakestDomain
        XCTAssertNotNil(weakest)
        XCTAssertEqual(weakest?.domain, .memory) // 33.33%
        XCTAssertEqual(weakest?.score.pct, 33.33)
    }

    func testStrongestDomainReturnsNilWhenNoDomainScores() {
        let result = createTestResultWithoutDomainScores()

        XCTAssertNil(result.strongestDomain)
    }

    func testWeakestDomainReturnsNilWhenNoDomainScores() {
        let result = createTestResultWithoutDomainScores()

        XCTAssertNil(result.weakestDomain)
    }

    func testStrongestWeakestExcludesDomainsWithZeroQuestions() {
        let domainScores: [String: DomainScore] = [
            "pattern": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil),
            "logic": DomainScore(correct: 0, total: 0, pct: nil, percentile: nil), // No questions
            "spatial": DomainScore(correct: 2, total: 4, pct: 50.0, percentile: nil),
            "math": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: nil),
            "verbal": DomainScore(correct: 1, total: 4, pct: 25.0, percentile: nil),
            "memory": DomainScore(correct: 0, total: 0, pct: nil, percentile: nil) // No questions
        ]

        let result = TestResult(
            id: 1,
            testSessionId: 10,
            userId: 100,
            iqScore: 115,
            percentileRank: 84.0,
            totalQuestions: 16,
            correctAnswers: 10,
            accuracyPercentage: 62.5,
            completionTimeSeconds: 1200,
            completedAt: Date(),
            domainScores: domainScores
        )

        let strongest = result.strongestDomain
        XCTAssertEqual(strongest?.domain, .math) // 100%

        let weakest = result.weakestDomain
        XCTAssertEqual(weakest?.domain, .verbal) // 25%
    }

    // MARK: - Helper Methods

    private func createTestResultWithDomainScores() -> TestResult {
        let domainScores: [String: DomainScore] = [
            "pattern": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil),
            "logic": DomainScore(correct: 2, total: 3, pct: 66.67, percentile: nil),
            "spatial": DomainScore(correct: 2, total: 3, pct: 66.67, percentile: nil),
            "math": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil),
            "verbal": DomainScore(correct: 3, total: 3, pct: 100.0, percentile: nil),
            "memory": DomainScore(correct: 1, total: 3, pct: 33.33, percentile: nil)
        ]

        return TestResult(
            id: 1,
            testSessionId: 10,
            userId: 100,
            iqScore: 115,
            percentileRank: 84.0,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completionTimeSeconds: 1200,
            completedAt: Date(),
            domainScores: domainScores
        )
    }

    private func createTestResultWithoutDomainScores() -> TestResult {
        TestResult(
            id: 1,
            testSessionId: 10,
            userId: 100,
            iqScore: 115,
            percentileRank: 84.0,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completionTimeSeconds: 1200,
            completedAt: Date(),
            domainScores: nil
        )
    }
}
