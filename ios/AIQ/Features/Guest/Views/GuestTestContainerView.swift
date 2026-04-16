import AIQSharedKit
import SwiftUI
import UIKit

/// Container view for the guest test flow.
///
/// Manages its own NavigationStack and guest test lifecycle:
/// 1. Starts a guest test via `TestTakingViewModel.startGuestTest(deviceId:)`
/// 2. Reuses the standard test-taking UI components (same questions, timer, navigation)
/// 3. Shows results with a "Create Account" / "Maybe Later" CTA
///
/// This view is presented from `RootView` when `isGuestTestMode` is true,
/// bypassing authentication entirely.
struct GuestTestContainerView: View {
    @StateObject private var viewModel: TestTakingViewModel
    @StateObject private var timerManager = TestTimerManager()

    @State private var showQuestionGrid = false
    @State private var showTimeWarningBanner = false
    @State private var warningBannerDismissed = false
    @State private var isAutoSubmitting = false
    @State private var showRegistration = false

    /// Callback to exit guest mode and return to WelcomeView
    let onExit: () -> Void

    /// Called when the guest test limit has been reached (testsRemaining == 0)
    let onLimitReached: () -> Void

    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    init(
        onExit: @escaping () -> Void,
        onLimitReached: @escaping () -> Void = {},
        serviceContainer: ServiceContainer = .shared
    ) {
        self.onExit = onExit
        self.onLimitReached = onLimitReached
        let vm = ViewModelFactory.makeTestTakingViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                if viewModel.isTestCompleted, let result = viewModel.testResult {
                    guestResultsView(result: result)
                } else if shouldShowLoadFailure {
                    guestLoadFailureView
                } else {
                    guestTestContentView
                }

                if viewModel.isLoading && viewModel.navigationState.questions.isEmpty {
                    LoadingOverlay(message: "Preparing your test...")
                        .loadingOverlayTransition(reduceMotion: reduceMotion)
                }

                if viewModel.isSubmitting {
                    LoadingOverlay(message: "Submitting your test...")
                        .loadingOverlayTransition(reduceMotion: reduceMotion)
                }
            }
            .navigationTitle("AIQ Test")
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarBackButtonHidden(true)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if !viewModel.isTestCompleted {
                        Button("Exit") {
                            handleExit()
                        }
                        .frame(minWidth: 44, minHeight: 44)
                        .accessibilityLabel("Exit test")
                        .accessibilityIdentifier(
                            AccessibilityIdentifiers.GuestTestContainerView.exitButton
                        )
                    }
                }
            }
            .task {
                await startGuestTest()
            }
            .modifier(TestTimerModifier(
                timerManager: timerManager,
                isTestCompleted: viewModel.isTestCompleted,
                showTimeWarningBanner: $showTimeWarningBanner,
                warningBannerDismissed: $warningBannerDismissed,
                onExpire: handleTimerExpiration
            ))
            .overlay {
                if viewModel.showExitConfirmation {
                    exitConfirmationModal
                        .transition(.opacity)
                }
            }
            .alert("Time's Up!", isPresented: Binding(
                get: { viewModel.showTimeExpiredAlert },
                set: { if !$0 { viewModel.dismissTimeExpiredAlert() } }
            )) {
                Button("OK") {}
            } message: {
                let count = viewModel.answeredCount
                let plural = count == 1 ? "" : "s"
                Text(
                    "The 30-minute time limit has expired. " +
                        "Your \(count) answered question\(plural) " +
                        "will be submitted automatically."
                )
            }
            .navigationDestination(isPresented: $showRegistration) {
                RegistrationView()
            }
        }
    }

    // MARK: - Load Failure

    private var shouldShowLoadFailure: Bool {
        !viewModel.isLoading
            && viewModel.navigationState.questions.isEmpty
            && viewModel.error != nil
    }

    private var guestLoadFailureView: some View {
        VStack(spacing: DesignSystem.Spacing.xl) {
            Spacer()

            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 60))
                .foregroundColor(theme.colors.errorText)
                .accessibilityHidden(true)

            if let error = viewModel.error {
                Text(error.localizedDescription)
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, DesignSystem.Spacing.xxl)
            }

            PrimaryButton(
                title: "Try Again",
                action: {
                    Task { await startGuestTest() }
                }
            )
            .padding(.horizontal, DesignSystem.Spacing.xxl)

            Button("Go Back") {
                onExit()
            }
            .font(theme.typography.button)
            .foregroundColor(theme.colors.textSecondary)
            .frame(minHeight: 44)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemGroupedBackground))
    }

    // MARK: - Test Content

    private var guestTestContentView: some View {
        TestContentLayout(
            viewModel: viewModel,
            timerManager: timerManager,
            showQuestionGrid: $showQuestionGrid,
            showTimeWarningBanner: $showTimeWarningBanner,
            warningBannerDismissed: $warningBannerDismissed,
            reduceMotion: reduceMotion
        )
    }

    // MARK: - Guest Results

    private func guestResultsView(result: SubmittedTestResult) -> some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxxl) {
                guestScoreSection(result: result)
                guestResultsCTA
            }
            .padding(DesignSystem.Spacing.lg)
        }
        .background(theme.colors.backgroundGrouped)
        .navigationTitle("Test Results")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .onAppear {
            ServiceContainer.shared.resolve(HapticManagerProtocol.self).trigger(.success)
        }
    }

    private func guestScoreSection(result: SubmittedTestResult) -> some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            Image(systemName: "trophy.fill")
                .font(.system(size: theme.iconSizes.xl))
                .foregroundStyle(theme.gradients.trophyGradient)
                .accessibilityHidden(true)

            VStack(spacing: DesignSystem.Spacing.xs) {
                Text("Your Score")
                    .font(theme.typography.h3)
                    .foregroundColor(theme.colors.textSecondary)

                Text("\(result.iqScore)")
                    .scoreDisplayFont()
                    .foregroundStyle(theme.gradients.scoreGradient)

                Text(IQScoreUtility.classify(result.iqScore).description)
                    .font(theme.typography.bodyMedium)
                    .foregroundColor(theme.colors.textSecondary)
                    .multilineTextAlignment(.center)
            }

            if let percentile = result.percentileRank {
                PercentileCard(
                    percentileRank: percentile,
                    showAnimation: true
                )
            }

            // Domain breakdown
            if result.domainScoresConverted != nil {
                DomainScoresBreakdownView(
                    domainScores: result.domainScoresConverted,
                    showAnimation: true,
                    strongestDomain: result.strongestDomain,
                    weakestDomain: result.weakestDomain
                )
            }
        }
        .padding(DesignSystem.Spacing.xxl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.lg,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: theme.colors.background
        )
    }

    private var guestResultsCTA: some View {
        VStack(spacing: DesignSystem.Spacing.lg) {
            Image(systemName: "person.badge.plus")
                .font(.system(size: theme.iconSizes.lg))
                .foregroundStyle(theme.gradients.scoreGradient)
                .accessibilityHidden(true)

            Text("Save Your Score")
                .font(theme.typography.h3)
                .foregroundColor(theme.colors.textPrimary)

            Text("Create a free account to track your cognitive trends over time.")
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.textSecondary)
                .multilineTextAlignment(.center)

            PrimaryButton(
                title: "Create Account",
                action: {
                    showRegistration = true
                }
            )

            Button("Maybe Later") {
                onExit()
            }
            .font(theme.typography.button)
            .foregroundColor(theme.colors.textSecondary)
            .frame(minHeight: 44)
        }
        .padding(DesignSystem.Spacing.xxl)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.lg,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: theme.colors.background
        )
    }

    // MARK: - Actions

    private static let guestDeviceIdKey = "com.aiq.guestDeviceId"

    /// Returns a stable device identifier for guest tests.
    /// Prefers identifierForVendor; falls back to a UUID persisted in UserDefaults.
    private func stableDeviceId() -> String {
        if let vendorId = UIDevice.current.identifierForVendor?.uuidString {
            return vendorId
        }
        let defaults = UserDefaults.standard
        if let stored = defaults.string(forKey: Self.guestDeviceIdKey) {
            return stored
        }
        let newId = UUID().uuidString
        defaults.set(newId, forKey: Self.guestDeviceIdKey)
        return newId
    }

    private func startGuestTest() async {
        let deviceId = stableDeviceId()
        await viewModel.startGuestTest(deviceId: deviceId)

        if viewModel.guestTestsRemaining == 0 {
            onLimitReached()
        }

        if let session = viewModel.testSession {
            let timerStarted = timerManager.startWithSessionTime(session.startedAt)
            if !timerStarted {
                handleTimerExpiration()
            }
        }
    }

    private func handleExit() {
        if viewModel.answeredCount > 0 && !viewModel.isTestCompleted {
            viewModel.requestExit()
        } else {
            onExit()
        }
    }

    // MARK: - Exit Confirmation

    private var exitConfirmationMessage: String {
        let answered = viewModel.answeredCount
        let total = viewModel.totalQuestionCount
        if answered >= Constants.Test.abandonAnswerThreshold {
            return "You've answered \(answered) of \(total) questions. " +
                "Your answers will not be scored, and this will count as a test attempt. " +
                "You'll need to wait before you can retake the test."
        } else {
            return "You've answered \(answered) of \(total) questions. " +
                "Your answers will not be scored."
        }
    }

    private var exitConfirmationModal: some View {
        ConfirmationModal(
            iconName: "exclamationmark.triangle",
            title: "Exit Test?",
            message: exitConfirmationMessage,
            confirmLabel: "Exit",
            confirmAccessibilityLabel: "Exit test",
            confirmAccessibilityHint: "Double tap to exit the test without scoring",
            confirmAccessibilityIdentifier: AccessibilityIdentifiers.GuestTestContainerView.exitConfirmButton,
            cancelAccessibilityHint: "Double tap to continue the test",
            cancelAccessibilityIdentifier: AccessibilityIdentifiers.GuestTestContainerView.exitCancelButton,
            modalAccessibilityIdentifier: AccessibilityIdentifiers.GuestTestContainerView.exitConfirmationModal,
            onConfirm: {
                viewModel.cancelExit()
                onExit()
            },
            onCancel: { viewModel.cancelExit() }
        )
    }

    private func handleTimerExpiration() {
        guard !isAutoSubmitting else { return }
        isAutoSubmitting = true

        viewModel.lockAnswers()

        if viewModel.answeredCount > 0 {
            viewModel.presentTimeExpiredAlert()
        }

        Task {
            await viewModel.submitTestForTimeout()

            if viewModel.wasAbandonedSilently {
                onExit()
            }
        }
    }
}
