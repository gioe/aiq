import SwiftUI

/// Utility for classifying IQ scores and providing consistent visual styling
enum IQScoreUtility {
    /// IQ score classification categories based on standard ranges
    enum Category {
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
