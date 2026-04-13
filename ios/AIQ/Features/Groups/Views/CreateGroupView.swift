import AIQSharedKit
import SwiftUI

/// View for creating a new group
struct CreateGroupView: View {
    @StateObject private var viewModel: CreateGroupViewModel
    @EnvironmentObject private var router: AppRouter
    @Environment(\.appTheme) private var theme
    @FocusState private var isNameFocused: Bool

    /// Creates a CreateGroupView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeCreateGroupViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            // Group name input
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
                Text("Group Name")
                    .font(theme.typography.bodyMedium)
                    .foregroundStyle(theme.colors.textPrimary)

                TextField("Enter group name", text: $viewModel.groupName)
                    .textFieldStyle(.roundedBorder)
                    .focused($isNameFocused)
                    .onChange(of: viewModel.groupName) { newValue in
                        if newValue.count > CreateGroupViewModel.maxGroupNameLength {
                            viewModel.groupName = String(newValue.prefix(CreateGroupViewModel.maxGroupNameLength))
                        }
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.groupNameField)

                Text("\(viewModel.remainingCharacters) characters remaining")
                    .font(theme.typography.captionMedium)
                    .foregroundStyle(
                        viewModel.remainingCharacters < 5
                            ? theme.colors.errorText
                            : theme.colors.textSecondary
                    )
                    .accessibilityLabel("\(viewModel.remainingCharacters) characters remaining")
            }

            // Create button
            PrimaryButton(
                title: "Create Group",
                action: {
                    Task {
                        if await viewModel.createGroup() {
                            router.pop()
                        }
                    }
                },
                isLoading: viewModel.isLoading,
                isDisabled: !viewModel.isValidGroupName,
                accessibilityId: AccessibilityIdentifiers.GroupsView.createButton
            )

            if let error = viewModel.error {
                Text(error.localizedDescription)
                    .font(theme.typography.captionMedium)
                    .foregroundStyle(theme.colors.errorText)
                    .multilineTextAlignment(.center)
            }

            Spacer()
        }
        .padding(DesignSystem.Spacing.lg)
        .navigationTitle("Create Group")
        .onAppear {
            isNameFocused = true
        }
    }
}
