import SwiftUI

// MARK: - Percentile Card Extension

extension TestResultsView {
    /// Percentile ranking display card for test results
    func percentileCard(percentileRank: Double?, showAnimation: Bool) -> some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Medal icon
            Image(systemName: "medal.fill")
                .font(.system(size: DesignSystem.IconSize.lg))
                .foregroundStyle(
                    LinearGradient(
                        colors: [.orange, .yellow],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .scaleEffect(showAnimation ? 1.0 : 0.5)
                .opacity(showAnimation ? 1.0 : 0.0)
                .accessibilityHidden(true)

            // Percentile rank - large display
            if let percentileText = percentileFormatted(percentileRank) {
                Text(percentileText)
                    .font(Typography.h1)
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ColorPalette.statBlue, ColorPalette.statPurple],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .scaleEffect(showAnimation ? 1.0 : 0.8)
                    .opacity(showAnimation ? 1.0 : 0.0)
            }

            // Detailed percentile description
            if let description = percentileDescription(percentileRank) {
                Text(description)
                    .font(Typography.bodyMedium)
                    .foregroundColor(ColorPalette.textSecondary)
                    .opacity(showAnimation ? 1.0 : 0.0)
            }

            // Context message
            Text("You scored higher than \(percentileContextText(percentileRank)) of test takers")
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textTertiary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignSystem.Spacing.lg)
                .padding(.top, DesignSystem.Spacing.xs)
                .opacity(showAnimation ? 1.0 : 0.0)
        }
        .padding(DesignSystem.Spacing.xl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.lg,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: ColorPalette.background
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
        .accessibilityElement(children: .combine)
    }

    // MARK: - Percentile Helper Methods

    func percentileFormatted(_ percentileRank: Double?) -> String? {
        guard let percentile = percentileRank else { return nil }
        let topPercent = Int(round(100 - percentile))
        return "Top \(topPercent)%"
    }

    func percentileDescription(_ percentileRank: Double?) -> String? {
        guard let percentile = percentileRank else { return nil }
        let ordinal = ordinalSuffix(for: Int(round(percentile)))
        return "\(Int(round(percentile)))\(ordinal) percentile"
    }

    func percentileContextText(_ percentileRank: Double?) -> String {
        guard let percentile = percentileRank else { return "many" }
        return String(format: "%.0f%%", percentile)
    }

    func ordinalSuffix(for number: Int) -> String {
        let ones = number % 10
        let tens = (number % 100) / 10

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
}
