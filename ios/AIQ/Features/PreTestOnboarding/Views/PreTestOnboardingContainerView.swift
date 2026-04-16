import AIQSharedKit
import SwiftUI

/// Multi-page pre-test onboarding experience shown before a first-time user's test.
///
/// Pages cover test overview, testing rules, integrity messaging, and an optional
/// notification permission pitch.
///
/// Gate: `PreTestInfoGate.shouldShow()` (unchanged from DashboardView).
/// Persistence: sets `hasSeenPreTestInfo = true` on completion via the `onComplete` callback.
struct PreTestOnboardingContainerView: View {
    // MARK: - Callbacks

    /// Called when user completes the flow (taps "Begin Test" on the last page)
    let onComplete: () -> Void

    /// Called when user dismisses the flow (taps close button)
    let onDismiss: () -> Void

    /// Called when user enables reminders on the notification page
    let onEnableReminders: () -> Void

    /// Called when user declines reminders on the notification page
    let onDeclineReminders: () -> Void

    // MARK: - State

    @StateObject private var viewModel: PreTestOnboardingViewModel
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    // MARK: - Initialization

    init(
        showNotificationPage: Bool,
        onComplete: @escaping () -> Void,
        onDismiss: @escaping () -> Void,
        onEnableReminders: @escaping () -> Void,
        onDeclineReminders: @escaping () -> Void
    ) {
        _viewModel = StateObject(wrappedValue: PreTestOnboardingViewModel(
            showNotificationPage: showNotificationPage
        ))
        self.onComplete = onComplete
        self.onDismiss = onDismiss
        self.onEnableReminders = onEnableReminders
        self.onDeclineReminders = onDeclineReminders
    }

    // MARK: - Body

    var body: some View {
        ZStack {
            // Background
            theme.colors.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Close Button (top-right)
                HStack {
                    Spacer()

                    IconButton(
                        icon: "xmark",
                        action: handleDismiss,
                        accessibilityLabel: String(localized: "pretest.onboarding.close.accessibility"),
                        foregroundColor: theme.colors.textSecondary
                    )
                    .accessibilityIdentifier(AccessibilityIdentifiers.PreTestOnboardingView.closeButton)
                }
                .padding(.horizontal, DesignSystem.Spacing.lg)
                .padding(.top, DesignSystem.Spacing.md)

                // TabView with Pages
                TabView(selection: $viewModel.currentPage) {
                    PreTestOverviewPageView()
                        .tag(0)

                    PreTestRulesPageView()
                        .tag(1)

                    PreTestIntegrityPageView()
                        .tag(2)

                    if viewModel.totalPages == 4 {
                        PreTestNotificationsPageView(
                            onEnableReminders: handleEnableReminders,
                            onDeclineReminders: handleDeclineReminders
                        )
                        .tag(3)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .onChange(of: viewModel.currentPage) { _ in
                    ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.light)
                }

                // Custom page indicator
                PageIndicator(currentPage: $viewModel.currentPage, totalPages: viewModel.totalPages)
                    .padding(.bottom, DesignSystem.Spacing.md)

                // Bottom Button Area
                VStack(spacing: DesignSystem.Spacing.md) {
                    if viewModel.isNotificationPage {
                        // Notification page has its own buttons embedded in the page view
                        EmptyView()
                    } else if viewModel.isLastPage {
                        PrimaryButton(
                            title: String(localized: "pretest.onboarding.begin.test"),
                            action: handleComplete,
                            accessibilityId: AccessibilityIdentifiers.PreTestOnboardingView.beginTestButton
                        )
                        .padding(.horizontal, DesignSystem.Spacing.xxl)
                    } else {
                        PrimaryButton(
                            title: String(localized: "pretest.onboarding.continue"),
                            action: handleContinue,
                            accessibilityId: AccessibilityIdentifiers.PreTestOnboardingView.continueButton
                        )
                        .padding(.horizontal, DesignSystem.Spacing.xxl)
                    }
                }
                .padding(.bottom, DesignSystem.Spacing.xl)
            }
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.PreTestOnboardingView.containerView)
        .onAppear {
            ServiceContainer.shared.resolve(HapticManagerProtocol.self).prepare()
        }
    }

    // MARK: - Actions

    private func handleContinue() {
        ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.medium)

        if reduceMotion {
            viewModel.nextPage()
        } else {
            withAnimation(theme.animations.smooth) {
                viewModel.nextPage()
            }
        }
    }

    private func handleComplete() {
        ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.success)
        onComplete()
    }

    private func handleDismiss() {
        ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.medium)
        onDismiss()
    }

    private func handleEnableReminders() {
        ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.success)
        onEnableReminders()
    }

    private func handleDeclineReminders() {
        ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.medium)
        onDeclineReminders()
    }
}

// MARK: - Previews

#Preview("With Notifications") {
    PreTestOnboardingContainerView(
        showNotificationPage: true,
        onComplete: {},
        onDismiss: {},
        onEnableReminders: {},
        onDeclineReminders: {}
    )
}

#Preview("Without Notifications") {
    PreTestOnboardingContainerView(
        showNotificationPage: false,
        onComplete: {},
        onDismiss: {},
        onEnableReminders: {},
        onDeclineReminders: {}
    )
}

#Preview("Dark Mode") {
    PreTestOnboardingContainerView(
        showNotificationPage: true,
        onComplete: {},
        onDismiss: {},
        onEnableReminders: {},
        onDeclineReminders: {}
    )
    .preferredColorScheme(.dark)
}
