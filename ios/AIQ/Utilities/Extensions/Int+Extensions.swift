import Foundation

extension Int {
    /// Returns the ordinal suffix for this integer (e.g., "st", "nd", "rd", "th")
    /// Examples: 1 -> "st", 2 -> "nd", 3 -> "rd", 4 -> "th", 11 -> "th", 21 -> "st"
    var ordinalSuffix: String {
        let ones = self % 10
        let tens = (self % 100) / 10

        // Special case: 11th, 12th, 13th
        if tens == 1 {
            return "th"
        }

        switch ones {
        case 1: return "st"
        case 2: return "nd"
        case 3: return "rd"
        default: return "th"
        }
    }

    /// Returns this integer with its ordinal suffix (e.g., "1st", "2nd", "3rd", "4th")
    var ordinalString: String {
        "\(self)\(ordinalSuffix)"
    }
}
