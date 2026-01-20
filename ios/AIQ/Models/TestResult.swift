import AIQAPIClient
import Foundation
import SwiftUI

// MARK: - TestResult Type Alias

/// Test result model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.TestResultResponse` type.
/// UI-specific computed properties are provided via the `TestResult+Extensions.swift` file.
///
/// **Important Notes:**
/// - The generated type includes required fields: id, testSessionId, userId, iqScore, totalQuestions,
///   correctAnswers, accuracyPercentage, completedAt
/// - Optional properties (percentileRank, completionTimeSeconds, domainScores, confidenceInterval,
///   strongestDomain, weakestDomain) may have limited availability depending on OpenAPI generator version
/// - See TestResult+Extensions.swift for computed properties and UI helpers
public typealias TestResult = Components.Schemas.TestResultResponse

/// Legacy alias for backward compatibility with TestTakingViewModel
///
/// The SubmitTestResponse.result property returns a TestResultResponse, which is now aliased
/// as TestResult. This alias maintains compatibility with existing code that uses SubmittedTestResult.
public typealias SubmittedTestResult = TestResult

// MARK: - Paginated Test History Response (BCQ-004)

/// Response wrapper for paginated test history endpoint re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.PaginatedTestHistoryResponse` type.
/// The backend returns paginated results with metadata for pagination UI.
///
/// **Generated Properties:**
/// - results: [TestResultResponse] - List of test results for the current page
/// - totalCount: Int (mapped from total_count) - Total number of test results available for this user
/// - limit: Int - Number of results per page (max 100)
/// - offset: Int - Offset from the start of the results
/// - hasMore: Bool (mapped from has_more) - Whether there are more results beyond this page
public typealias PaginatedTestHistoryResponse = Components.Schemas.PaginatedTestHistoryResponse

// MARK: - Confidence Interval

/// Confidence interval model re-exported from OpenAPI generated types
///
/// This typealias provides a clean interface to the generated `Components.Schemas.ConfidenceIntervalSchema` type.
/// UI-specific computed properties are provided via an extension below.
///
/// Confidence intervals quantify the uncertainty in score measurement,
/// providing a range within which the true score is likely to fall.
/// This is calculated using the Standard Error of Measurement (SEM)
/// derived from the test's reliability coefficient.
///
/// Example: A score of 108 with CI [101, 115] at 95% confidence means
/// there is a 95% probability the true score falls between 101 and 115.
///
/// **Generated Properties:**
/// - lower: Int - Lower bound of the confidence interval (clamped to valid IQ range 40-160)
/// - upper: Int - Upper bound of the confidence interval (clamped to valid IQ range 40-160)
/// - confidenceLevel: Double (mapped from confidence_level) - Confidence level as a decimal (e.g., 0.95 for 95% CI)
/// - standardError: Double (mapped from standard_error) - Standard Error of Measurement (SEM)
///   used to calculate the interval
public typealias ConfidenceInterval = Components.Schemas.ConfidenceIntervalSchema

// MARK: - Domain Score

/// Represents performance breakdown for a single cognitive domain.
struct DomainScore: Codable, Equatable {
    let correct: Int
    let total: Int
    let pct: Double?
    /// Percentile rank (0-100) compared to population, available when population stats are configured
    let percentile: Double?

    /// Formatted percentage string (e.g., "75%")
    var percentageFormatted: String {
        guard let percentage = pct else { return "N/A" }
        return "\(Int(round(percentage)))%"
    }

    /// Accuracy as a decimal (0.0-1.0)
    var accuracy: Double? {
        guard let percentage = pct else { return nil }
        return percentage / 100.0
    }

    /// Formatted percentile string (e.g., "71st")
    var percentileFormatted: String? {
        guard let percentile else { return nil }
        return Int(round(percentile)).ordinalString
    }

    /// Description for accessibility (e.g., "71st percentile")
    var percentileDescription: String? {
        guard let formatted = percentileFormatted else { return nil }
        return "\(formatted) percentile"
    }

    /// Performance level based on percentile
    var performanceLevel: PerformanceLevel? {
        guard let percentile else { return nil }
        switch percentile {
        case 0 ..< 25:
            return .needsWork
        case 25 ..< 50:
            return .belowAverage
        case 50 ..< 75:
            return .average
        case 75 ..< 90:
            return .good
        case 90...:
            return .excellent
        default:
            return nil
        }
    }
}

/// Performance level categories for domain scores
enum PerformanceLevel {
    case needsWork // < 25th percentile
    case belowAverage // 25-50th percentile
    case average // 50-75th percentile
    case good // 75-90th percentile
    case excellent // >= 90th percentile

    var displayName: String {
        switch self {
        case .needsWork: "Needs Work"
        case .belowAverage: "Below Average"
        case .average: "Average"
        case .good: "Good"
        case .excellent: "Excellent"
        }
    }

    /// Color for icons, backgrounds, and UI elements (not text)
    /// - Warning: Light mode contrast insufficient for text on white backgrounds
    /// - Use `textColor` for text to ensure WCAG AA compliance
    var color: Color {
        switch self {
        case .needsWork: ColorPalette.performanceNeedsWork
        case .belowAverage: ColorPalette.performanceBelowAverage
        case .average: ColorPalette.performanceAverage
        case .good: ColorPalette.performanceGood
        case .excellent: ColorPalette.performanceExcellent
        }
    }

    /// WCAG AA compliant text color (4.5:1 contrast ratio on white backgrounds)
    /// Use this for displaying text in performance level colors
    var textColor: Color {
        switch self {
        case .needsWork: ColorPalette.errorText
        case .belowAverage: ColorPalette.warningText
        case .average: ColorPalette.infoText
        case .good: ColorPalette.performanceGoodText
        case .excellent: ColorPalette.successText
        }
    }
}
