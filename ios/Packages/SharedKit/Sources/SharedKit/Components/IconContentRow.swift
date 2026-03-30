import SwiftUI

/// Reusable flat row component for displaying icon-labeled content with an optional description
///
/// IconContentRow consolidates the icon+text row pattern used across onboarding screens.
/// It provides:
/// - SF Symbol icon with customizable color, fixed to a 32×32 frame for alignment
/// - Primary title text with an optional secondary description below it
/// - Automatic accessibility support via `.accessibilityElement(children: .combine)`
///
/// Pass a `description` when additional context is needed below the title.
/// Omit it (or pass `nil`) for a simpler single-line row.
public struct IconContentRow: View {
    // MARK: - Properties

    /// SF Symbol name for the icon
    public let icon: String

    /// Icon tint color
    public let iconColor: Color

    /// Primary row text
    public let title: String

    /// Optional secondary text shown below the title
    public let description: String?

    // MARK: - Initializer

    public init(icon: String, iconColor: Color, title: String, description: String? = nil) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.description = description
    }

    @Environment(\.appTheme) private var theme

    // MARK: - Body

    public var body: some View {
        HStack(spacing: theme.spacing.md) {
            Image(systemName: icon)
                .font(.system(size: theme.iconSizes.md))
                .foregroundColor(iconColor)
                .frame(width: 32, height: 32)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: theme.spacing.xs) {
                Text(title)
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textPrimary)
                    .multilineTextAlignment(.leading)

                if let description {
                    Text(description)
                        .font(theme.typography.bodySmall)
                        .foregroundColor(theme.colors.textSecondary)
                        .multilineTextAlignment(.leading)
                }
            }

            Spacer()
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews

#Preview("Title only") {
    VStack(spacing: DesignSystem.Spacing.lg) {
        IconContentRow(
            icon: "chart.line.uptrend.xyaxis",
            iconColor: ColorPalette.statBlue,
            title: "Track your performance over time"
        )

        IconContentRow(
            icon: "checkmark.circle.fill",
            iconColor: ColorPalette.successText,
            title: "End-to-end encryption for all data"
        )
    }
    .padding()
}
