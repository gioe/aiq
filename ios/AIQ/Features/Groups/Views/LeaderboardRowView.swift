import AIQAPIClientCore
import AIQSharedKit
import SwiftUI

/// A single row in the leaderboard showing a member's rank and scores
struct LeaderboardRowView: View {
    let entry: Components.Schemas.LeaderboardEntryResponse
    let isCurrentUser: Bool
    @Environment(\.appTheme) private var theme

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            // Rank badge
            rankBadge

            // Name
            Text(entry.firstName)
                .font(theme.typography.bodyMedium)
                .foregroundStyle(theme.colors.textPrimary)
                .fontWeight(isCurrentUser ? .semibold : .regular)

            Spacer()

            // Scores
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(entry.bestScore)")
                    .font(theme.typography.bodyMedium)
                    .foregroundStyle(theme.colors.textPrimary)
                    .fontWeight(.semibold)

                Text("avg \(Int(entry.averageScore.rounded()))")
                    .font(theme.typography.captionMedium)
                    .foregroundStyle(theme.colors.textSecondary)
            }
        }
        .padding(DesignSystem.Spacing.md)
        .background(isCurrentUser ? theme.colors.primary.opacity(0.08) : Color.clear)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "\(rankLabel) \(entry.firstName), best score \(entry.bestScore)," +
                " average \(Int(entry.averageScore.rounded()))"
        )
    }

    // MARK: - Rank Badge

    private var rankBadge: some View {
        Group {
            switch entry.rank {
            case 1:
                Image(systemName: "trophy.fill")
                    .foregroundStyle(.yellow)
            case 2:
                Image(systemName: "trophy.fill")
                    .foregroundStyle(.gray)
            case 3:
                Image(systemName: "trophy.fill")
                    .foregroundStyle(.brown)
            default:
                Text("#\(entry.rank)")
                    .font(theme.typography.captionMedium)
                    .foregroundStyle(theme.colors.textSecondary)
            }
        }
        .frame(width: 32)
        .accessibilityHidden(true)
    }

    private var rankLabel: String {
        switch entry.rank {
        case 1: "First place"
        case 2: "Second place"
        case 3: "Third place"
        default: "Rank \(entry.rank)"
        }
    }
}
