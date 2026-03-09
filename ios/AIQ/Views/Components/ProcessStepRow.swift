import SwiftUI

/// A numbered step component for process flows
struct ProcessStepRow: View {
    let number: Int
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: DesignSystem.Spacing.md) {
            // Number Badge
            ZStack {
                Circle()
                    .fill(ColorPalette.primary)
                    .frame(width: 32, height: 32)

                Text("\(number)")
                    .font(Typography.labelMedium)
                    .foregroundColor(.white)
            }
            .accessibilityHidden(true)

            // Text
            Text(text)
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textPrimary)
                .multilineTextAlignment(.leading)

            Spacer()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Step \(number): \(text)")
    }
}

#Preview {
    VStack(spacing: 16) {
        ProcessStepRow(number: 1, text: "Answer 25 unique questions across different cognitive domains")
        ProcessStepRow(number: 2, text: "Complete the test in one sitting (approximately 20-25 minutes)")
        ProcessStepRow(number: 3, text: "Receive your IQ score and detailed performance breakdown")
    }
    .padding()
}
