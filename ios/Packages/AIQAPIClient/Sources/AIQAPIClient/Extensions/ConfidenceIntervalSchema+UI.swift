// MARK: - ConfidenceIntervalSchema UI Extensions

//
// Extends the generated ConfidenceIntervalSchema with formatting and accessibility helpers.
// Confidence intervals represent the statistical uncertainty around an IQ score.
//
// Pattern: Each extension file follows the naming convention `<TypeName>+UI.swift`.

import Foundation

public extension Components.Schemas.ConfidenceIntervalSchema {
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
    /// Callers can use this to make precision decisions based on their own thresholds.
    /// Note: isPrecise was intentionally not included as "precision" thresholds vary by context
    /// and should be defined in the UI layer where the domain-specific cutoffs are known.
    var intervalWidth: Int {
        upper - lower
    }

    /// Standard error formatted to 2 decimal places
    var standardErrorFormatted: String {
        String(format: "%.2f", standardError)
    }
}
