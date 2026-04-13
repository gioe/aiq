import AIQSharedKit
import SwiftUI

/// Root view for the Groups tab showing all groups the user belongs to
struct GroupsListView: View {
    @StateObject private var viewModel: GroupsListViewModel
    @EnvironmentObject private var router: AppRouter
    @Environment(\.appTheme) private var theme

    /// Creates a GroupsListView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeGroupsListViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        Group {
            if viewModel.isLoading && viewModel.groups.isEmpty {
                LoadingView(message: "Loading groups...")
                    .accessibilityIdentifier(AccessibilityIdentifiers.Common.loadingView)
            } else if let error = viewModel.error {
                ErrorView(error: error) {
                    Task { await viewModel.fetchGroups() }
                }
                .accessibilityIdentifier(AccessibilityIdentifiers.Common.errorView)
            } else if viewModel.hasGroups {
                groupsList
            } else {
                emptyState
            }
        }
        .navigationTitle("Groups")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        router.push(.createGroup)
                    } label: {
                        Label("Create Group", systemImage: "plus.circle")
                    }
                    Button {
                        router.push(.joinGroup)
                    } label: {
                        Label("Join Group", systemImage: "person.badge.plus")
                    }
                } label: {
                    Image(systemName: "plus")
                        .accessibilityLabel("Add group")
                }
                .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.addButton)
            }
        }
        .task {
            await viewModel.fetchGroups()
        }
    }

    // MARK: - Groups List

    private var groupsList: some View {
        ScrollView {
            LazyVStack(spacing: DesignSystem.Spacing.md) {
                ForEach(viewModel.groups, id: \.id) { group in
                    GroupCardView(group: group)
                        .onTapGesture {
                            router.push(.groupDetail(groupId: group.id))
                        }
                        .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.groupCard(id: group.id))
                }
            }
            .padding(.horizontal, DesignSystem.Spacing.md)
            .padding(.vertical, DesignSystem.Spacing.sm)
        }
        .refreshable {
            await viewModel.refreshGroups()
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.groupsList)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        EmptyStateView(
            icon: "person.3",
            title: "No Groups Yet",
            message: "Create a group to compete with friends or join one with an invite code.",
            actionTitle: "Create Group",
            action: {
                router.push(.createGroup)
            }
        )
        .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.emptyState)
    }
}
