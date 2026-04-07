import SwiftUI

/// Reusable card component for displaying icon-labeled content with a title and description
///
/// IconContentCard consolidates the icon+text card pattern used across onboarding screens.
/// It provides:
/// - SF Symbol icon with customizable color alongside a semibold title
/// - Description text below the header row
/// - Consistent card styling with background, corner radius, and shadow
/// - Automatic accessibility support via `.accessibilityElement(children: .combine)`
public struct IconContentCard: View {
    // MARK: - Properties

    /// SF Symbol name for the icon
    public let icon: String

    /// Icon tint color
    public let iconColor: Color

    /// Card title text
    public let title: String

    /// Card description text
    public let description: String

    @Environment(\.appTheme) private var theme

    // MARK: - Initializer

    public init(icon: String, iconColor: Color, title: String, description: String) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.description = description
    }

    // MARK: - Body

    public var body: some View {
        VStack(alignment: .leading, spacing: theme.spacing.md) {
            // Icon and Title
            HStack(spacing: theme.spacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: theme.iconSizes.md))
                    .foregroundColor(iconColor)
                    .accessibilityHidden(true)

                Text(title)
                    .font(theme.typography.bodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(theme.colors.textPrimary)
            }

            // Description
            Text(description)
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.textSecondary)
                .multilineTextAlignment(.leading)
        }
        .padding(theme.spacing.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(theme.colors.backgroundSecondary)
        .cornerRadius(theme.cornerRadius.md)
        .shadowStyle(theme.shadows.sm)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews

#Preview("Light Mode") {
    VStack(spacing: DesignSystem.Spacing.lg) {
        IconContentCard(
            icon: "brain.head.profile",
            iconColor: ColorPalette.statPurple,
            title: "Neuroplasticity Takes Time",
            description: "Cognitive abilities take time to change. Testing every 3 months reveals meaningful growth."
        )

        IconContentCard(
            icon: "chart.xyaxis.line",
            iconColor: ColorPalette.statBlue,
            title: "Meaningful Trends",
            description: "Spacing tests shows real performance trends, not just daily fluctuations."
        )
    }
    .padding()
}
