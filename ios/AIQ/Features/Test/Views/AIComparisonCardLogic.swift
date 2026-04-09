import AIQAPIClientCore
import CoreGraphics

// MARK: - AI Comparison Card Logic

/// Pure computation logic extracted from `AIComparisonCard` for testability.
///
/// All methods are stateless and side-effect-free. The view delegates to these
/// static functions so the math can be exercised without a SwiftUI environment.
enum AIComparisonCardLogic {
    // MARK: - Constants

    /// The minimum IQ value represented on the gauge bar.
    static let gaugeMinIQ: Double = 70

    /// The maximum IQ value represented on the gauge bar.
    static let gaugeMaxIQ: Double = 160

    // MARK: - Gauge Position

    /// Returns the horizontal offset (in points) for an IQ score on a gauge bar.
    ///
    /// Scores outside `[gaugeMinIQ, gaugeMaxIQ]` are clamped to the boundaries,
    /// so the marker never overflows the bar.
    ///
    /// - Parameters:
    ///   - iq: The IQ score to position.
    ///   - barWidth: The full pixel width of the gauge track.
    /// - Returns: A `CGFloat` offset from the leading edge, in the range `[0, barWidth]`.
    static func gaugePosition(for iq: Double, barWidth: CGFloat) -> CGFloat {
        let clamped = max(gaugeMinIQ, min(gaugeMaxIQ, iq))
        let fraction = (clamped - gaugeMinIQ) / (gaugeMaxIQ - gaugeMinIQ)
        return barWidth * CGFloat(fraction)
    }

    // MARK: - Best Model

    /// Returns the model with the highest `meanIq`, or `nil` if the array is empty.
    ///
    /// When multiple models share the same `meanIq` the result is implementation-defined
    /// (one of the tied models is returned, but callers should not depend on which one).
    ///
    /// - Parameter models: The array of benchmark model summaries to search.
    static func bestModel(from models: [Components.Schemas.ModelSummary]) -> Components.Schemas.ModelSummary? {
        models.max { $0.meanIq < $1.meanIq }
    }

    // MARK: - Average AI IQ

    /// Returns the arithmetic mean of `meanIq` across all models, or `0` when the array is empty.
    ///
    /// - Parameter models: The array of benchmark model summaries to average.
    static func averageAIIQ(from models: [Components.Schemas.ModelSummary]) -> Double {
        guard !models.isEmpty else { return 0 }
        let total = models.reduce(0.0) { $0 + $1.meanIq }
        return total / Double(models.count)
    }

    // MARK: - Compared Domains

    /// Returns the cognitive domains present in both the user's results and the best AI model's
    /// domain accuracy data, in `CognitiveDomain.allCases` order.
    ///
    /// A domain is included only when:
    /// - The user has a non-`nil` `pct` for that domain.
    /// - The best AI model reports an `accuracyPct` for that domain.
    ///
    /// - Parameters:
    ///   - userDomainScores: The user's per-domain score breakdown, keyed by `domain.rawValue`.
    ///   - bestModel: The highest-ranked AI benchmark model.
    /// - Returns: Tuples of `(domain, userPct, aiPct)` sorted by `CognitiveDomain.allCases` order.
    static func comparedDomains(
        userDomainScores: [String: DomainScore]?,
        bestModel: Components.Schemas.ModelSummary?
    ) -> [(domain: TestResult.CognitiveDomain, userPct: Double, aiPct: Double)] {
        guard let userScores = userDomainScores,
              let bestModelDomains = bestModel?.domainAccuracy
        else { return [] }

        return TestResult.CognitiveDomain.allCases.compactMap { domain in
            guard let userScore = userScores[domain.rawValue],
                  let userPct = userScore.pct,
                  let aiDomain = bestModelDomains.first(where: { $0.domain == domain.rawValue })
            else { return nil }
            return (domain: domain, userPct: userPct, aiPct: aiDomain.accuracyPct)
        }
    }
}
