import AIQAPIClientCore
import AIQSharedKit
import SwiftUI

/// Detail view showing group info, leaderboard, and members
struct GroupDetailView: View {
    @StateObject private var viewModel: GroupDetailViewModel
    @EnvironmentObject private var router: AppRouter
    @Environment(\.appTheme) private var theme
    @State private var shareItem: ShareItem?

    /// Creates a GroupDetailView for the specified group
    /// - Parameters:
    ///   - groupId: The ID of the group to display
    ///   - serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    init(groupId: Int, serviceContainer: ServiceContainer = .shared) {
        let apiService: OpenAPIServiceProtocol = serviceContainer.resolve()
        let authManager: AuthManagerProtocol = serviceContainer.resolve()
        let vm = GroupDetailViewModel(apiService: apiService, authManager: authManager, groupId: groupId)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        Group {
            if viewModel.isLoading && viewModel.group == nil {
                LoadingView(message: "Loading group...")
                    .accessibilityIdentifier(AccessibilityIdentifiers.Common.loadingView)
            } else if let error = viewModel.error, viewModel.group == nil {
                ErrorView(error: error, retryAction: {
                    Task { await viewModel.fetchGroupData() }
                })
                .accessibilityIdentifier(AccessibilityIdentifiers.Common.errorView)
            } else {
                content
            }
        }
        .navigationTitle(viewModel.group?.name ?? "Group")
        .toolbar {
            if viewModel.isOwner {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button {
                            shareInvite()
                        } label: {
                            Label("Share Invite", systemImage: "square.and.arrow.up")
                        }
                        Button(role: .destructive) {
                            viewModel.showDeleteConfirmation = true
                        } label: {
                            Label("Delete Group", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
        }
        .sheet(item: $shareItem) { item in
            ShareSheet(activityItems: [item.text])
        }
        .confirmationDialog(
            "Delete Group",
            isPresented: $viewModel.showDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                Task {
                    if await viewModel.deleteGroup() {
                        router.pop()
                    }
                }
            }
        } message: {
            Text("This will permanently delete the group and remove all members. This cannot be undone.")
        }
        .task {
            await viewModel.fetchGroupData()
        }
    }

    // MARK: - Content

    private var content: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.lg) {
                // Invite code section (owner only)
                if let code = viewModel.inviteCode {
                    inviteCodeCard(code: code)
                }

                // Leaderboard section
                if let leaderboard = viewModel.leaderboard {
                    leaderboardSection(leaderboard: leaderboard)
                }

                // Members section
                if let group = viewModel.group {
                    membersSection(group: group)
                }
            }
            .padding(.horizontal, DesignSystem.Spacing.md)
            .padding(.vertical, DesignSystem.Spacing.sm)
        }
        .refreshable {
            await viewModel.refreshGroupData()
        }
    }

    // MARK: - Invite Code Card

    private func inviteCodeCard(code: String) -> some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            Text("Invite Code")
                .font(theme.typography.captionMedium)
                .foregroundStyle(theme.colors.textSecondary)

            Text(code)
                .font(.system(.title2, design: .monospaced))
                .foregroundStyle(theme.colors.textPrimary)
                .textSelection(.enabled)

            Button {
                shareInvite()
            } label: {
                Label("Share Invite", systemImage: "square.and.arrow.up")
                    .font(theme.typography.bodyMedium)
            }
            .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.shareInviteButton)
        }
        .frame(maxWidth: .infinity)
        .padding(DesignSystem.Spacing.lg)
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md))
        .shadowStyle(DesignSystem.Shadow.sm)
        .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.inviteCodeCard)
    }

    // MARK: - Leaderboard Section

    private func leaderboardSection(leaderboard: Components.Schemas.LeaderboardResponse) -> some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            Text("Leaderboard")
                .font(theme.typography.h3)
                .foregroundStyle(theme.colors.textPrimary)

            if leaderboard.entries.isEmpty {
                Text("No scores yet. Take a test to appear on the leaderboard!")
                    .font(theme.typography.bodyMedium)
                    .foregroundStyle(theme.colors.textSecondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, DesignSystem.Spacing.lg)
            } else {
                VStack(spacing: 0) {
                    ForEach(leaderboard.entries, id: \.userId) { entry in
                        LeaderboardRowView(
                            entry: entry,
                            isCurrentUser: entry.userId == viewModel.currentUserId
                        )

                        if entry.userId != leaderboard.entries.last?.userId {
                            Divider()
                        }
                    }
                }
                .background(Color(.systemBackground))
                .clipShape(RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md))
                .shadowStyle(DesignSystem.Shadow.sm)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.leaderboard)
    }

    // MARK: - Members Section

    private func membersSection(group: Components.Schemas.GroupDetailResponse) -> some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            Text("Members (\(group.memberCount)/\(group.maxMembers))")
                .font(theme.typography.h3)
                .foregroundStyle(theme.colors.textPrimary)

            VStack(spacing: 0) {
                ForEach(group.members, id: \.userId) { member in
                    memberRow(member: member)

                    if member.userId != group.members.last?.userId {
                        Divider()
                    }
                }
            }
            .background(Color(.systemBackground))
            .clipShape(RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md))
            .shadowStyle(DesignSystem.Shadow.sm)
        }
    }

    private func memberRow(member: Components.Schemas.GroupMemberResponse) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(member.firstName)
                    .font(theme.typography.bodyMedium)
                    .foregroundStyle(theme.colors.textPrimary)

                if member.role == "owner" {
                    Text("Owner")
                        .font(theme.typography.captionMedium)
                        .foregroundStyle(theme.colors.primary)
                }
            }

            Spacer()

            if viewModel.isOwner && member.userId != viewModel.currentUserId {
                Button(role: .destructive) {
                    Task { await viewModel.removeMember(userId: member.userId) }
                } label: {
                    Image(systemName: "person.crop.circle.badge.minus")
                        .foregroundStyle(.red)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Remove \(member.firstName) from group")
            }
        }
        .padding(DesignSystem.Spacing.md)
    }

    // MARK: - Actions

    private func shareInvite() {
        guard let code = viewModel.inviteCode else { return }
        let text = if let link = viewModel.inviteLink {
            "Join my group on AIQ! Use invite code: \(code) or tap this link: \(link)"
        } else {
            "Join my group on AIQ! Use invite code: \(code)"
        }
        shareItem = ShareItem(text: text)
    }
}

// MARK: - Share Item

/// Wrapper to make share text identifiable for the sheet modifier
private struct ShareItem: Identifiable {
    let id = UUID()
    let text: String
}

// MARK: - Share Sheet

private struct ShareSheet: UIViewControllerRepresentable {
    let activityItems: [Any]

    func makeUIViewController(context _: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: activityItems, applicationActivities: nil)
    }

    func updateUIViewController(_: UIActivityViewController, context _: Context) {}
}
