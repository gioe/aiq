import SwiftUI

/// Percentile ranking display card for test results
struct PercentileCard: View {
    let percentileRank: Double?
    let showAnimation: Bool

    var body: some View {
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
            if let percentileText = percentileFormatted {
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
            if let description = percentileDescription {
                Text(description)
                    .font(Typography.bodyMedium)
                    .foregroundColor(ColorPalette.textSecondary)
                    .opacity(showAnimation ? 1.0 : 0.0)
            }

            // Context message
            Text("You scored higher than \(percentileContextText) of test takers")
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

    // MARK: - Computed Properties

    private var percentileFormatted: String? {
        guard let percentile = percentileRank else { return nil }
        let topPercent = Int(round(100 - percentile))
        return "Top \(topPercent)%"
    }

    private var percentileDescription: String? {
        guard let percentile = percentileRank else { return nil }
        return "\(Int(round(percentile)).ordinalString) percentile"
    }

    private var percentileContextText: String {
        guard let percentile = percentileRank else { return "many" }
        return String(format: "%.0f%%", percentile)
    }
}

#Preview {
    PercentileCard(percentileRank: 84.0, showAnimation: true)
        .padding()
}
