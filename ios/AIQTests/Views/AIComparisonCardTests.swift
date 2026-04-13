@testable import AIQ
import AIQAPIClientCore
import XCTest

/// Tests for `AIComparisonCardLogic` — the pure computation layer extracted from `AIComparisonCard`.
///
/// No SwiftUI environment is required. All test methods exercise static functions directly,
/// so the suite is synchronous and has no `@MainActor` annotation.
final class AIComparisonCardTests: XCTestCase {
    // MARK: - Test Helpers

    private func makeModel(
        displayName: String = "Test Model",
        meanIq: Double = 100,
        accuracyPct: Double = 80,
        vendor: String = "test",
        runs: Int = 10,
        domainAccuracy: [Components.Schemas.DomainAccuracySummary]? = nil
    ) -> Components.Schemas.ModelSummary {
        .init(
            displayName: displayName,
            vendor: vendor,
            meanIq: meanIq,
            accuracyPct: accuracyPct,
            runs: runs,
            domainAccuracy: domainAccuracy
        )
    }

    private func makeDomainAccuracy(
        domain: String,
        accuracyPct: Double = 75.0,
        totalQuestions: Int = 20
    ) -> Components.Schemas.DomainAccuracySummary {
        .init(domain: domain, accuracyPct: accuracyPct, totalQuestions: totalQuestions)
    }

    private func makeDomainScore(
        correct: Int = 15,
        total: Int = 20,
        pct: Double? = 75.0,
        percentile: Double? = nil
    ) -> DomainScore {
        DomainScore(correct: correct, total: total, pct: pct, percentile: percentile)
    }

    // MARK: - Gauge Position Tests

    func testGaugePositionAtMinimumBoundary() {
        // Given - IQ exactly at gauge minimum
        let iq: Double = 70
        let barWidth: CGFloat = 900

        // When
        let position = AIComparisonCardLogic.gaugePosition(for: iq, barWidth: barWidth)

        // Then - fraction = (70 - 70) / (160 - 70) = 0, position = 0
        XCTAssertEqual(position, 0)
    }

    func testGaugePositionAtMaximumBoundary() {
        // Given - IQ exactly at gauge maximum
        let iq: Double = 160
        let barWidth: CGFloat = 900

        // When
        let position = AIComparisonCardLogic.gaugePosition(for: iq, barWidth: barWidth)

        // Then - fraction = (160 - 70) / (160 - 70) = 1, position = 900
        XCTAssertEqual(position, 900)
    }

    func testGaugePositionBelowMinimumClamps() {
        // Given - IQ below gaugeMinIQ (70)
        let clampedPosition = AIComparisonCardLogic.gaugePosition(for: 70, barWidth: 900)

        // When
        let belowMinPosition = AIComparisonCardLogic.gaugePosition(for: 50, barWidth: 900)

        // Then - clamped to minimum, same result as IQ=70
        XCTAssertEqual(belowMinPosition, clampedPosition)
        XCTAssertEqual(belowMinPosition, 0)
    }

    func testGaugePositionAboveMaximumClamps() {
        // Given - IQ above gaugeMaxIQ (160)
        let clampedPosition = AIComparisonCardLogic.gaugePosition(for: 160, barWidth: 900)

        // When
        let aboveMaxPosition = AIComparisonCardLogic.gaugePosition(for: 200, barWidth: 900)

        // Then - clamped to maximum, same result as IQ=160
        XCTAssertEqual(aboveMaxPosition, clampedPosition)
        XCTAssertEqual(aboveMaxPosition, 900)
    }

    func testGaugePositionMidRange() {
        // Given - IQ at the midpoint of 70–160 range (115)
        let iq: Double = 115
        let barWidth: CGFloat = 900

        // When
        let position = AIComparisonCardLogic.gaugePosition(for: iq, barWidth: barWidth)

        // Then - fraction = (115 - 70) / (160 - 70) = 45 / 90 = 0.5, position = 450
        XCTAssertEqual(position, 450)
    }

    func testGaugePositionWithZeroBarWidth() {
        // Given - bar has no width
        let barWidth: CGFloat = 0

        // When
        let position = AIComparisonCardLogic.gaugePosition(for: 120, barWidth: barWidth)

        // Then - barWidth * fraction = 0 * anything = 0
        XCTAssertEqual(position, 0)
    }

    // MARK: - Best Model Tests

    func testBestModelWithEmptyArray() {
        // When
        let result = AIComparisonCardLogic.bestModel(from: [])

        // Then
        XCTAssertNil(result)
    }

    func testBestModelWithSingleModel() {
        // Given
        let model = makeModel(displayName: "Solo", meanIq: 110)

        // When
        let result = AIComparisonCardLogic.bestModel(from: [model])

        // Then
        XCTAssertEqual(result?.displayName, "Solo")
        XCTAssertEqual(result?.meanIq, 110)
    }

    func testBestModelWithMultipleModels() {
        // Given - three models with different meanIq values
        let models = [
            makeModel(displayName: "Low", meanIq: 95),
            makeModel(displayName: "High", meanIq: 120),
            makeModel(displayName: "Mid", meanIq: 105)
        ]

        // When
        let result = AIComparisonCardLogic.bestModel(from: models)

        // Then - the model with meanIq 120 wins
        XCTAssertEqual(result?.displayName, "High")
        XCTAssertEqual(result?.meanIq, 120)
    }

    func testBestModelWithEqualMeanIQ() {
        // Given - two models share the same meanIq
        let models = [
            makeModel(displayName: "Alpha", meanIq: 115),
            makeModel(displayName: "Beta", meanIq: 115)
        ]

        // When
        let result = AIComparisonCardLogic.bestModel(from: models)

        // Then - one of the tied models is returned (no crash, non-nil)
        XCTAssertNotNil(result)
        XCTAssertEqual(result?.meanIq, 115)
    }

    // MARK: - Average AI IQ Tests

    func testAverageAIIQWithEmptyArray() {
        // When
        let result = AIComparisonCardLogic.averageAIIQ(from: [])

        // Then - guard clause returns 0
        XCTAssertEqual(result, 0)
    }

    func testAverageAIIQWithSingleModel() {
        // Given
        let models = [makeModel(meanIq: 110)]

        // When
        let result = AIComparisonCardLogic.averageAIIQ(from: models)

        // Then
        XCTAssertEqual(result, 110)
    }

    func testAverageAIIQWithMultipleModels() {
        // Given - mean of 90, 100, 120 = 310 / 3 ≈ 103.333…
        let models = [
            makeModel(meanIq: 90),
            makeModel(meanIq: 100),
            makeModel(meanIq: 120)
        ]

        // When
        let result = AIComparisonCardLogic.averageAIIQ(from: models)

        // Then
        XCTAssertEqual(result, 310.0 / 3.0, accuracy: 0.001)
    }

    func testAverageAIIQWithIdenticalModels() {
        // Given - all models have the same meanIq
        let models = [
            makeModel(meanIq: 108),
            makeModel(meanIq: 108),
            makeModel(meanIq: 108)
        ]

        // When
        let result = AIComparisonCardLogic.averageAIIQ(from: models)

        // Then
        XCTAssertEqual(result, 108)
    }

    // MARK: - Compared Domains Tests

    func testComparedDomainsWithNilUserScores() {
        // Given
        let bestModel = makeModel(domainAccuracy: [makeDomainAccuracy(domain: "pattern")])

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: nil, bestModel: bestModel)

        // Then - guard returns [] when userDomainScores is nil
        XCTAssertTrue(result.isEmpty)
    }

    func testComparedDomainsWithNilBestModel() {
        // Given
        let userScores = ["pattern": makeDomainScore()]

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: userScores, bestModel: nil)

        // Then - guard returns [] when bestModel is nil
        XCTAssertTrue(result.isEmpty)
    }

    func testComparedDomainsWithNilDomainAccuracy() {
        // Given - bestModel has domainAccuracy = nil
        let bestModel = makeModel(domainAccuracy: nil)
        let userScores = ["pattern": makeDomainScore()]

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: userScores, bestModel: bestModel)

        // Then - guard on bestModel?.domainAccuracy returns []
        XCTAssertTrue(result.isEmpty)
    }

    func testComparedDomainsWithMatchingDomains() {
        // Given - user has pattern + logic; AI has pattern + logic + spatial
        let userScores: [String: DomainScore] = [
            "pattern": makeDomainScore(pct: 80.0),
            "logic": makeDomainScore(pct: 70.0)
        ]
        let bestModel = makeModel(domainAccuracy: [
            makeDomainAccuracy(domain: "pattern", accuracyPct: 85.0),
            makeDomainAccuracy(domain: "logic", accuracyPct: 90.0),
            makeDomainAccuracy(domain: "spatial", accuracyPct: 75.0)
        ])

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: userScores, bestModel: bestModel)

        // Then - only pattern and logic appear (intersection)
        XCTAssertEqual(result.count, 2)
        let domains = result.map(\.domain.rawValue)
        XCTAssertTrue(domains.contains("pattern"))
        XCTAssertTrue(domains.contains("logic"))
        XCTAssertFalse(domains.contains("spatial"))
    }

    func testComparedDomainsWithNoMatchingDomains() {
        // Given - user has pattern, AI has logic only
        let userScores: [String: DomainScore] = [
            "pattern": makeDomainScore()
        ]
        let bestModel = makeModel(domainAccuracy: [
            makeDomainAccuracy(domain: "logic")
        ])

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: userScores, bestModel: bestModel)

        // Then - no overlap
        XCTAssertTrue(result.isEmpty)
    }

    func testComparedDomainsWithNilUserPct() {
        // Given - user has a domain score but pct is nil
        let userScores: [String: DomainScore] = [
            "pattern": makeDomainScore(pct: nil)
        ]
        let bestModel = makeModel(domainAccuracy: [
            makeDomainAccuracy(domain: "pattern")
        ])

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: userScores, bestModel: bestModel)

        // Then - domain is filtered out because userPct is nil
        XCTAssertTrue(result.isEmpty)
    }

    func testComparedDomainsReturnsCorrectValues() {
        // Given
        let userScores: [String: DomainScore] = [
            "pattern": makeDomainScore(pct: 72.0),
            "logic": makeDomainScore(pct: 88.0)
        ]
        let bestModel = makeModel(domainAccuracy: [
            makeDomainAccuracy(domain: "pattern", accuracyPct: 91.0),
            makeDomainAccuracy(domain: "logic", accuracyPct: 77.0)
        ])

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: userScores, bestModel: bestModel)

        // Then - verify the exact numeric values come through correctly
        XCTAssertEqual(result.count, 2)

        guard let patternEntry = result.first(where: { $0.domain.rawValue == "pattern" }),
              let logicEntry = result.first(where: { $0.domain.rawValue == "logic" })
        else {
            return XCTFail("Expected pattern and logic entries in result")
        }

        XCTAssertEqual(patternEntry.userPct, 72.0, accuracy: 0.001)
        XCTAssertEqual(patternEntry.aiPct, 91.0, accuracy: 0.001)
        XCTAssertEqual(logicEntry.userPct, 88.0, accuracy: 0.001)
        XCTAssertEqual(logicEntry.aiPct, 77.0, accuracy: 0.001)
    }

    func testComparedDomainsPreservesDomainOrder() {
        // Given - user and AI both have all six domains, in shuffled insertion order
        let userScores: [String: DomainScore] = [
            "verbal": makeDomainScore(pct: 60.0),
            "memory": makeDomainScore(pct: 55.0),
            "math": makeDomainScore(pct: 65.0),
            "spatial": makeDomainScore(pct: 70.0),
            "logic": makeDomainScore(pct: 75.0),
            "pattern": makeDomainScore(pct: 80.0)
        ]
        let bestModel = makeModel(domainAccuracy: [
            makeDomainAccuracy(domain: "memory"),
            makeDomainAccuracy(domain: "verbal"),
            makeDomainAccuracy(domain: "math"),
            makeDomainAccuracy(domain: "logic"),
            makeDomainAccuracy(domain: "spatial"),
            makeDomainAccuracy(domain: "pattern")
        ])

        // When
        let result = AIComparisonCardLogic.comparedDomains(userDomainScores: userScores, bestModel: bestModel)

        // Then - result order must follow CognitiveDomain.allCases: pattern, logic, spatial, math, verbal, memory
        let expectedOrder = TestResult.CognitiveDomain.allCases
        XCTAssertEqual(result.count, expectedOrder.count)
        for (index, expectedDomain) in expectedOrder.enumerated() {
            XCTAssertEqual(
                result[index].domain,
                expectedDomain,
                "Expected domain \(expectedDomain.rawValue) at index \(index), got \(result[index].domain.rawValue)"
            )
        }
    }
}
