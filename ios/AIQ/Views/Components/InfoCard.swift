import SwiftUI

/// Reusable card component for displaying informational content with an icon
///
/// InfoCard provides a consistent layout for displaying information with:
/// - SF Symbol icon with customizable color
/// - Title and description text
/// - Automatic accessibility support
///
/// This component is used across authentication screens (WelcomeView, RegistrationView)
/// to highlight features, benefits, and key information.
struct InfoCard: View {
    // MARK: - Properties

    /// SF Symbol name for the icon
    let icon: String

    /// Card title text
    let title: String

    /// Card description text
    let description: String

    /// Icon color
    let color: Color

    // MARK: - Body

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            // Icon
            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.lg))
                .foregroundColor(color)
                .frame(width: 50, height: 50)
                .accessibilityHidden(true)

            // Text Content
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
                Text(title)
                    .font(Typography.bodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(ColorPalette.textPrimary)

                Text(description)
                    .font(Typography.bodySmall)
                    .foregroundColor(ColorPalette.textSecondary)
            }

            Spacer()
        }
        .padding(DesignSystem.Spacing.md)
        .background(ColorPalette.backgroundSecondary)
        .cornerRadius(DesignSystem.CornerRadius.md)
        .shadow(
            color: DesignSystem.Shadow.sm.color,
            radius: DesignSystem.Shadow.sm.radius,
            x: DesignSystem.Shadow.sm.x,
            y: DesignSystem.Shadow.sm.y
        )
        .accessibilityLabel("\(title). \(description)")
    }
}

// MARK: - Previews

#Preview("Single Card") {
    InfoCard(
        icon: "puzzlepiece.extension.fill",
        title: "Fresh AI Challenges",
        description: "New questions every test",
        color: ColorPalette.statBlue
    )
    .padding()
}

#Preview("Multiple Cards") {
    VStack(spacing: DesignSystem.Spacing.md) {
        InfoCard(
            icon: "puzzlepiece.extension.fill",
            title: "Fresh AI Challenges",
            description: "New questions every test",
            color: ColorPalette.statBlue
        )

        InfoCard(
            icon: "chart.line.uptrend.xyaxis",
            title: "Track Your Progress",
            description: "Watch your IQ improve over time",
            color: ColorPalette.statGreen
        )

        InfoCard(
            icon: "lock.shield.fill",
            title: "Secure & Private",
            description: "Your data is encrypted and never shared",
            color: ColorPalette.statGreen
        )

        InfoCard(
            icon: "chart.xyaxis.line",
            title: "Visual Analytics",
            description: "Beautiful charts tracking your cognitive growth",
            color: ColorPalette.statOrange
        )
    }
    .padding()
}

#Preview("Different Colors") {
    ScrollView {
        VStack(spacing: DesignSystem.Spacing.md) {
            InfoCard(
                icon: "star.fill",
                title: "Primary Color",
                description: "Using primary color from palette",
                color: ColorPalette.primary
            )

            InfoCard(
                icon: "heart.fill",
                title: "Error Color",
                description: "Using error color from palette",
                color: ColorPalette.error
            )

            InfoCard(
                icon: "checkmark.circle.fill",
                title: "Success Color",
                description: "Using success color from palette",
                color: ColorPalette.success
            )

            InfoCard(
                icon: "info.circle.fill",
                title: "Info Color",
                description: "Using info color from palette",
                color: ColorPalette.info
            )
        }
        .padding()
    }
}

#Preview("Dark Mode") {
    VStack(spacing: DesignSystem.Spacing.md) {
        InfoCard(
            icon: "puzzlepiece.extension.fill",
            title: "Fresh AI Challenges",
            description: "New questions every test",
            color: ColorPalette.statBlue
        )

        InfoCard(
            icon: "chart.line.uptrend.xyaxis",
            title: "Track Your Progress",
            description: "Watch your IQ improve over time",
            color: ColorPalette.statGreen
        )
    }
    .padding()
    .preferredColorScheme(.dark)
}
