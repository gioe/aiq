import SwiftUI

// MARK: - Domain Score Bar View

/// A single horizontal bar representing performance in one cognitive domain.
struct DomainScoreBarView: View {
    let domain: TestResult.CognitiveDomain
    let score: DomainScore
    let isStrongest: Bool
    let isWeakest: Bool

    @State private var animatedProgress: Double = 0

    private var percentage: Double {
        score.pct ?? 0
    }

    private var progress: Double {
        percentage / 100.0
    }

    /// Bar color based on percentile performance level, falling back to strongest/weakest indicators
    private var barColor: Color {
        // Use performance level color if percentile is available
        if let level = score.performanceLevel {
            return level.color
        }
        // Fall back to strongest/weakest indicators
        if isStrongest {
            return ColorPalette.success
        } else if isWeakest {
            return ColorPalette.warning
        }
        return ColorPalette.primary
    }

    private var accessibilityLabel: String {
        var label = "\(domain.displayName): \(score.percentageFormatted)"
        if let percentileDesc = score.percentileDescription {
            label += ", \(percentileDesc)"
        }
        label += ", \(score.correct) of \(score.total) correct"
        if isStrongest {
            label += ", strongest domain"
        } else if isWeakest {
            label += ", weakest domain"
        }
        if let level = score.performanceLevel {
            label += ", \(level.displayName) performance"
        }
        return label
    }

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
            // Domain name and score
            HStack {
                HStack(spacing: DesignSystem.Spacing.xs) {
                    Text(domain.displayName)
                        .font(Typography.labelMedium)
                        .foregroundColor(ColorPalette.textPrimary)

                    if isStrongest {
                        Image(systemName: "star.fill")
                            .font(.system(size: 10))
                            .foregroundColor(ColorPalette.success)
                            .accessibilityHidden(true)
                    } else if isWeakest {
                        Image(systemName: "arrow.up.circle")
                            .font(.system(size: 10))
                            .foregroundColor(ColorPalette.warning)
                            .accessibilityHidden(true)
                    }
                }

                Spacer()

                // Score display: percentage and percentile
                HStack(spacing: DesignSystem.Spacing.sm) {
                    Text(score.percentageFormatted)
                        .font(Typography.labelMedium)
                        .foregroundColor(ColorPalette.textSecondary)

                    // Show percentile badge if available
                    if let percentileFormatted = score.percentileFormatted {
                        Text(percentileFormatted)
                            .font(Typography.captionSmall)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                            .padding(.horizontal, DesignSystem.Spacing.xs)
                            .padding(.vertical, 2)
                            .background(barColor)
                            .cornerRadius(4)
                    }
                }
            }

            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    // Background track
                    RoundedRectangle(cornerRadius: 4)
                        .fill(ColorPalette.backgroundTertiary)
                        .frame(height: 8)

                    // Filled progress
                    RoundedRectangle(cornerRadius: 4)
                        .fill(barColor)
                        .frame(width: geometry.size.width * animatedProgress, height: 8)
                }
            }
            .frame(height: 8)

            // Correct/Total detail with percentile description
            HStack {
                Text("\(score.correct)/\(score.total) correct")
                    .font(Typography.captionSmall)
                    .foregroundColor(ColorPalette.textTertiary)

                if let percentileDesc = score.percentileDescription {
                    Text("•")
                        .font(Typography.captionSmall)
                        .foregroundColor(ColorPalette.textTertiary)

                    Text(percentileDesc)
                        .font(Typography.captionSmall)
                        .foregroundColor(barColor)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityValue("\(Int(percentage)) percent")
        .onAppear {
            withAnimation(DesignSystem.Animation.smooth.delay(0.1)) {
                animatedProgress = progress
            }
        }
    }
}

// MARK: - Domain Scores Breakdown View

/// Container view displaying all domain scores in a vertical list.
struct DomainScoresBreakdownView: View {
    let domainScores: [String: DomainScore]?
    let showAnimation: Bool
    /// Strongest domain name from API (when population stats available)
    let strongestDomainFromAPI: String?
    /// Weakest domain name from API (when population stats available)
    let weakestDomainFromAPI: String?

    init(
        domainScores: [String: DomainScore]?,
        showAnimation: Bool,
        strongestDomain: String? = nil,
        weakestDomain: String? = nil
    ) {
        self.domainScores = domainScores
        self.showAnimation = showAnimation
        strongestDomainFromAPI = strongestDomain
        weakestDomainFromAPI = weakestDomain
    }

    /// Computed property to get sorted domain scores with metadata
    private var sortedScores: [(domain: TestResult.CognitiveDomain, score: DomainScore)]? {
        guard let scores = domainScores else { return nil }

        return TestResult.CognitiveDomain.allCases.compactMap { domain in
            guard let score = scores[domain.rawValue] else { return nil }
            return (domain, score)
        }
    }

    /// Use API-provided strongest domain or fall back to local calculation
    private var strongestDomain: TestResult.CognitiveDomain? {
        if let apiDomain = strongestDomainFromAPI {
            return TestResult.CognitiveDomain(rawValue: apiDomain)
        }
        return sortedScores?
            .filter { $0.score.pct != nil && $0.score.total > 0 }
            .max { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }?
            .domain
    }

    /// Use API-provided weakest domain or fall back to local calculation
    private var weakestDomain: TestResult.CognitiveDomain? {
        if let apiDomain = weakestDomainFromAPI {
            return TestResult.CognitiveDomain(rawValue: apiDomain)
        }
        return sortedScores?
            .filter { $0.score.pct != nil && $0.score.total > 0 }
            .min { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }?
            .domain
    }

    /// Get the strongest domain score for messaging
    private var strongestDomainScore: DomainScore? {
        guard let domain = strongestDomain else { return nil }
        return domainScores?[domain.rawValue]
    }

    /// Get the weakest domain score for messaging
    private var weakestDomainScore: DomainScore? {
        guard let domain = weakestDomain else { return nil }
        return domainScores?[domain.rawValue]
    }

    /// Check if any domain has percentile data available
    private var hasPercentileData: Bool {
        sortedScores?.contains { $0.score.percentile != nil } ?? false
    }

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
            // Section header
            HStack {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: DesignSystem.IconSize.md))
                    .foregroundColor(ColorPalette.primary)
                    .accessibilityHidden(true)

                Text("Cognitive Domains")
                    .font(Typography.h4)
                    .foregroundColor(ColorPalette.textPrimary)
            }
            .accessibilityAddTraits(.isHeader)

            if let scores = sortedScores, !scores.isEmpty {
                // Strongest/Weakest domain messaging (when percentile data available)
                if hasPercentileData {
                    domainHighlightsView
                }

                VStack(spacing: DesignSystem.Spacing.lg) {
                    ForEach(scores, id: \.domain) { item in
                        DomainScoreBarView(
                            domain: item.domain,
                            score: item.score,
                            isStrongest: item.domain == strongestDomain,
                            isWeakest: item.domain == weakestDomain && strongestDomain != weakestDomain
                        )
                    }
                }

                // Legend
                legendView
            } else {
                // Empty state
                emptyStateView
            }
        }
        .padding(DesignSystem.Spacing.lg)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: ColorPalette.background
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .offset(y: showAnimation ? 0 : 20)
    }

    // MARK: - Domain Highlights View

    @ViewBuilder
    private var domainHighlightsView: some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            // Strongest domain highlight
            if let domain = strongestDomain, let score = strongestDomainScore {
                domainHighlightRow(DomainHighlightConfig(
                    icon: "star.fill",
                    iconColor: ColorPalette.success,
                    title: "Strongest:",
                    domain: domain.displayName,
                    percentile: score.percentileFormatted,
                    performanceLevel: score.performanceLevel
                ))
            }

            // Weakest domain highlight (only if different from strongest)
            if let domain = weakestDomain, let score = weakestDomainScore, weakestDomain != strongestDomain {
                domainHighlightRow(DomainHighlightConfig(
                    icon: "arrow.up.circle",
                    iconColor: ColorPalette.warning,
                    title: "Room to grow:",
                    domain: domain.displayName,
                    percentile: score.percentileFormatted,
                    performanceLevel: score.performanceLevel
                ))
            }
        }
        .padding(DesignSystem.Spacing.md)
        .background(ColorPalette.backgroundSecondary)
        .cornerRadius(DesignSystem.CornerRadius.sm)
    }

    /// Configuration for domain highlight row
    private struct DomainHighlightConfig {
        let icon: String
        let iconColor: Color
        let title: String
        let domain: String
        let percentile: String?
        let performanceLevel: PerformanceLevel?
    }

    private func domainHighlightRow(_ config: DomainHighlightConfig) -> some View {
        HStack(spacing: DesignSystem.Spacing.sm) {
            Image(systemName: config.icon)
                .font(.system(size: 12))
                .foregroundColor(config.iconColor)
                .accessibilityHidden(true)

            Text(config.title)
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textSecondary)

            Text(config.domain)
                .font(Typography.captionMedium)
                .fontWeight(.semibold)
                .foregroundColor(ColorPalette.textPrimary)

            Spacer()

            if let percentile = config.percentile {
                Text(percentile)
                    .font(Typography.captionSmall)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.horizontal, DesignSystem.Spacing.xs)
                    .padding(.vertical, 2)
                    .background(config.performanceLevel?.color ?? ColorPalette.primary)
                    .cornerRadius(4)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var legendView: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
            HStack(spacing: DesignSystem.Spacing.lg) {
                legendItem(icon: "star.fill", color: ColorPalette.success, text: "Strongest")
                legendItem(icon: "arrow.up.circle", color: ColorPalette.warning, text: "Room to grow")
            }

            // Performance level legend (when percentile data available)
            if hasPercentileData {
                let levels: [PerformanceLevel] = [.excellent, .good, .average, .belowAverage, .needsWork]
                HStack(spacing: DesignSystem.Spacing.sm) {
                    Text("Percentile:")
                        .font(Typography.captionSmall)
                        .foregroundColor(ColorPalette.textTertiary)

                    ForEach(levels, id: \.displayName) { level in
                        Circle()
                            .fill(level.color)
                            .frame(width: 8, height: 8)
                    }

                    Text("90+ → <25")
                        .font(Typography.captionSmall)
                        .foregroundColor(ColorPalette.textTertiary)
                }
            }
        }
        .font(Typography.captionSmall)
        .foregroundColor(ColorPalette.textTertiary)
        .padding(.top, DesignSystem.Spacing.sm)
        .accessibilityHidden(true) // Legend is supplementary
    }

    private func legendItem(icon: String, color: Color, text: String) -> some View {
        HStack(spacing: DesignSystem.Spacing.xs) {
            Image(systemName: icon)
                .font(.system(size: 8))
                .foregroundColor(color)
            Text(text)
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            Image(systemName: "chart.bar.xaxis")
                .font(.system(size: DesignSystem.IconSize.lg))
                .foregroundColor(ColorPalette.textTertiary)
                .accessibilityHidden(true)

            Text("Domain breakdown not available")
                .font(Typography.bodySmall)
                .foregroundColor(ColorPalette.textTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DesignSystem.Spacing.xl)
        .accessibilityLabel("Domain breakdown is not available for this test result")
    }
}

// MARK: - Previews

#Preview("All Domains with Percentiles") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [
                "pattern": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 95.2),
                "logic": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 71.1),
                "spatial": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 52.3),
                "math": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 68.5),
                "verbal": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 45.8),
                "memory": DomainScore(correct: 1, total: 2, pct: 50.0, percentile: 30.2)
            ],
            showAnimation: true,
            strongestDomain: "pattern",
            weakestDomain: "memory"
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("All Domains - No Percentiles") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [
                "pattern": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: nil),
                "logic": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil),
                "spatial": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: nil),
                "math": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil),
                "verbal": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: nil),
                "memory": DomainScore(correct: 1, total: 2, pct: 50.0, percentile: nil)
            ],
            showAnimation: true
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("Mixed Performance Levels") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [
                "pattern": DomainScore(correct: 1, total: 4, pct: 25.0, percentile: 12.5),
                "logic": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 98.0),
                "spatial": DomainScore(correct: 0, total: 3, pct: 0.0, percentile: 2.0),
                "math": DomainScore(correct: 2, total: 4, pct: 50.0, percentile: 35.0),
                "verbal": DomainScore(correct: 3, total: 3, pct: 100.0, percentile: 92.5),
                "memory": DomainScore(correct: 2, total: 2, pct: 100.0, percentile: 85.0)
            ],
            showAnimation: true,
            strongestDomain: "logic",
            weakestDomain: "spatial"
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("Partial Domains") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [
                "pattern": DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 71.5),
                "logic": DomainScore(correct: 2, total: 3, pct: 66.7, percentile: 55.0),
                "math": DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 94.0)
            ],
            showAnimation: true,
            strongestDomain: "math",
            weakestDomain: "logic"
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("No Domain Scores") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: nil,
            showAnimation: true
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("Empty Dictionary") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [:],
            showAnimation: true
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("Single Domain Bar - With Percentile") {
    DomainScoreBarView(
        domain: .pattern,
        score: DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 71.1),
        isStrongest: false,
        isWeakest: false
    )
    .padding()
}

#Preview("Single Domain Bar - No Percentile") {
    DomainScoreBarView(
        domain: .pattern,
        score: DomainScore(correct: 3, total: 4, pct: 75.0, percentile: nil),
        isStrongest: false,
        isWeakest: false
    )
    .padding()
}

#Preview("Strongest Domain Bar - Excellent") {
    DomainScoreBarView(
        domain: .logic,
        score: DomainScore(correct: 4, total: 4, pct: 100.0, percentile: 95.0),
        isStrongest: true,
        isWeakest: false
    )
    .padding()
}

#Preview("Weakest Domain Bar - Needs Work") {
    DomainScoreBarView(
        domain: .memory,
        score: DomainScore(correct: 1, total: 4, pct: 25.0, percentile: 15.0),
        isStrongest: false,
        isWeakest: true
    )
    .padding()
}

#Preview("Domain Bar - Average Performance") {
    DomainScoreBarView(
        domain: .spatial,
        score: DomainScore(correct: 2, total: 4, pct: 50.0, percentile: 55.0),
        isStrongest: false,
        isWeakest: false
    )
    .padding()
}

#Preview("Domain Bar - Good Performance") {
    DomainScoreBarView(
        domain: .verbal,
        score: DomainScore(correct: 3, total: 4, pct: 75.0, percentile: 80.0),
        isStrongest: false,
        isWeakest: false
    )
    .padding()
}
