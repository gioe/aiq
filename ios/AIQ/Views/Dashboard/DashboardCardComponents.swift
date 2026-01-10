import SwiftUI

// MARK: - Stat Card

struct StatCard: View {
    let label: String
    let value: String
    let icon: String
    let color: Color
    var accessibilityId: String?

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [color.opacity(0.2), color.opacity(0.1)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 56, height: 56)

                Image(systemName: icon)
                    .font(.system(size: DesignSystem.IconSize.lg, weight: .semibold))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [color, color.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .accessibilityHidden(true)
            }

            Text(value)
                .font(Typography.statValue)
                .foregroundStyle(
                    LinearGradient(
                        colors: [ColorPalette.textPrimary, ColorPalette.textSecondary],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .accessibilityHidden(true)

            Text(label)
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity)
        .padding(DesignSystem.Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .fill(ColorPalette.backgroundSecondary)
                .shadow(
                    color: Color.black.opacity(0.08),
                    radius: DesignSystem.Shadow.md.radius,
                    x: 0,
                    y: DesignSystem.Shadow.md.y
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .strokeBorder(
                    LinearGradient(
                        colors: [
                            Color.gray.opacity(0.1),
                            Color.gray.opacity(0.05)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1
                )
        )
        .accessibilityLabel("\(label): \(value)")
        .accessibilityIdentifier(accessibilityId ?? "")
    }
}

// MARK: - Test Card Components

struct TestCardHeader: View {
    let dateFormatted: String?

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.sm) {
            ZStack {
                Circle()
                    .fill(ColorPalette.primary.opacity(0.1))
                    .frame(width: 44, height: 44)

                Image(systemName: "chart.line.uptrend.xyaxis")
                    .font(.system(size: DesignSystem.IconSize.md))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .accessibilityHidden(true)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("Latest Result")
                    .font(Typography.h3)
                    .foregroundColor(ColorPalette.textPrimary)

                if let dateStr = dateFormatted {
                    Text(dateStr)
                        .font(Typography.captionMedium)
                        .foregroundColor(ColorPalette.textSecondary)
                }
            }

            Spacer()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Latest Result" + (dateFormatted.map { ", \($0)" } ?? ""))
    }
}

struct TestCardScores: View {
    let result: TestResult

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.xl) {
            iqScore
            Spacer()
            accuracy
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "IQ Score: \(result.iqScore), Accuracy: \(result.accuracyPercentage, specifier: "%.0f") percent"
        )
    }

    private var iqScore: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
            Text("IQ Score")
                .font(Typography.bodySmall)
                .foregroundColor(ColorPalette.textSecondary)

            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("\(result.iqScore)")
                    .font(Typography.displaySmall)
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.8)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )

                if result.iqScore > 100 {
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(ColorPalette.success)
                } else if result.iqScore < 100 {
                    Image(systemName: "arrow.down.right")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(ColorPalette.error)
                }
            }
        }
    }

    private var accuracy: some View {
        VStack(alignment: .trailing, spacing: DesignSystem.Spacing.xs) {
            Text("Accuracy")
                .font(Typography.bodySmall)
                .foregroundColor(ColorPalette.textSecondary)

            Text("\(result.accuracyPercentage, specifier: "%.0f")%")
                .font(Typography.h2)
                .foregroundColor(ColorPalette.textPrimary)
        }
    }
}

struct TestCardProgress: View {
    let result: TestResult

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.sm) {
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(ColorPalette.backgroundTertiary)
                        .frame(height: 8)

                    let progressWidth = geometry.size.width
                        * (CGFloat(result.correctAnswers) / CGFloat(result.totalQuestions))

                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.7)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: progressWidth, height: 8)
                }
            }
            .frame(height: 8)

            Text("\(result.correctAnswers)/\(result.totalQuestions)")
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .fixedSize()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(result.correctAnswers) correct out of \(result.totalQuestions) questions")
    }
}
