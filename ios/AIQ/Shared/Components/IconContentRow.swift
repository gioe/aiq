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
struct IconContentRow: View {
    // MARK: - Properties

    /// SF Symbol name for the icon
    let icon: String

    /// Icon tint color
    let iconColor: Color

    /// Primary row text
    let title: String

    /// Optional secondary text shown below the title
    let description: String?

    // MARK: - Initializer

    init(icon: String, iconColor: Color, title: String, description: String? = nil) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.description = description
    }

    @Environment(\.appTheme) private var theme

    // MARK: - Body

    var body: some View {
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
            title: "Track your cognitive performance over time"
        )

        IconContentRow(
            icon: "checkmark.circle.fill",
            iconColor: ColorPalette.successText,
            title: "End-to-end encryption for all test data"
        )

        IconContentRow(
            icon: "1.circle.fill",
            iconColor: ColorPalette.primary,
            title: "Answer 25 unique questions across different cognitive domains"
        )
    }
    .padding()
}

#Preview("With description") {
    VStack(spacing: DesignSystem.Spacing.lg) {
        IconContentRow(
            icon: "brain.head.profile",
            iconColor: ColorPalette.statPurple,
            title: "AI-Generated Questions",
            description: "Fresh, unique questions created by advanced language models for every test session."
        )

        IconContentRow(
            icon: "lock.shield.fill",
            iconColor: ColorPalette.successText,
            title: "Private & Secure",
            description: "Your data is encrypted and never shared with third parties."
        )
    }
    .padding()
}

#Preview("Dark Mode") {
    VStack(spacing: DesignSystem.Spacing.lg) {
        IconContentRow(
            icon: "chart.line.uptrend.xyaxis",
            iconColor: ColorPalette.statBlue,
            title: "Track your cognitive performance over time"
        )

        IconContentRow(
            icon: "brain.head.profile",
            iconColor: ColorPalette.statPurple,
            title: "AI-Generated Questions",
            description: "Fresh, unique questions created by advanced language models."
        )
    }
    .padding()
    .preferredColorScheme(.dark)
}
