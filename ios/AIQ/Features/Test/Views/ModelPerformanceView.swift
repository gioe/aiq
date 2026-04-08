import AIQSharedKit
import SwiftUI

// MARK: - Model Score Bar View

/// A single horizontal bar representing performance for one AI model.
struct ModelScoreBarView: View {
    let modelName: String
    let score: ModelScore

    @State private var animatedProgress: Double = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    private var percentage: Double {
        score.pct ?? 0
    }

    private var progress: Double {
        percentage / 100.0
    }

    /// Bar color based on accuracy percentage
    private var barColor: Color {
        switch percentage {
        case 80...:
            ColorPalette.performanceExcellent
        case 60 ..< 80:
            ColorPalette.performanceGood
        case 40 ..< 60:
            ColorPalette.performanceAverage
        case 20 ..< 40:
            ColorPalette.performanceBelowAverage
        default:
            ColorPalette.performanceNeedsWork
        }
    }

    /// Display name: use "Unknown Model" for empty/null model names
    private var displayName: String {
        modelName.isEmpty ? "Unknown Model" : modelName
    }

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
            // Model name and score
            HStack {
                Text(displayName)
                    .font(theme.typography.labelMedium)
                    .foregroundColor(theme.colors.textPrimary)
                    .lineLimit(1)

                Spacer()

                HStack(spacing: DesignSystem.Spacing.sm) {
                    Text(score.percentageFormatted)
                        .font(theme.typography.labelMedium)
                        .foregroundColor(theme.colors.textSecondary)
                }
            }

            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(theme.colors.backgroundTertiary)
                        .frame(height: 8)

                    RoundedRectangle(cornerRadius: 4)
                        .fill(barColor)
                        .frame(width: geometry.size.width * animatedProgress, height: 8)
                }
            }
            .frame(height: 8)

            // Correct/Total detail
            Text("\(score.correct)/\(score.total) correct")
                .font(theme.typography.captionSmall)
                .foregroundColor(theme.colors.textTertiary)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(displayName): \(score.percentageFormatted), \(score.correct) of \(score.total) correct")
        .accessibilityValue("\(Int(percentage)) percent")
        .onAppear {
            if reduceMotion {
                animatedProgress = progress
            } else {
                withAnimation(theme.animations.smooth.delay(0.1)) {
                    animatedProgress = progress
                }
            }
        }
    }
}

// MARK: - Vendor Section View

/// Expandable section showing a vendor's aggregate score with drill-down to individual models.
struct VendorSectionView: View {
    let vendor: TestResult.ModelVendor
    let models: [(model: String, score: ModelScore)]
    let aggregate: ModelScore
    let showAnimation: Bool

    @State private var isExpanded = false
    @State private var animatedProgress: Double = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    private var percentage: Double {
        aggregate.pct ?? 0
    }

    private var progress: Double {
        percentage / 100.0
    }

    /// Bar color based on accuracy percentage
    private var barColor: Color {
        switch percentage {
        case 80...:
            ColorPalette.performanceExcellent
        case 60 ..< 80:
            ColorPalette.performanceGood
        case 40 ..< 60:
            ColorPalette.performanceAverage
        case 20 ..< 40:
            ColorPalette.performanceBelowAverage
        default:
            ColorPalette.performanceNeedsWork
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            // Vendor header (tappable to expand)
            Button {
                withAnimation(theme.animations.standard) {
                    isExpanded.toggle()
                }
            } label: {
                VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
                    HStack {
                        Text(vendor.displayName)
                            .font(theme.typography.labelMedium)
                            .fontWeight(.semibold)
                            .foregroundColor(theme.colors.textPrimary)

                        if models.count > 1 {
                            Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                                .font(.system(size: 10))
                                .foregroundColor(theme.colors.textTertiary)
                        }

                        Spacer()

                        Text(aggregate.percentageFormatted)
                            .font(theme.typography.labelMedium)
                            .foregroundColor(theme.colors.textSecondary)
                    }

                    // Aggregate progress bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(theme.colors.backgroundTertiary)
                                .frame(height: 8)

                            RoundedRectangle(cornerRadius: 4)
                                .fill(barColor)
                                .frame(width: geometry.size.width * animatedProgress, height: 8)
                        }
                    }
                    .frame(height: 8)

                    // Correct/Total
                    Text("\(aggregate.correct)/\(aggregate.total) correct")
                        .font(theme.typography.captionSmall)
                        .foregroundColor(theme.colors.textTertiary)
                }
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(
                "\(vendor.displayName): \(aggregate.percentageFormatted), " +
                    "\(aggregate.correct) of \(aggregate.total) correct"
            )
            .accessibilityValue("\(Int(percentage)) percent")
            .accessibilityHint(
                models.count > 1
                    ? "Double tap to \(isExpanded ? "collapse" : "expand") individual models"
                    : ""
            )

            // Expanded model details
            if isExpanded && models.count > 1 {
                VStack(spacing: DesignSystem.Spacing.md) {
                    ForEach(models, id: \.model) { item in
                        ModelScoreBarView(
                            modelName: item.model,
                            score: item.score
                        )
                    }
                }
                .padding(.leading, DesignSystem.Spacing.lg)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .onAppear {
            if reduceMotion {
                animatedProgress = progress
            } else {
                withAnimation(theme.animations.smooth.delay(0.1)) {
                    animatedProgress = progress
                }
            }
        }
    }
}

// MARK: - Model Performance Breakdown View

/// Container view displaying AI model performance grouped by vendor.
struct ModelPerformanceBreakdownView: View {
    let modelScores: [String: ModelScore]?
    let showAnimation: Bool

    @Environment(\.appTheme) private var theme

    /// Vendor-grouped scores computed from raw model scores
    private var vendorGroups: [(
        vendor: TestResult.ModelVendor,
        models: [(model: String, score: ModelScore)],
        aggregate: ModelScore
    )] {
        guard let scores = modelScores, !scores.isEmpty else { return [] }

        var groups: [TestResult.ModelVendor: [(model: String, score: ModelScore)]] = [:]
        for (model, score) in scores {
            let vendor = TestResult.ModelVendor.from(modelName: model)
            groups[vendor, default: []].append((model: model, score: score))
        }

        return groups.map { vendor, models in
            let sortedModels = models.sorted { $0.model < $1.model }
            let totalCorrect = models.reduce(0) { $0 + $1.score.correct }
            let totalQuestions = models.reduce(0) { $0 + $1.score.total }
            let pct = totalQuestions > 0 ? (Double(totalCorrect) / Double(totalQuestions)) * 100.0 : nil
            let aggregate = ModelScore(correct: totalCorrect, total: totalQuestions, pct: pct)
            return (vendor: vendor, models: sortedModels, aggregate: aggregate)
        }
        .sorted { ($0.aggregate.pct ?? 0) > ($1.aggregate.pct ?? 0) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
            // Section header
            HStack {
                Image(systemName: "cpu")
                    .font(.system(size: theme.iconSizes.md))
                    .foregroundColor(theme.colors.primary)
                    .accessibilityHidden(true)

                Text("Model Performance")
                    .font(theme.typography.h4)
                    .foregroundColor(theme.colors.textPrimary)
            }
            .accessibilityAddTraits(.isHeader)

            if !vendorGroups.isEmpty {
                VStack(spacing: DesignSystem.Spacing.lg) {
                    ForEach(vendorGroups, id: \.vendor) { group in
                        VendorSectionView(
                            vendor: group.vendor,
                            models: group.models,
                            aggregate: group.aggregate,
                            showAnimation: showAnimation
                        )
                    }
                }
            } else {
                emptyStateView
            }
        }
        .padding(DesignSystem.Spacing.lg)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: theme.colors.background
        )
        .opacity(showAnimation ? 1.0 : 0.0)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.ModelPerformanceView.container)
    }

    private var emptyStateView: some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            Image(systemName: "cpu")
                .font(.system(size: theme.iconSizes.lg))
                .foregroundColor(theme.colors.textTertiary)
                .accessibilityHidden(true)

            Text("Model performance data not available for this test.")
                .font(theme.typography.bodySmall)
                .foregroundColor(theme.colors.textTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DesignSystem.Spacing.xl)
        .accessibilityLabel("Model performance data not available")
    }
}

// MARK: - Previews

#if DebugBuild

    #Preview("Multiple Vendors") {
        ScrollView {
            ModelPerformanceBreakdownView(
                modelScores: [
                    "gpt-4o": ModelScore(correct: 5, total: 7, pct: 71.4),
                    "gpt-4o-mini": ModelScore(correct: 3, total: 4, pct: 75.0),
                    "claude-3-opus": ModelScore(correct: 3, total: 4, pct: 75.0),
                    "claude-3-5-sonnet": ModelScore(correct: 4, total: 5, pct: 80.0),
                    "gemini-1.5-pro": ModelScore(correct: 2, total: 3, pct: 66.7)
                ],
                showAnimation: true
            )
            .padding()
        }
        .background(DefaultTheme().colors.backgroundGrouped)
    }

    #Preview("Single Vendor") {
        ScrollView {
            ModelPerformanceBreakdownView(
                modelScores: [
                    "gpt-4o": ModelScore(correct: 8, total: 10, pct: 80.0)
                ],
                showAnimation: true
            )
            .padding()
        }
        .background(DefaultTheme().colors.backgroundGrouped)
    }

    #Preview("No Data") {
        ScrollView {
            ModelPerformanceBreakdownView(
                modelScores: nil,
                showAnimation: true
            )
            .padding()
        }
        .background(DefaultTheme().colors.backgroundGrouped)
    }

#endif
