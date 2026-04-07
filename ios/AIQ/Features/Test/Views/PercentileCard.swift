import AIQSharedKit
import SwiftUI

/// Percentile ranking display card for test results
struct PercentileCard: View {
    let percentileRank: Double?
    let showAnimation: Bool

    @Environment(\.appTheme) private var theme

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Medal icon
            Image(systemName: "medal.fill")
                .font(.system(size: theme.iconSizes.lg))
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
                    .font(theme.typography.h1)
                    .foregroundStyle(
                        LinearGradient(
                            colors: [theme.colors.statBlue, theme.colors.statPurple],
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
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .opacity(showAnimation ? 1.0 : 0.0)
            }

            // Context message
            Text("percentile.card.description".localized(with: percentileContextText))
                .font(theme.typography.captionMedium)
                .foregroundColor(theme.colors.textTertiary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignSystem.Spacing.lg)
                .padding(.top, DesignSystem.Spacing.xs)
                .opacity(showAnimation ? 1.0 : 0.0)
        }
        .padding(DesignSystem.Spacing.xl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.lg,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: theme.colors.background
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
        .accessibilityElement(children: .combine)
    }

    // MARK: - Computed Properties

    private var percentileFormatted: String? {
        guard let percentile = percentileRank else { return nil }
        let topPercent = Int(round(100 - percentile))
        return "percentile.card.top.format".localized(with: topPercent)
    }

    private var percentileDescription: String? {
        guard let percentile = percentileRank else { return nil }
        return "percentile.card.percentile.format".localized(with: Int(round(percentile)).ordinalString)
    }

    private var percentileContextText: String {
        guard let percentile = percentileRank else { return "percentile.card.many".localized }
        return String(format: "%.0f%%", percentile)
    }
}

#Preview {
    PercentileCard(percentileRank: 84.0, showAnimation: true)
        .padding()
}
