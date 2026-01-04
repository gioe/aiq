import SwiftUI

/// A reusable row component for highlighting a feature with an icon and text
struct FeatureHighlightRow: View {
    let icon: String
    let text: String
    let iconColor: Color

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            // Icon
            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.md))
                .foregroundColor(iconColor)
                .frame(width: 32, height: 32)
                .accessibilityHidden(true)

            // Text
            Text(text)
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textPrimary)
                .multilineTextAlignment(.leading)

            Spacer()
        }
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    VStack(spacing: 16) {
        FeatureHighlightRow(
            icon: "chart.line.uptrend.xyaxis",
            text: "Track your cognitive performance over time",
            iconColor: ColorPalette.statBlue
        )
        FeatureHighlightRow(
            icon: "brain.head.profile",
            text: "Fresh questions generated daily",
            iconColor: ColorPalette.statPurple
        )
        FeatureHighlightRow(
            icon: "lock.shield.fill",
            text: "Private and secure results",
            iconColor: ColorPalette.successText
        )
    }
    .padding()
}
