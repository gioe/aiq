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

    // MARK: - DomainScore Percentile Tests

    func testDomainScorePercentileFormatted() {
        // Test ordinal suffixes
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 1.0).percentileFormatted,
            "1st"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 2.0).percentileFormatted,
            "2nd"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 3.0).percentileFormatted,
            "3rd"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 4.0).percentileFormatted,
            "4th"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 11.0).percentileFormatted,
            "11th"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 12.0).percentileFormatted,
            "12th"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 13.0).percentileFormatted,
            "13th"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 21.0).percentileFormatted,
            "21st"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 22.0).percentileFormatted,
            "22nd"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 23.0).percentileFormatted,
            "23rd"
        )
        XCTAssertEqual(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 71.5).percentileFormatted,
            "72nd" // Rounds to nearest integer
        )

        // Test nil percentile
        XCTAssertNil(
            DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil).percentileFormatted
        )
    }

    func testDomainScorePercentileDescription() {
        let score = DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 71.0)
        XCTAssertEqual(score.percentileDescription, "71st percentile")

        let scoreNil = DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil)
        XCTAssertNil(scoreNil.percentileDescription)
    }

    // MARK: - PerformanceLevel Tests

    func testDomainScorePerformanceLevelExcellent() {
        // >= 90th percentile
        let score90 = DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 90.0)
        XCTAssertEqual(score90.performanceLevel, .excellent)

        let score95 = DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 95.0)
        XCTAssertEqual(score95.performanceLevel, .excellent)

        let score99 = DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 99.0)
        XCTAssertEqual(score99.performanceLevel, .excellent)
    }

    func testDomainScorePerformanceLevelGood() {
        // 75-90th percentile
        let score75 = DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 75.0)
        XCTAssertEqual(score75.performanceLevel, .good)

        let score85 = DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 85.0)
        XCTAssertEqual(score85.performanceLevel, .good)

        let score89 = DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 89.9)
        XCTAssertEqual(score89.performanceLevel, .good)
    }

    func testDomainScorePerformanceLevelAverage() {
        // 50-75th percentile
        let score50 = DomainScore(correct: 2, total: 4, pct: 50.0, percentile: 50.0)
        XCTAssertEqual(score50.performanceLevel, .average)

        let score60 = DomainScore(correct: 2, total: 4, pct: 50.0, percentile: 60.0)
        XCTAssertEqual(score60.performanceLevel, .average)

        let score74 = DomainScore(correct: 2, total: 4, pct: 50.0, percentile: 74.9)
        XCTAssertEqual(score74.performanceLevel, .average)
    }

    func testDomainScorePerformanceLevelBelowAverage() {
        // 25-50th percentile
        let score25 = DomainScore(correct: 1, total: 4, pct: 25.0, percentile: 25.0)
        XCTAssertEqual(score25.performanceLevel, .belowAverage)

        let score35 = DomainScore(correct: 1, total: 4, pct: 25.0, percentile: 35.0)
        XCTAssertEqual(score35.performanceLevel, .belowAverage)

        let score49 = DomainScore(correct: 1, total: 4, pct: 25.0, percentile: 49.9)
        XCTAssertEqual(score49.performanceLevel, .belowAverage)
    }

    func testDomainScorePerformanceLevelNeedsWork() {
        // < 25th percentile
        let score0 = DomainScore(correct: 0, total: 4, pct: 0.0, percentile: 0.0)
        XCTAssertEqual(score0.performanceLevel, .needsWork)

        let score10 = DomainScore(correct: 0, total: 4, pct: 0.0, percentile: 10.0)
        XCTAssertEqual(score10.performanceLevel, .needsWork)

        let score24 = DomainScore(correct: 0, total: 4, pct: 0.0, percentile: 24.9)
        XCTAssertEqual(score24.performanceLevel, .needsWork)
    }

    func testDomainScorePerformanceLevelNilWhenNoPercentile() {
        let score = DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil)
        XCTAssertNil(score.performanceLevel)
    }

    func testPerformanceLevelDisplayNames() {
        XCTAssertEqual(PerformanceLevel.excellent.displayName, "Excellent")
        XCTAssertEqual(PerformanceLevel.good.displayName, "Good")
        XCTAssertEqual(PerformanceLevel.average.displayName, "Average")
        XCTAssertEqual(PerformanceLevel.belowAverage.displayName, "Below Average")
        XCTAssertEqual(PerformanceLevel.needsWork.displayName, "Needs Work")
    }

    func testPerformanceLevelColors() {
        // Verify colors are assigned (not nil)
        XCTAssertNotNil(PerformanceLevel.excellent.color)
        XCTAssertNotNil(PerformanceLevel.good.color)
        XCTAssertNotNil(PerformanceLevel.average.color)
        XCTAssertNotNil(PerformanceLevel.belowAverage.color)
        XCTAssertNotNil(PerformanceLevel.needsWork.color)

        // Verify colors match ColorPalette
        XCTAssertEqual(PerformanceLevel.excellent.color, ColorPalette.performanceExcellent)
        XCTAssertEqual(PerformanceLevel.good.color, ColorPalette.performanceGood)
        XCTAssertEqual(PerformanceLevel.average.color, ColorPalette.performanceAverage)
        XCTAssertEqual(PerformanceLevel.belowAverage.color, ColorPalette.performanceBelowAverage)
        XCTAssertEqual(PerformanceLevel.needsWork.color, ColorPalette.performanceNeedsWork)
    }

    // MARK: - DomainScore Decoding with Percentile Tests

    func testDomainScoreDecodingWithPercentile() throws {
        let json = """
        {
            "correct": 3,
            "total": 4,
            "pct": 75.0,
            "percentile": 71.5
        }
        """

        let data = json.data(using: .utf8)!
        let domainScore = try JSONDecoder().decode(DomainScore.self, from: data)

        XCTAssertEqual(domainScore.correct, 3)
        XCTAssertEqual(domainScore.total, 4)
        XCTAssertEqual(domainScore.pct, 75.0)
        XCTAssertEqual(domainScore.percentile, 71.5)
    }

    func testDomainScoreDecodingWithNullPercentile() throws {
        let json = """
        {
            "correct": 3,
            "total": 4,
            "pct": 75.0,
            "percentile": null
        }
        """

        let data = json.data(using: .utf8)!
        let domainScore = try JSONDecoder().decode(DomainScore.self, from: data)

        XCTAssertEqual(domainScore.pct, 75.0)
        XCTAssertNil(domainScore.percentile)
    }

    func testDomainScoreDecodingWithoutPercentileField() throws {
        // Backward compatibility - percentile field may not be present
        let json = """
        {
            "correct": 3,
            "total": 4,
            "pct": 75.0
        }
        """

        let data = json.data(using: .utf8)!
        let domainScore = try JSONDecoder().decode(DomainScore.self, from: data)

        XCTAssertEqual(domainScore.pct, 75.0)
        XCTAssertNil(domainScore.percentile)
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
