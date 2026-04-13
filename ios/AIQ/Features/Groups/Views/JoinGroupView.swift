import AIQSharedKit
import SwiftUI

/// View for joining a group via invite code
struct JoinGroupView: View {
    @StateObject private var viewModel: JoinGroupViewModel
    @EnvironmentObject private var router: AppRouter
    @Environment(\.appTheme) private var theme
    @FocusState private var isCodeFocused: Bool

    /// Creates a JoinGroupView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeJoinGroupViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            // Invite code input
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
                Text("Invite Code")
                    .font(theme.typography.bodyMedium)
                    .foregroundStyle(theme.colors.textPrimary)

                TextField("Enter invite code", text: $viewModel.inviteCode)
                    .textFieldStyle(.roundedBorder)
                    .autocapitalization(.none)
                    .autocorrectionDisabled()
                    .focused($isCodeFocused)
                    .accessibilityIdentifier(AccessibilityIdentifiers.GroupsView.inviteCodeField)
            }

            // Join button
            PrimaryButton(
                title: "Join Group",
                action: {
                    Task {
                        if await viewModel.joinGroup() {
                            router.pop()
                        }
                    }
                },
                isLoading: viewModel.isLoading,
                isDisabled: !viewModel.isValidCode,
                accessibilityId: AccessibilityIdentifiers.GroupsView.joinButton
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
        .navigationTitle("Join Group")
        .onAppear {
            isCodeFocused = true
        }
    }
}
