import SwiftUI

/// A row component with checkmark and privacy feature text
struct PrivacyFeatureRow: View {
    let text: String

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            // Checkmark Icon
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: DesignSystem.IconSize.md))
                .foregroundColor(ColorPalette.successText)
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
        PrivacyFeatureRow(text: "End-to-end encryption for all test data")
        PrivacyFeatureRow(text: "No sale of personal information to third parties")
        PrivacyFeatureRow(text: "GDPR and CCPA compliant data handling")
        PrivacyFeatureRow(text: "Your results are private and only visible to you")
    }
    .padding()
}
