import SwiftUI

/// A card component with icon and explanation for displaying rationale
struct RationaleCard: View {
    let icon: String
    let title: String
    let description: String
    let iconColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.md) {
            // Icon and Title
            HStack(spacing: DesignSystem.Spacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: DesignSystem.IconSize.md))
                    .foregroundColor(iconColor)
                    .accessibilityHidden(true)

                Text(title)
                    .font(Typography.bodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(ColorPalette.textPrimary)
            }

            // Description
            Text(description)
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .multilineTextAlignment(.leading)
        }
        .padding(DesignSystem.Spacing.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(ColorPalette.backgroundSecondary)
        .cornerRadius(DesignSystem.CornerRadius.md)
        .shadow(
            color: DesignSystem.Shadow.sm.color,
            radius: DesignSystem.Shadow.sm.radius,
            x: DesignSystem.Shadow.sm.x,
            y: DesignSystem.Shadow.sm.y
        )
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    VStack(spacing: 16) {
        RationaleCard(
            icon: "brain.head.profile",
            title: "Neuroplasticity Takes Time",
            // swiftlint:disable:next line_length
            description: "Your cognitive abilities don't change overnight. Testing every 3 months gives your brain time to adapt and grow.",
            iconColor: ColorPalette.statPurple
        )
        RationaleCard(
            icon: "chart.xyaxis.line",
            title: "Meaningful Trends",
            // swiftlint:disable:next line_length
            description: "Spacing tests allows you to see real trends in your performance, not just daily fluctuations.",
            iconColor: ColorPalette.statBlue
        )
    }
    .padding()
}
