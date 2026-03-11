import SwiftUI

/// Utility for classifying IQ scores and providing consistent visual styling
enum IQScoreUtility {
    /// IQ score classification categories based on standard ranges
    enum Category: Equatable, CaseIterable {
        case extremelyLow
        case belowAverage
        case average
        case aboveAverage
        case gifted
        case highlyGifted
        case invalid

        /// User-facing description of the IQ score category
        var description: String {
            switch self {
            case .extremelyLow:
                "Extremely Low"
            case .belowAverage:
                "Below Average"
            case .average:
                "Average"
            case .aboveAverage:
                "Above Average"
            case .gifted:
                "Gifted"
            case .highlyGifted:
                "Highly Gifted"
            case .invalid:
                "Invalid Score"
            }
        }

        /// Color representing the score category
        /// - Note: For backgrounds, badges, and icons only. Use `textColor` for text labels.
        /// - Warning: Light mode contrast may be insufficient for text (WCAG AA requires 4.5:1)
        /// Uses ColorPalette semantic colors for design system consistency
        var color: Color {
            switch self {
            case .highlyGifted, .gifted:
                ColorPalette.success
            case .aboveAverage:
                ColorPalette.info
            case .average:
                ColorPalette.info
            case .belowAverage:
                ColorPalette.warning
            case .extremelyLow, .invalid:
                ColorPalette.error
            }
        }

        /// WCAG AA compliant text color for the score category
        /// - Note: Use this for all text labels. Use `color` for backgrounds, badges, and icons.
        /// - Returns: A color meeting WCAG AA 4.5:1 contrast ratio in both light and dark modes
        ///
        /// This property ensures accessibility by using darker color variants in light mode
        /// that meet WCAG AA contrast requirements (4.5:1) for normal text on white backgrounds.
        /// In dark mode, standard semantic colors provide excellent contrast (7.5:1 to 11.4:1).
        var textColor: Color {
            switch self {
            case .highlyGifted, .gifted:
                ColorPalette.successText
            case .aboveAverage, .average:
                ColorPalette.infoText
            case .belowAverage:
                ColorPalette.warningText
            case .extremelyLow, .invalid:
                ColorPalette.errorText
            }
        }

        /// Gradient representing the score category
        /// Uses ColorPalette semantic colors for design system consistency
        var gradient: LinearGradient {
            let colors: [Color] = switch self {
            case .highlyGifted, .gifted:
                [ColorPalette.success, ColorPalette.success.opacity(0.7)]
            case .aboveAverage:
                [ColorPalette.info, ColorPalette.info.opacity(0.7)]
            case .average:
                [ColorPalette.info.opacity(0.7), ColorPalette.info]
            case .belowAverage:
                [ColorPalette.warning, ColorPalette.warning.opacity(0.7)]
            case .extremelyLow, .invalid:
                [ColorPalette.error, ColorPalette.warning]
            }

            return LinearGradient(
                colors: colors,
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }

        /// SF Symbol icon name representing the score category
        var icon: String {
            switch self {
            case .highlyGifted, .gifted:
                "star.fill"
            case .aboveAverage:
                "rosette"
            case .average:
                "circle.fill"
            case .belowAverage, .extremelyLow, .invalid:
                "circle"
            }
        }

        /// Statistical percentile range for the score category
        ///
        /// Based on the standard IQ distribution (mean=100, SD=15):
        /// - z-score cutoffs correspond to IQ thresholds in `classify(_:)`
        /// - Percentiles derived from cumulative normal distribution
        ///
        /// See docs/methodology/METHODOLOGY.md Section 3.3 for reference.
        var percentileRange: String {
            switch self {
            case .highlyGifted:
                "99.9th percentile and above"
            case .gifted:
                "98th to 99.9th percentile"
            case .aboveAverage:
                "84th to 98th percentile"
            case .average:
                "16th to 84th percentile"
            case .belowAverage:
                "2nd to 16th percentile"
            case .extremelyLow:
                "Below 2nd percentile"
            case .invalid:
                "N/A"
            }
        }
    }

    /// Classifies an IQ score into a category
    /// - Parameter score: The IQ score to classify
    /// - Returns: The appropriate category for the given score
    static func classify(_ score: Int) -> Category {
        switch score {
        case 0 ..< 70:
            .extremelyLow
        case 70 ..< 85:
            .belowAverage
        case 85 ..< 115:
            .average
        case 115 ..< 130:
            .aboveAverage
        case 130 ..< 145:
            .gifted
        case 145...:
            .highlyGifted
        default:
            .invalid
        }
    }
}
