import AIQAPIClientCore
import AIQSharedKit
import SwiftUI

/// Card component displaying a group summary in the groups list
struct GroupCardView: View {
    let group: Components.Schemas.GroupResponse
    @Environment(\.appTheme) private var theme

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            // Group icon
            Image(systemName: "person.3.fill")
                .font(.title2)
                .foregroundStyle(theme.colors.primary)
                .frame(width: 44, height: 44)
                .background(theme.colors.primary.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.sm))

            // Group info
            VStack(alignment: .leading, spacing: 4) {
                Text(group.name)
                    .font(theme.typography.bodyMedium)
                    .foregroundStyle(theme.colors.textPrimary)
                    .lineLimit(1)

                Text("\(group.memberCount) / \(group.maxMembers) members")
                    .font(theme.typography.captionMedium)
                    .foregroundStyle(theme.colors.textSecondary)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(theme.colors.textSecondary)
        }
        .padding(DesignSystem.Spacing.md)
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md))
        .shadowStyle(DesignSystem.Shadow.sm)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(group.name), \(group.memberCount) of \(group.maxMembers) members")
        .accessibilityHint("Double tap to view group details")
    }
}
