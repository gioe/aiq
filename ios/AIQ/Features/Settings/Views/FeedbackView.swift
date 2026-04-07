import AIQSharedKit
import SwiftUI

/// Feedback form view for user feedback submissions
struct FeedbackView: View {
    @StateObject private var viewModel: FeedbackViewModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.appTheme) private var theme

    /// Creates a FeedbackView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeFeedbackViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        ZStack {
            ScrollView {
                VStack(spacing: DesignSystem.Spacing.xxl) {
                    // Header
                    headerSection

                    // Form Fields
                    formFieldsSection
                }
                .padding(DesignSystem.Spacing.lg)
            }
            .navigationTitle("Feedback")
            .navigationBarTitleDisplayMode(.large)

            // Success Message Overlay
            if viewModel.showSuccessMessage {
                successOverlay
            }

            // Loading Overlay
            if viewModel.isLoading {
                LoadingOverlay(message: "Submitting feedback...")
            }
        }
    }

    // MARK: - Subviews

    private var headerSection: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            Text("We'd love to hear from you!")
                .font(theme.typography.h3)
                .foregroundColor(theme.colors.textPrimary)
                .multilineTextAlignment(.center)

            Text("Share your feedback, report bugs, or request new features.")
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.textSecondary)
                .multilineTextAlignment(.center)
        }
        .accessibilityElement(children: .combine)
    }

    private var formFieldsSection: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            // Name Field
            nameField

            // Email Field
            emailField

            // Category Menu
            categoryMenu

            // Description Field
            descriptionField

            // Submit Button
            submitButton
        }
    }

    private var nameField: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            CustomTextField(
                title: "Name",
                placeholder: "Enter your name",
                text: $viewModel.name,
                autocapitalization: .words,
                accessibilityId: AccessibilityIdentifiers.FeedbackView.nameTextField
            )

            if !viewModel.nameValidation.isValid, !viewModel.name.isEmpty {
                validationErrorText(viewModel.nameValidation.errorMessage ?? "")
            }
        }
    }

    private var emailField: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            CustomTextField(
                title: "Email",
                placeholder: "Enter your email",
                text: $viewModel.email,
                keyboardType: .emailAddress,
                autocapitalization: .never,
                accessibilityId: AccessibilityIdentifiers.FeedbackView.emailTextField
            )

            if !viewModel.emailValidation.isValid, !viewModel.email.isEmpty {
                validationErrorText(viewModel.emailValidation.errorMessage ?? "")
            }
        }
    }

    private var categoryMenu: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            Text("Category")
                .font(theme.typography.labelMedium)
                .foregroundColor(theme.colors.textPrimary)

            Menu {
                ForEach(FeedbackCategory.allCases, id: \.self) { category in
                    Button {
                        viewModel.selectedCategory = category
                    } label: {
                        HStack {
                            Text(category.displayName)
                            if viewModel.selectedCategory == category {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            } label: {
                HStack {
                    Text(viewModel.selectedCategory?.displayName ?? "Select a category")
                        .foregroundColor(
                            viewModel.selectedCategory == nil
                                ? theme.colors.textSecondary
                                : theme.colors.textPrimary
                        )
                    Spacer()
                    Image(systemName: "chevron.down")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(theme.colors.textSecondary)
                }
                .frame(minHeight: 44) // Ensure minimum touch target
                .padding(DesignSystem.Spacing.lg)
                .background(theme.colors.backgroundSecondary)
                .cornerRadius(DesignSystem.CornerRadius.md)
                .overlay(
                    RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                        .stroke(theme.colors.textSecondary.opacity(0.2), lineWidth: 1)
                )
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 44) // Ensure minimum touch target for entire menu
            .accessibilityLabel("Category, \(viewModel.selectedCategory?.displayName ?? "not selected")")
            .accessibilityHint("Double tap to open menu and select a feedback category")
            .accessibilityIdentifier(AccessibilityIdentifiers.FeedbackView.categoryMenu)

            if !viewModel.categoryValidation.isValid, viewModel.selectedCategory == nil, !viewModel.name.isEmpty {
                validationErrorText(viewModel.categoryValidation.errorMessage ?? "")
            }
        }
    }

    private var descriptionField: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
            Text("Description")
                .font(theme.typography.labelMedium)
                .foregroundColor(theme.colors.textPrimary)

            ZStack(alignment: .topLeading) {
                TextEditor(text: $viewModel.description)
                    .frame(minHeight: 150)
                    .padding(DesignSystem.Spacing.sm)
                    .scrollContentBackground(.hidden)
                    .background(theme.colors.backgroundSecondary)
                    .cornerRadius(DesignSystem.CornerRadius.md)
                    .overlay(
                        RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                            .stroke(theme.colors.textSecondary.opacity(0.2), lineWidth: 1)
                    )

                if viewModel.description.isEmpty {
                    Text("Describe your feedback, bug, or feature request...")
                        .font(theme.typography.bodyMedium)
                        .foregroundColor(theme.colors.textSecondary)
                        .padding(.horizontal, DesignSystem.Spacing.lg)
                        .padding(.vertical, DesignSystem.Spacing.lg)
                        .allowsHitTesting(false)
                }
            }
            .accessibilityLabel(viewModel.description.isEmpty ? "Description, empty" : "Description")
            .accessibilityHint("Text field. Double tap to edit. Minimum 10 characters required.")
            .accessibilityIdentifier(AccessibilityIdentifiers.FeedbackView.descriptionTextField)

            // Character count
            Text("\(viewModel.description.count) characters")
                .font(theme.typography.captionMedium)
                .foregroundColor(theme.colors.textSecondary)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .accessibilityLabel("\(viewModel.description.count) characters entered")

            if !viewModel.descriptionValidation.isValid, !viewModel.description.isEmpty {
                validationErrorText(viewModel.descriptionValidation.errorMessage ?? "")
            }
        }
    }

    private var submitButton: some View {
        Button {
            Task {
                await viewModel.submitFeedback()
            }
        } label: {
            HStack {
                Spacer()
                Text("Submit Feedback")
                    .font(theme.typography.button)
                    .foregroundColor(.white)
                Spacer()
            }
            .frame(minHeight: 44) // Ensure minimum touch target
            .padding(DesignSystem.Spacing.lg)
            .background(
                viewModel.isFormValid
                    ? theme.colors.primary
                    : theme.colors.textSecondary.opacity(0.3)
            )
            .cornerRadius(DesignSystem.CornerRadius.md)
        }
        .disabled(!viewModel.isFormValid || viewModel.isLoading)
        .accessibilityLabel("Submit Feedback")
        .accessibilityHint(
            viewModel.isFormValid
                ? "Double tap to submit your feedback"
                : "Complete all fields to enable submission"
        )
        .accessibilityIdentifier(AccessibilityIdentifiers.FeedbackView.submitButton)
    }

    private var successOverlay: some View {
        ZStack {
            theme.colors.background.opacity(0.95)
                .ignoresSafeArea()

            VStack(spacing: DesignSystem.Spacing.xl) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: theme.iconSizes.huge))
                    .foregroundColor(theme.colors.success)
                    .accessibilityHidden(true)

                Text("Thank you!")
                    .font(theme.typography.h2)
                    .foregroundColor(theme.colors.textPrimary)

                Text("Your feedback has been submitted successfully.")
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .multilineTextAlignment(.center)
            }
            .padding(DesignSystem.Spacing.xxl)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Success. Thank you! Your feedback has been submitted successfully.")
        .accessibilityAddTraits(.isStaticText)
    }

    // MARK: - Helper Functions

    private func validationErrorText(_ message: String) -> some View {
        Text(message)
            .font(theme.typography.captionMedium)
            .foregroundColor(theme.colors.errorText)
            .accessibilityLabel("Error: \(message)")
    }
}

#Preview {
    NavigationStack {
        FeedbackView()
    }
}

#Preview("With Validation Errors") {
    NavigationStack {
        FeedbackView()
    }
}
