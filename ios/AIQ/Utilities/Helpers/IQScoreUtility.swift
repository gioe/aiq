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
        var color: Color {
            switch self {
            case .highlyGifted, .gifted:
                .green
            case .aboveAverage:
                .blue
            case .average:
                .cyan
            case .belowAverage:
                .orange
            case .extremelyLow, .invalid:
                .red
            }
        }

        /// Gradient representing the score category
        var gradient: LinearGradient {
            let colors: [Color] = switch self {
            case .highlyGifted, .gifted:
                [.green, .mint]
            case .aboveAverage:
                [.blue, .cyan]
            case .average:
                [.cyan, .blue]
            case .belowAverage:
                [.orange, .yellow]
            case .extremelyLow, .invalid:
                [.red, .orange]
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
