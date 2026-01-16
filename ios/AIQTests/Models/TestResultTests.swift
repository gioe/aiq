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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

        let data = try XCTUnwrap(json.data(using: .utf8))
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

    // MARK: - ConfidenceInterval Decoding Tests

    func testConfidenceIntervalDecoding() throws {
        let json = """
        {
            "lower": 101,
            "upper": 115,
            "confidence_level": 0.95,
            "standard_error": 3.5
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let ci = try JSONDecoder().decode(ConfidenceInterval.self, from: data)

        XCTAssertEqual(ci.lower, 101)
        XCTAssertEqual(ci.upper, 115)
        XCTAssertEqual(ci.confidenceLevel, 0.95)
        XCTAssertEqual(ci.standardError, 3.5)
    }

    func testConfidenceIntervalRangeFormatted() {
        let ci = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        XCTAssertEqual(ci.rangeFormatted, "101-115")
    }

    func testConfidenceIntervalConfidencePercentage() {
        let ci95 = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        XCTAssertEqual(ci95.confidencePercentage, 95)

        let ci90 = ConfidenceInterval(lower: 102, upper: 114, confidenceLevel: 0.90, standardError: 3.5)
        XCTAssertEqual(ci90.confidencePercentage, 90)

        let ci99 = ConfidenceInterval(lower: 99, upper: 117, confidenceLevel: 0.99, standardError: 3.5)
        XCTAssertEqual(ci99.confidencePercentage, 99)
    }

    func testConfidenceIntervalFullDescription() {
        let ci = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        XCTAssertEqual(ci.fullDescription, "95% confidence interval: 101-115")
    }

    func testConfidenceIntervalAccessibilityDescription() {
        let ci = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        XCTAssertEqual(ci.accessibilityDescription, "Score range from 101 to 115 with 95 percent confidence")
    }

    func testConfidenceIntervalEquality() {
        let ci1 = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        let ci2 = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        let ci3 = ConfidenceInterval(lower: 100, upper: 116, confidenceLevel: 0.95, standardError: 3.5)

        XCTAssertEqual(ci1, ci2)
        XCTAssertNotEqual(ci1, ci3)
    }

    // MARK: - TestResult with ConfidenceInterval Tests

    func testTestResultDecodingWithConfidenceInterval() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 100,
            "iq_score": 108,
            "percentile_rank": 70.2,
            "total_questions": 20,
            "correct_answers": 14,
            "accuracy_percentage": 70.0,
            "completion_time_seconds": 1200,
            "completed_at": "2025-12-13T10:00:00Z",
            "domain_scores": null,
            "confidence_interval": {
                "lower": 101,
                "upper": 115,
                "confidence_level": 0.95,
                "standard_error": 3.5
            }
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let result = try decoder.decode(TestResult.self, from: data)

        XCTAssertEqual(result.id, 1)
        XCTAssertEqual(result.iqScore, 108)
        XCTAssertNotNil(result.confidenceInterval)
        XCTAssertEqual(result.confidenceInterval?.lower, 101)
        XCTAssertEqual(result.confidenceInterval?.upper, 115)
        XCTAssertEqual(result.confidenceInterval?.confidenceLevel, 0.95)
        XCTAssertEqual(result.confidenceInterval?.standardError, 3.5)
    }

    func testTestResultDecodingWithNullConfidenceInterval() throws {
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 100,
            "iq_score": 108,
            "percentile_rank": 70.2,
            "total_questions": 20,
            "correct_answers": 14,
            "accuracy_percentage": 70.0,
            "completion_time_seconds": 1200,
            "completed_at": "2025-12-13T10:00:00Z",
            "confidence_interval": null
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let result = try decoder.decode(TestResult.self, from: data)

        XCTAssertEqual(result.iqScore, 108)
        XCTAssertNil(result.confidenceInterval)
    }

    func testTestResultDecodingWithoutConfidenceIntervalField() throws {
        // Backward compatibility - confidence_interval field may not be present
        let json = """
        {
            "id": 1,
            "test_session_id": 10,
            "user_id": 100,
            "iq_score": 108,
            "percentile_rank": 70.2,
            "total_questions": 20,
            "correct_answers": 14,
            "accuracy_percentage": 70.0,
            "completed_at": "2025-12-13T10:00:00Z"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let result = try decoder.decode(TestResult.self, from: data)

        XCTAssertEqual(result.iqScore, 108)
        XCTAssertNil(result.confidenceInterval)
    }

    // MARK: - TestResult Score Display Helper Tests

    func testScoreWithConfidenceIntervalWhenPresent() {
        let ci = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        let result = TestResult(
            id: 1,
            testSessionId: 10,
            userId: 100,
            iqScore: 108,
            percentileRank: 70.2,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completedAt: Date(),
            confidenceInterval: ci
        )

        XCTAssertEqual(result.scoreWithConfidenceInterval, "108 (101-115)")
    }

    func testScoreWithConfidenceIntervalWhenNil() {
        let result = TestResult(
            id: 1,
            testSessionId: 10,
            userId: 100,
            iqScore: 108,
            percentileRank: 70.2,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completedAt: Date(),
            confidenceInterval: nil
        )

        XCTAssertEqual(result.scoreWithConfidenceInterval, "108")
    }

    func testScoreAccessibilityDescriptionWithConfidenceInterval() {
        let ci = ConfidenceInterval(lower: 101, upper: 115, confidenceLevel: 0.95, standardError: 3.5)
        let result = TestResult(
            id: 1,
            testSessionId: 10,
            userId: 100,
            iqScore: 108,
            percentileRank: 70.2,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completedAt: Date(),
            confidenceInterval: ci
        )

        XCTAssertEqual(
            result.scoreAccessibilityDescription,
            "IQ score 108. Score range from 101 to 115 with 95 percent confidence"
        )
    }

    func testScoreAccessibilityDescriptionWithoutConfidenceInterval() {
        let result = TestResult(
            id: 1,
            testSessionId: 10,
            userId: 100,
            iqScore: 108,
            percentileRank: 70.2,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completedAt: Date(),
            confidenceInterval: nil
        )

        XCTAssertEqual(result.scoreAccessibilityDescription, "IQ score 108")
    }

    // MARK: - ConfidenceInterval Edge Cases

    func testConfidenceIntervalAtBoundaries() {
        // Test lower boundary of valid IQ range (40)
        let ciAtLowerBound = ConfidenceInterval(lower: 40, upper: 55, confidenceLevel: 0.95, standardError: 7.5)
        XCTAssertEqual(ciAtLowerBound.lower, 40)
        XCTAssertEqual(ciAtLowerBound.rangeFormatted, "40-55")

        // Test upper boundary of valid IQ range (160)
        let ciAtUpperBound = ConfidenceInterval(lower: 145, upper: 160, confidenceLevel: 0.95, standardError: 7.5)
        XCTAssertEqual(ciAtUpperBound.upper, 160)
        XCTAssertEqual(ciAtUpperBound.rangeFormatted, "145-160")
    }

    func testConfidenceIntervalWithDifferentConfidenceLevels() throws {
        // 90% confidence level
        let json90 = """
        {
            "lower": 102,
            "upper": 114,
            "confidence_level": 0.90,
            "standard_error": 3.5
        }
        """
        let ci90 = try JSONDecoder().decode(ConfidenceInterval.self, from: XCTUnwrap(json90.data(using: .utf8)))
        XCTAssertEqual(ci90.confidencePercentage, 90)
        XCTAssertEqual(ci90.fullDescription, "90% confidence interval: 102-114")

        // 99% confidence level
        let json99 = """
        {
            "lower": 99,
            "upper": 117,
            "confidence_level": 0.99,
            "standard_error": 3.5
        }
        """
        let ci99 = try JSONDecoder().decode(ConfidenceInterval.self, from: XCTUnwrap(json99.data(using: .utf8)))
        XCTAssertEqual(ci99.confidencePercentage, 99)
        XCTAssertEqual(ci99.fullDescription, "99% confidence interval: 99-117")
    }

    // MARK: - PaginatedTestHistoryResponse Metadata Validation Tests (BCQ-043)

    func testPaginatedResponseMetadataDecoding() throws {
        let json = """
        {
            "results": [
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
                    "completed_at": "2025-12-13T10:00:00Z"
                }
            ],
            "total_count": 100,
            "limit": 50,
            "offset": 0,
            "has_more": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

        // Verify pagination metadata fields are correctly populated
        XCTAssertEqual(response.totalCount, 100, "totalCount should match expected value")
        XCTAssertEqual(response.limit, 50, "limit should match expected value")
        XCTAssertEqual(response.offset, 0, "offset should match expected value")
        XCTAssertTrue(response.hasMore, "hasMore should be true when total exceeds current page")
        XCTAssertEqual(response.results.count, 1, "results array should contain one test result")
    }

    func testPaginatedResponseTotalCountMatchesExpectedValue() throws {
        // Test various total counts to ensure consistent handling
        let testCases: [(totalCount: Int, results: Int, description: String)] = [
            (0, 0, "empty results"),
            (1, 1, "single result"),
            (50, 50, "exactly one page"),
            (100, 50, "multiple pages - first page"),
            (1000, 50, "large total count")
        ]

        for testCase in testCases {
            let resultsJson = (0 ..< testCase.results).map { i in
                """
                {
                    "id": \(i + 1),
                    "test_session_id": \(i + 10),
                    "user_id": 100,
                    "iq_score": 115,
                    "total_questions": 20,
                    "correct_answers": 14,
                    "accuracy_percentage": 70.0,
                    "completed_at": "2025-12-13T10:00:00Z"
                }
                """
            }.joined(separator: ",")

            let json = """
            {
                "results": [\(resultsJson)],
                "total_count": \(testCase.totalCount),
                "limit": 50,
                "offset": 0,
                "has_more": \(testCase.totalCount > testCase.results ? "true" : "false")
            }
            """

            let data = try XCTUnwrap(json.data(using: .utf8))
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

            XCTAssertEqual(
                response.totalCount,
                testCase.totalCount,
                "totalCount should be \(testCase.totalCount) for \(testCase.description)"
            )
            XCTAssertEqual(
                response.results.count,
                testCase.results,
                "results count should be \(testCase.results) for \(testCase.description)"
            )
        }
    }

    func testPaginatedResponseLimitAndOffsetAreCorrectlyPopulated() throws {
        // Test various limit/offset combinations
        let testCases: [(limit: Int, offset: Int, description: String)] = [
            (50, 0, "first page with default limit"),
            (100, 0, "first page with max limit"),
            (25, 0, "first page with custom limit"),
            (50, 50, "second page"),
            (50, 100, "third page"),
            (10, 90, "last partial page")
        ]

        for testCase in testCases {
            let json = """
            {
                "results": [],
                "total_count": 100,
                "limit": \(testCase.limit),
                "offset": \(testCase.offset),
                "has_more": \(testCase.offset + testCase.limit < 100 ? "true" : "false")
            }
            """

            let data = try XCTUnwrap(json.data(using: .utf8))
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

            XCTAssertEqual(
                response.limit,
                testCase.limit,
                "limit should be \(testCase.limit) for \(testCase.description)"
            )
            XCTAssertEqual(
                response.offset,
                testCase.offset,
                "offset should be \(testCase.offset) for \(testCase.description)"
            )
        }
    }

    func testPaginatedResponseHasMoreIsCorrectlyCalculated() throws {
        // Test hasMore flag with various scenarios
        let testCases: [(totalCount: Int, offset: Int, limit: Int, hasMore: Bool, description: String)] = [
            (100, 0, 50, true, "first page with more results"),
            (100, 50, 50, false, "last page - exactly at end"),
            (50, 0, 50, false, "single page - exact fit"),
            (45, 0, 50, false, "single page - partial"),
            (0, 0, 50, false, "empty results"),
            (150, 100, 50, false, "final page of multiple pages"),
            (150, 50, 50, true, "middle page")
        ]

        for testCase in testCases {
            let json = """
            {
                "results": [],
                "total_count": \(testCase.totalCount),
                "limit": \(testCase.limit),
                "offset": \(testCase.offset),
                "has_more": \(testCase.hasMore)
            }
            """

            let data = try XCTUnwrap(json.data(using: .utf8))
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

            XCTAssertEqual(
                response.hasMore,
                testCase.hasMore,
                "hasMore should be \(testCase.hasMore) for \(testCase.description)"
            )
        }
    }

    func testPaginatedResponseWithEmptyResults() throws {
        let json = """
        {
            "results": [],
            "total_count": 0,
            "limit": 50,
            "offset": 0,
            "has_more": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

        XCTAssertTrue(response.results.isEmpty, "results should be empty")
        XCTAssertEqual(response.totalCount, 0, "totalCount should be 0 for empty results")
        XCTAssertFalse(response.hasMore, "hasMore should be false for empty results")
    }

    func testPaginatedResponseWithSingleResult() throws {
        let json = """
        {
            "results": [
                {
                    "id": 1,
                    "test_session_id": 10,
                    "user_id": 100,
                    "iq_score": 108,
                    "total_questions": 20,
                    "correct_answers": 14,
                    "accuracy_percentage": 70.0,
                    "completed_at": "2025-12-13T10:00:00Z"
                }
            ],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
            "has_more": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

        XCTAssertEqual(response.results.count, 1, "results should contain exactly one item")
        XCTAssertEqual(response.totalCount, 1, "totalCount should be 1")
        XCTAssertFalse(response.hasMore, "hasMore should be false for single result")
        XCTAssertEqual(response.results[0].iqScore, 108, "result IQ score should match")
    }

    func testPaginatedResponseWithMaxLimit() throws {
        // Test with maximum allowed limit (100)
        let json = """
        {
            "results": [],
            "total_count": 500,
            "limit": 100,
            "offset": 0,
            "has_more": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

        XCTAssertEqual(response.limit, 100, "limit should be 100 (max)")
        XCTAssertEqual(response.totalCount, 500, "totalCount should reflect full dataset")
        XCTAssertTrue(response.hasMore, "hasMore should be true when more results exist")
    }

    func testPaginatedResponseCodingKeys() throws {
        // Verify snake_case to camelCase mapping works correctly
        let json = """
        {
            "results": [],
            "total_count": 42,
            "limit": 25,
            "offset": 10,
            "has_more": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

        // These assertions verify the CodingKeys enum properly maps snake_case
        XCTAssertEqual(response.totalCount, 42, "total_count should map to totalCount")
        XCTAssertEqual(response.hasMore, true, "has_more should map to hasMore")
    }

    func testPaginatedResponseWithResultsContainingOptionalFields() throws {
        // Test that results with optional fields decode correctly within paginated response
        let json = """
        {
            "results": [
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
                    "confidence_interval": {
                        "lower": 108,
                        "upper": 122,
                        "confidence_level": 0.95,
                        "standard_error": 3.5
                    },
                    "domain_scores": {
                        "pattern": {"correct": 3, "total": 4, "pct": 75.0}
                    }
                },
                {
                    "id": 2,
                    "test_session_id": 11,
                    "user_id": 100,
                    "iq_score": 100,
                    "percentile_rank": null,
                    "total_questions": 20,
                    "correct_answers": 10,
                    "accuracy_percentage": 50.0,
                    "completion_time_seconds": null,
                    "completed_at": "2025-12-12T10:00:00Z",
                    "confidence_interval": null,
                    "domain_scores": null
                }
            ],
            "total_count": 2,
            "limit": 50,
            "offset": 0,
            "has_more": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(PaginatedTestHistoryResponse.self, from: data)

        XCTAssertEqual(response.results.count, 2, "should decode both results")
        XCTAssertEqual(response.totalCount, 2, "totalCount should be 2")

        // First result with optional fields present
        let firstResult = response.results[0]
        XCTAssertNotNil(firstResult.confidenceInterval, "first result should have CI")
        XCTAssertNotNil(firstResult.domainScores, "first result should have domain scores")
        XCTAssertEqual(firstResult.completionTimeSeconds, 1200, "first result should have completion time")

        // Second result with optional fields null
        let secondResult = response.results[1]
        XCTAssertNil(secondResult.confidenceInterval, "second result should have nil CI")
        XCTAssertNil(secondResult.domainScores, "second result should have nil domain scores")
        XCTAssertNil(secondResult.completionTimeSeconds, "second result should have nil completion time")
    }
}
