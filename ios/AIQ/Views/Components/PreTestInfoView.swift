import AIQSharedKit
import SwiftUI

/// A bottom-sheet modal informing users about the test before they begin.
///
/// Shown to first-time users (no completed tests) and onboarding skippers
/// when the "Don't Show Again" preference has not been set. Explains test
/// duration, baseline scoring, environment expectations, and retest cadence.
///
/// Usage:
/// ```swift
/// .sheet(isPresented: $showPreTestInfo) {
///     PreTestInfoView(
///         onStartTest: {
///             // Proceed to test
///             navigateToTest()
///         },
///         onDontShowAgain: {
///             // Persist the preference
///             hasSeenPreTestInfo = true
///         },
///         onDismiss: {
///             // Return to dashboard — no navigation
///         }
///     )
/// }
/// ```
struct PreTestInfoView: View {
    // MARK: - Callbacks

    /// Called when user taps "I'm Ready — Start Test". If `dontShowAgain` is set,
    /// `onDontShowAgain` is called first, then this callback.
    let onStartTest: () -> Void

    /// Called before `onStartTest` when the user has toggled "Don't Show Again".
    let onDontShowAgain: () -> Void

    /// Called when user taps "Not Now" or the close button. No navigation occurs.
    let onDismiss: () -> Void

    // MARK: - Environment

    @Environment(\.dismiss) private var dismiss
    @Environment(\.appTheme) private var theme

    // MARK: - State

    /// Local toggle state for the "Don't Show Again" control.
    /// The caller is responsible for persisting this via `onDontShowAgain`.
    @State private var dontShowAgain: Bool = false

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            // Close button row
            HStack {
                Spacer()

                IconButton(
                    icon: "xmark",
                    action: handleDismiss,
                    accessibilityLabel: NSLocalizedString(
                        "pretest.info.close.accessibility",
                        comment: "Close pre-test info modal"
                    ),
                    foregroundColor: theme.colors.textSecondary
                )
            }
            .padding(.horizontal, theme.spacing.lg)
            .padding(.top, theme.spacing.lg)

            Spacer()

            // Icon
            Image(systemName: "brain.head.profile")
                .font(.system(size: theme.iconSizes.huge))
                .foregroundColor(theme.colors.primary)
                .accessibilityHidden(true)
                .padding(.bottom, theme.spacing.xl)

            // Title
            Text(NSLocalizedString("pretest.info.title", comment: "Pre-test info modal title"))
                .font(theme.typography.h1)
                .foregroundColor(theme.colors.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.bottom, theme.spacing.xl)
                .accessibilityAddTraits(.isHeader)

            // Bullet points
            VStack(alignment: .leading, spacing: theme.spacing.md) {
                bulletRow(
                    icon: "clock.fill",
                    text: NSLocalizedString("pretest.info.duration", comment: "Duration bullet point")
                )
                bulletRow(
                    icon: "chart.bar.fill",
                    text: NSLocalizedString("pretest.info.baseline", comment: "Baseline bullet point")
                )
                bulletRow(
                    icon: "eye.fill",
                    text: NSLocalizedString("pretest.info.environment", comment: "Environment bullet point")
                )
                bulletRow(
                    icon: "calendar",
                    text: NSLocalizedString("pretest.info.retest", comment: "Retest interval bullet point")
                )
            }
            .padding(.horizontal, theme.spacing.xxxl)
            .padding(.bottom, theme.spacing.xl)

            // Don't Show Again toggle
            Toggle(
                NSLocalizedString("pretest.info.dont.show.again", comment: "Don't show again toggle label"),
                isOn: $dontShowAgain
            )
            .font(theme.typography.bodyMedium)
            .foregroundColor(theme.colors.textSecondary)
            .padding(.horizontal, theme.spacing.xxxl)
            .padding(.bottom, theme.spacing.xxl)
            .accessibilityIdentifier(AccessibilityIdentifiers.PreTestInfoView.dontShowAgainToggle)
            .accessibilityHint("Double tap to toggle whether this screen shows before future tests")

            Spacer()

            // Action buttons
            VStack(spacing: theme.spacing.md) {
                PrimaryButton(
                    title: NSLocalizedString(
                        "pretest.info.start.button",
                        comment: "Primary start test button"
                    ),
                    action: handleStartTest,
                    accessibilityId: AccessibilityIdentifiers.PreTestInfoView.startTestButton
                )

                Button(action: handleDismiss) {
                    Text(NSLocalizedString("pretest.info.not.now.button", comment: "Secondary dismiss button"))
                        .font(theme.typography.button)
                        .foregroundColor(theme.colors.textSecondary)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 44)
                }
                .accessibilityLabel(
                    NSLocalizedString("pretest.info.not.now.button", comment: "Secondary dismiss button")
                )
                .accessibilityHint("Double tap to return to the dashboard without starting a test")
                .accessibilityIdentifier(AccessibilityIdentifiers.PreTestInfoView.notNowButton)
            }
            .padding(.horizontal, theme.spacing.xxl)
            .padding(.bottom, theme.spacing.xxxl)
        }
        .background(theme.colors.background)
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }

    // MARK: - Private Views

    /// Renders a single icon + text bullet row.
    private func bulletRow(icon: String, text: String) -> some View {
        HStack(alignment: .top, spacing: theme.spacing.md) {
            Image(systemName: icon)
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.primary)
                .frame(width: 20)
                .accessibilityHidden(true)

            Text(text)
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(text)
    }

    // MARK: - Private Methods

    /// Handles the start test action, persisting "don't show again" if toggled.
    private func handleStartTest() {
        if dontShowAgain {
            onDontShowAgain()
        }
        dismiss()
        onStartTest()
    }

    /// Handles the dismiss / "Not Now" action.
    private func handleDismiss() {
        dismiss()
        onDismiss()
    }
}

// MARK: - Gate Logic

/// Stateless gate for determining whether `PreTestInfoView` should be shown.
///
/// Extracted from `DashboardView` so it can be unit-tested without spinning up SwiftUI.
enum PreTestInfoGate {
    /// Returns `true` when the pre-test info modal should be displayed.
    ///
    /// The modal is suppressed if the user has previously toggled "Don't Show Again"
    /// (`hasSeenPreTestInfo == true`). Otherwise it shows for:
    /// - First-time users with no completed tests (`testCount == 0`), or
    /// - Users who skipped the onboarding flow (`didSkipOnboarding == true`).
    static func shouldShow(
        testCount: Int,
        didSkipOnboarding: Bool,
        hasSeenPreTestInfo: Bool
    ) -> Bool {
        !hasSeenPreTestInfo && (testCount == 0 || didSkipOnboarding)
    }
}

// MARK: - Previews

#Preview("Default") {
    PreTestInfoView(
        onStartTest: { print("Start test tapped") },
        onDontShowAgain: { print("Don't show again set") },
        onDismiss: { print("Dismissed") }
    )
}

#Preview("Dark Mode") {
    PreTestInfoView(
        onStartTest: { print("Start test tapped") },
        onDontShowAgain: { print("Don't show again set") },
        onDismiss: { print("Dismissed") }
    )
    .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    PreTestInfoView(
        onStartTest: { print("Start test tapped") },
        onDontShowAgain: { print("Don't show again set") },
        onDismiss: { print("Dismissed") }
    )
    .environment(\.sizeCategory, .accessibilityExtraExtraExtraLarge)
}
