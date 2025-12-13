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

    private var barColor: Color {
        if isStrongest {
            ColorPalette.success
        } else if isWeakest {
            ColorPalette.warning
        } else {
            ColorPalette.primary
        }
    }

    private var accessibilityLabel: String {
        var label = "\(domain.displayName): \(score.percentageFormatted)"
        label += ", \(score.correct) of \(score.total) correct"
        if isStrongest {
            label += ", strongest domain"
        } else if isWeakest {
            label += ", weakest domain"
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

                Text(score.percentageFormatted)
                    .font(Typography.labelMedium)
                    .foregroundColor(ColorPalette.textSecondary)
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

            // Correct/Total detail
            Text("\(score.correct)/\(score.total) correct")
                .font(Typography.captionSmall)
                .foregroundColor(ColorPalette.textTertiary)
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

    /// Computed property to get sorted domain scores with metadata
    private var sortedScores: [(domain: TestResult.CognitiveDomain, score: DomainScore)]? {
        guard let scores = domainScores else { return nil }

        return TestResult.CognitiveDomain.allCases.compactMap { domain in
            guard let score = scores[domain.rawValue] else { return nil }
            return (domain, score)
        }
    }

    private var strongestDomain: TestResult.CognitiveDomain? {
        sortedScores?
            .filter { $0.score.pct != nil && $0.score.total > 0 }
            .max { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }?
            .domain
    }

    private var weakestDomain: TestResult.CognitiveDomain? {
        sortedScores?
            .filter { $0.score.pct != nil && $0.score.total > 0 }
            .min { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }?
            .domain
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

    private var legendView: some View {
        HStack(spacing: DesignSystem.Spacing.lg) {
            legendItem(icon: "star.fill", color: ColorPalette.success, text: "Strongest")
            legendItem(icon: "arrow.up.circle", color: ColorPalette.warning, text: "Room to grow")
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

#Preview("All Domains") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [
                "pattern": DomainScore(correct: 4, total: 4, pct: 100.0),
                "logic": DomainScore(correct: 3, total: 4, pct: 75.0),
                "spatial": DomainScore(correct: 2, total: 3, pct: 66.7),
                "math": DomainScore(correct: 3, total: 4, pct: 75.0),
                "verbal": DomainScore(correct: 2, total: 3, pct: 66.7),
                "memory": DomainScore(correct: 1, total: 2, pct: 50.0)
            ],
            showAnimation: true
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("Mixed Performance") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [
                "pattern": DomainScore(correct: 1, total: 4, pct: 25.0),
                "logic": DomainScore(correct: 4, total: 4, pct: 100.0),
                "spatial": DomainScore(correct: 0, total: 3, pct: 0.0),
                "math": DomainScore(correct: 2, total: 4, pct: 50.0),
                "verbal": DomainScore(correct: 3, total: 3, pct: 100.0),
                "memory": DomainScore(correct: 2, total: 2, pct: 100.0)
            ],
            showAnimation: true
        )
        .padding()
    }
    .background(ColorPalette.backgroundGrouped)
}

#Preview("Partial Domains") {
    ScrollView {
        DomainScoresBreakdownView(
            domainScores: [
                "pattern": DomainScore(correct: 3, total: 4, pct: 75.0),
                "logic": DomainScore(correct: 2, total: 3, pct: 66.7),
                "math": DomainScore(correct: 4, total: 4, pct: 100.0)
            ],
            showAnimation: true
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

#Preview("Single Domain Bar") {
    DomainScoreBarView(
        domain: .pattern,
        score: DomainScore(correct: 3, total: 4, pct: 75.0),
        isStrongest: false,
        isWeakest: false
    )
    .padding()
}

#Preview("Strongest Domain Bar") {
    DomainScoreBarView(
        domain: .logic,
        score: DomainScore(correct: 4, total: 4, pct: 100.0),
        isStrongest: true,
        isWeakest: false
    )
    .padding()
}

#Preview("Weakest Domain Bar") {
    DomainScoreBarView(
        domain: .memory,
        score: DomainScore(correct: 1, total: 4, pct: 25.0),
        isStrongest: false,
        isWeakest: true
    )
    .padding()
}
