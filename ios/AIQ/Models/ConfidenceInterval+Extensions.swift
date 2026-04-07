import AIQAPIClientCore
import Foundation

// MARK: - ConfidenceIntervalSchema UI Extensions

// Extensions for the ConfidenceInterval type (Components.Schemas.ConfidenceIntervalSchema)
//
// Provides formatting and accessibility helpers for confidence intervals, which represent
// the statistical uncertainty around an IQ score.
//
// Migrated from the APIClient package to the app target (TASK-711) following the
// 'bring your own extensions' pattern.

extension Components.Schemas.ConfidenceIntervalSchema {
    /// Formatted range string (e.g., "101-115")
    var rangeFormatted: String {
        "\(lower)-\(upper)"
    }

    /// Confidence level as a percentage integer (e.g., 95 for 0.95)
    var confidencePercentage: Int {
        Int(round(confidenceLevel * 100))
    }

    /// Full description (e.g., "95% confidence interval: 101-115")
    var fullDescription: String {
        "\(confidencePercentage)% confidence interval: \(rangeFormatted)"
    }

    /// Accessibility description for VoiceOver
    var accessibilityDescription: String {
        "Score range from \(lower) to \(upper) with \(confidencePercentage) percent confidence"
    }

    /// Width of the interval in IQ points (e.g., 14 for range 101-115)
    var intervalWidth: Int {
        upper - lower
    }

    /// Standard error formatted to 2 decimal places
    var standardErrorFormatted: String {
        String(format: "%.2f", standardError)
    }
}
