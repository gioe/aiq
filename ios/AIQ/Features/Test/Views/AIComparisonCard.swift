import AIQAPIClientCore
import AIQSharedKit
import SwiftUI

// MARK: - AI Comparison Card

/// Card displayed on the post-test results screen comparing the user's IQ score against
/// AI model benchmarks from the `/v1/benchmark/summary` endpoint.
///
/// Shows three data sections:
/// 1. IQ score comparison columns (user vs. best AI vs. average AI)
/// 2. A visual horizontal gauge placing all three scores on a 70–160 IQ range
/// 3. Per-domain paired accuracy bars (user vs. best AI)
struct AIComparisonCard: View {
    let userIQScore: Int
    let userDomainScores: [String: DomainScore]?
    let benchmarkModels: [Components.Schemas.ModelSummary]
    let showAnimation: Bool

    @State private var showGauge = false
    @Environment(\.appTheme) private var theme
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    // MARK: - Computed Properties

    /// The AI model with the highest mean IQ, used as the "Best AI" reference point.
    private var bestModel: Components.Schemas.ModelSummary? {
        AIComparisonCardLogic.bestModel(from: benchmarkModels)
    }

    /// Mean IQ of the best-performing AI model.
    private var bestAIIQ: Double {
        bestModel?.meanIq ?? 0
    }

    /// Average mean IQ across all benchmark models.
    private var averageAIIQ: Double {
        AIComparisonCardLogic.averageAIIQ(from: benchmarkModels)
    }

    /// Cognitive domains present in both the user's results and the best AI model's domain accuracy.
    private var comparedDomains: [(domain: TestResult.CognitiveDomain, userPct: Double, aiPct: Double)] {
        AIComparisonCardLogic.comparedDomains(userDomainScores: userDomainScores, bestModel: bestModel)
    }

    // MARK: - Body

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
            headerView

            if benchmarkModels.isEmpty {
                emptyStateView
            } else {
                iqComparisonView
                    .padding(.vertical, DesignSystem.Spacing.xs)

                gaugeView

                if !comparedDomains.isEmpty {
                    domainComparisonView
                }
            }
        }
        .padding(DesignSystem.Spacing.lg)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: theme.colors.background
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.AIComparisonCard.container)
        .onAppear {
            if reduceMotion {
                showGauge = true
            } else {
                withAnimation(theme.animations.smooth.delay(0.2)) {
                    showGauge = true
                }
            }
        }
    }

    // MARK: - Header

    private var headerView: some View {
        HStack {
            Image(systemName: "brain.head.profile")
                .font(.system(size: theme.iconSizes.md))
                .foregroundColor(theme.colors.primary)
                .accessibilityHidden(true)

            Text("How You Compare to AI")
                .font(theme.typography.h4)
                .foregroundColor(theme.colors.textPrimary)
        }
        .accessibilityAddTraits(.isHeader)
    }

    // MARK: - IQ Comparison Columns

    private var iqComparisonView: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            iqStatColumn(
                title: "You",
                value: "\(userIQScore)",
                subtitle: nil,
                valueColor: theme.colors.primary
            )

            Divider()
                .frame(height: 50)
                .accessibilityHidden(true)

            iqStatColumn(
                title: "Best AI",
                value: "\(Int(round(bestAIIQ)))",
                subtitle: bestModel?.displayName,
                valueColor: theme.colors.statBlue
            )

            Divider()
                .frame(height: 50)
                .accessibilityHidden(true)

            iqStatColumn(
                title: "Avg AI",
                value: "\(Int(round(averageAIIQ)))",
                subtitle: "\(benchmarkModels.count) models",
                valueColor: theme.colors.statOrange
            )
        }
        .frame(maxWidth: .infinity)
    }

    private func iqStatColumn(
        title: String,
        value: String,
        subtitle: String?,
        valueColor: Color
    ) -> some View {
        VStack(spacing: DesignSystem.Spacing.xs) {
            Text(title)
                .font(theme.typography.captionMedium)
                .foregroundColor(theme.colors.textSecondary)
                .lineLimit(1)

            Text(value)
                .font(theme.typography.h3)
                .foregroundColor(valueColor)
                .lineLimit(1)
                .minimumScaleFactor(0.7)

            if let subtitle {
                Text(subtitle)
                    .font(theme.typography.captionSmall)
                    .foregroundColor(theme.colors.textTertiary)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            subtitle.map { "\(title): \(value), \($0)" } ?? "\(title): \(value)"
        )
    }

    // MARK: - IQ Gauge

    /// Horizontal bar spanning the 70–160 IQ range with markers for the user, best AI, and average AI.
    private var gaugeView: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            Text("IQ Range")
                .font(theme.typography.captionMedium)
                .foregroundColor(theme.colors.textSecondary)
                .accessibilityHidden(true)

            GeometryReader { geometry in
                let markerInset: CGFloat = 9
                let usableWidth = geometry.size.width - markerInset * 2

                ZStack(alignment: .leading) {
                    // Track
                    RoundedRectangle(cornerRadius: 4)
                        .fill(theme.colors.backgroundTertiary)
                        .frame(height: 10)

                    // User marker
                    gaugeMarker(
                        iqScore: Double(userIQScore),
                        color: theme.colors.primary,
                        shape: .circle,
                        barWidth: usableWidth,
                        inset: markerInset
                    )

                    // Average AI marker
                    gaugeMarker(
                        iqScore: averageAIIQ,
                        color: theme.colors.statOrange,
                        shape: .diamond,
                        barWidth: usableWidth,
                        inset: markerInset
                    )

                    // Best AI marker
                    gaugeMarker(
                        iqScore: bestAIIQ,
                        color: theme.colors.statBlue,
                        shape: .diamond,
                        barWidth: usableWidth,
                        inset: markerInset
                    )
                }
            }
            .frame(height: 18)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(gaugeAccessibilityLabel)

            gaugeLegendView
        }
    }

    private enum GaugeMarkerShape {
        case circle
        case diamond
    }

    private func gaugePosition(for iq: Double, barWidth: CGFloat) -> CGFloat {
        AIComparisonCardLogic.gaugePosition(for: iq, barWidth: barWidth)
    }

    @ViewBuilder
    private func gaugeMarker(
        iqScore: Double,
        color: Color,
        shape: GaugeMarkerShape,
        barWidth: CGFloat,
        inset: CGFloat
    ) -> some View {
        let position = showGauge
            ? inset + gaugePosition(for: iqScore, barWidth: barWidth)
            : inset + barWidth / 2
        let markerRadius: CGFloat = shape == .circle ? 9 : 6

        Group {
            switch shape {
            case .circle:
                Circle()
                    .fill(color)
                    .frame(width: 18, height: 18)
                    .overlay(
                        Circle()
                            .stroke(theme.colors.background, lineWidth: 2)
                    )
            case .diamond:
                Rectangle()
                    .fill(color)
                    .frame(width: 12, height: 12)
                    .rotationEffect(.degrees(45))
                    .overlay(
                        Rectangle()
                            .stroke(theme.colors.background, lineWidth: 2)
                            .rotationEffect(.degrees(45))
                    )
            }
        }
        .offset(x: position - markerRadius, y: 0)
    }

    private var gaugeLegendView: some View {
        HStack(spacing: DesignSystem.Spacing.lg) {
            gaugeLegendItem(color: theme.colors.primary, shape: .circle, label: "You")
            gaugeLegendItem(color: theme.colors.statBlue, shape: .diamond, label: "Best AI")
            gaugeLegendItem(color: theme.colors.statOrange, shape: .diamond, label: "Avg AI")

            Spacer()

            HStack(spacing: DesignSystem.Spacing.xs) {
                Text("70")
                    .font(theme.typography.captionSmall)
                    .foregroundColor(theme.colors.textTertiary)
                Text("–")
                    .font(theme.typography.captionSmall)
                    .foregroundColor(theme.colors.textTertiary)
                Text("160")
                    .font(theme.typography.captionSmall)
                    .foregroundColor(theme.colors.textTertiary)
            }
        }
        .accessibilityHidden(true)
    }

    private func gaugeLegendItem(color: Color, shape: GaugeMarkerShape, label: String) -> some View {
        HStack(spacing: DesignSystem.Spacing.xs) {
            Group {
                switch shape {
                case .circle:
                    Circle()
                        .fill(color)
                        .frame(width: 8, height: 8)
                case .diamond:
                    Rectangle()
                        .fill(color)
                        .frame(width: 7, height: 7)
                        .rotationEffect(.degrees(45))
                }
            }

            Text(label)
                .font(theme.typography.captionSmall)
                .foregroundColor(theme.colors.textTertiary)
        }
    }

    private var gaugeAccessibilityLabel: String {
        "IQ comparison gauge from 70 to 160. " +
            "Your score: \(userIQScore). " +
            "Best AI score: \(Int(round(bestAIIQ))). " +
            "Average AI score: \(Int(round(averageAIIQ)))."
    }

    // MARK: - Domain Comparison

    private var domainComparisonView: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.md) {
            domainComparisonHeaderView

            VStack(spacing: DesignSystem.Spacing.md) {
                ForEach(comparedDomains, id: \.domain) { item in
                    DomainComparisonBarView(
                        domain: item.domain,
                        userPct: item.userPct,
                        aiPct: item.aiPct
                    )
                }
            }
        }
    }

    private var domainComparisonHeaderView: some View {
        HStack {
            Text("Domain Accuracy")
                .font(theme.typography.labelMedium)
                .foregroundColor(theme.colors.textPrimary)
                .accessibilityAddTraits(.isHeader)

            Spacer()

            HStack(spacing: DesignSystem.Spacing.md) {
                domainLegendPill(color: theme.colors.primary, label: "You")
                domainLegendPill(color: theme.colors.statBlue, label: "Best AI")
            }
            .accessibilityHidden(true)
        }
    }

    private func domainLegendPill(color: Color, label: String) -> some View {
        HStack(spacing: DesignSystem.Spacing.xs) {
            RoundedRectangle(cornerRadius: 2)
                .fill(color)
                .frame(width: 12, height: 6)
            Text(label)
                .font(theme.typography.captionSmall)
                .foregroundColor(theme.colors.textTertiary)
        }
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            Image(systemName: "cpu")
                .font(.system(size: theme.iconSizes.lg))
                .foregroundColor(theme.colors.textTertiary)
                .accessibilityHidden(true)
            Text("AI benchmark data is not yet available.")
                .font(theme.typography.bodySmall)
                .foregroundColor(theme.colors.textTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DesignSystem.Spacing.xl)
        .accessibilityLabel("AI benchmark data not available")
    }
}

// MARK: - Domain Comparison Bar View

/// A paired horizontal bar row showing user accuracy vs. best AI accuracy for one domain.
private struct DomainComparisonBarView: View {
    let domain: TestResult.CognitiveDomain
    let userPct: Double
    let aiPct: Double

    @State private var animatedUserProgress: Double = 0
    @State private var animatedAIProgress: Double = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    private var userProgress: Double {
        userPct / 100.0
    }

    private var aiProgress: Double {
        aiPct / 100.0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
            Text(domain.displayName)
                .font(theme.typography.captionMedium)
                .foregroundColor(theme.colors.textSecondary)
                .lineLimit(1)

            // User bar
            HStack(spacing: DesignSystem.Spacing.sm) {
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill(theme.colors.backgroundTertiary)
                            .frame(height: 7)

                        RoundedRectangle(cornerRadius: 3)
                            .fill(theme.colors.primary)
                            .frame(width: geometry.size.width * animatedUserProgress, height: 7)
                    }
                }
                .frame(height: 7)

                Text("\(Int(round(userPct)))%")
                    .font(theme.typography.captionSmall)
                    .foregroundColor(theme.colors.textSecondary)
                    .frame(width: 36, alignment: .trailing)
            }

            // AI bar
            HStack(spacing: DesignSystem.Spacing.sm) {
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill(theme.colors.backgroundTertiary)
                            .frame(height: 7)

                        RoundedRectangle(cornerRadius: 3)
                            .fill(theme.colors.statBlue)
                            .frame(width: geometry.size.width * animatedAIProgress, height: 7)
                    }
                }
                .frame(height: 7)

                Text("\(Int(round(aiPct)))%")
                    .font(theme.typography.captionSmall)
                    .foregroundColor(theme.colors.textSecondary)
                    .frame(width: 36, alignment: .trailing)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            "\(domain.displayName): you \(Int(round(userPct))) percent, " +
                "best AI \(Int(round(aiPct))) percent"
        )
        .onAppear {
            if reduceMotion {
                animatedUserProgress = userProgress
                animatedAIProgress = aiProgress
            } else {
                withAnimation(theme.animations.smooth.delay(0.1)) {
                    animatedUserProgress = userProgress
                }
                withAnimation(theme.animations.smooth.delay(0.2)) {
                    animatedAIProgress = aiProgress
                }
            }
        }
    }
}
