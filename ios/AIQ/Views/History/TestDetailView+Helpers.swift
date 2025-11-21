import SwiftUI

// MARK: - TestDetailView Computed Properties Extension

extension TestDetailView {
    var scoreColor: Color {
        switch testResult.iqScore {
        case 130...:
            .green
        case 115 ..< 130:
            .blue
        case 85 ..< 115:
            .cyan
        case 70 ..< 85:
            .orange
        default:
            .red
        }
    }

    var scoreGradient: LinearGradient {
        let colors: [Color] = switch testResult.iqScore {
        case 130...:
            [.green, .mint]
        case 115 ..< 130:
            [.blue, .cyan]
        case 85 ..< 115:
            [.cyan, .blue]
        case 70 ..< 85:
            [.orange, .yellow]
        default:
            [.red, .orange]
        }

        return LinearGradient(
            colors: colors,
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    var scoreIconName: String {
        switch testResult.iqScore {
        case 130...:
            "star.fill"
        case 115 ..< 130:
            "rosette"
        case 85 ..< 115:
            "circle.fill"
        default:
            "circle"
        }
    }

    var iqRangeDescription: String {
        switch testResult.iqScore {
        case 0 ..< 70:
            "Extremely Low"
        case 70 ..< 85:
            "Below Average"
        case 85 ..< 115:
            "Average"
        case 115 ..< 130:
            "Above Average"
        case 130 ..< 145:
            "Gifted"
        case 145...:
            "Highly Gifted"
        default:
            "Invalid Score"
        }
    }

    var comparisonIcon: String {
        guard let average = userAverage else { return "equal.circle.fill" }
        if testResult.iqScore > average {
            return "arrow.up.circle.fill"
        } else if testResult.iqScore < average {
            return "arrow.down.circle.fill"
        } else {
            return "equal.circle.fill"
        }
    }

    var comparisonColor: Color {
        guard let average = userAverage else { return .gray }
        if testResult.iqScore > average {
            return .green
        } else if testResult.iqScore < average {
            return .orange
        } else {
            return .blue
        }
    }

    var comparisonText: String {
        guard let average = userAverage else { return "Only test result" }
        if testResult.iqScore > average {
            return "Above your average"
        } else if testResult.iqScore < average {
            return "Below your average"
        } else {
            return "Equal to your average"
        }
    }

    var comparisonDifference: String {
        guard let average = userAverage else { return "" }
        let diff = abs(testResult.iqScore - average)
        if testResult.iqScore > average {
            return "+\(diff)"
        } else if testResult.iqScore < average {
            return "-\(diff)"
        } else {
            return "±0"
        }
    }

    var performanceIcon: String {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return "star.circle.fill"
        case 75 ..< 90:
            return "hand.thumbsup.fill"
        case 60 ..< 75:
            return "checkmark.circle.fill"
        case 50 ..< 60:
            return "arrow.up.circle.fill"
        default:
            return "book.fill"
        }
    }

    var performanceColor: Color {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return .green
        case 75 ..< 90:
            return .blue
        case 60 ..< 75:
            return .cyan
        case 50 ..< 60:
            return .orange
        default:
            return .red
        }
    }

    var performanceTitle: String {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return "Outstanding Performance"
        case 75 ..< 90:
            return "Great Job"
        case 60 ..< 75:
            return "Good Effort"
        case 50 ..< 60:
            return "Keep Practicing"
        default:
            return "Room for Improvement"
        }
    }

    var performanceDescription: String {
        let accuracy = testResult.accuracyPercentage

        switch accuracy {
        case 90...:
            return "You've demonstrated excellent problem-solving abilities with this test. " +
                "Your performance shows strong cognitive skills."
        case 75 ..< 90:
            return "Your performance shows strong analytical skills. " +
                "You're doing well and demonstrating solid understanding."
        case 60 ..< 75:
            return "You're making good progress. " +
                "Consider reviewing the areas you found challenging to further improve."
        case 50 ..< 60:
            return "You're building your skills. " +
                "Regular practice and reviewing difficult concepts will help you improve."
        default:
            return "There's room to grow. " +
                "Focus on understanding the patterns and practicing regularly to build your skills."
        }
    }

    func formatFullDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .long
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }

    func formatAverageTime(_ totalSeconds: Int, questions: Int) -> String {
        let avgSeconds = Double(totalSeconds) / Double(questions)
        let minutes = Int(avgSeconds) / 60
        let seconds = Int(avgSeconds) % 60

        if minutes > 0 {
            return String(format: "%d:%02d per question", minutes, seconds)
        } else {
            return String(format: "%d sec per question", seconds)
        }
    }
}
