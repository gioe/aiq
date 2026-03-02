import SwiftUI

/// Dashboard/Home view showing user stats and test availability
struct DashboardView: View {
    @StateObject private var viewModel: DashboardViewModel
    private let authManager: any AuthManagerProtocol
    @EnvironmentObject var router: AppRouter

    /// Whether user skipped onboarding (determines if info card should show)
    @AppStorage("didSkipOnboarding") private var didSkipOnboarding: Bool = false

    /// Whether user has dismissed the onboarding info card
    @AppStorage("hasDismissedOnboardingInfoCard") private var hasDismissedOnboardingInfoCard: Bool = false

    /// Controls animation state for info card dismissal
    @State private var showOnboardingInfoCard: Bool = true

    /// Controls presentation of the onboarding flow
    @State private var showOnboarding: Bool = false

    /// Creates a DashboardView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeDashboardViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
        guard let resolved = serviceContainer.resolve(AuthManagerProtocol.self) else {
            fatalError("AuthManagerProtocol not registered in ServiceContainer")
        }
        authManager = resolved
    }

    var body: some View {
        ZStack {
            // Modern gradient background
            LinearGradient(
                gradient: Gradient(colors: [
                    ColorPalette.background,
                    ColorPalette.backgroundSecondary.opacity(0.3)
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            if viewModel.isLoading && !viewModel.hasTests {
                LoadingView(message: "Loading dashboard...")
            } else if viewModel.error != nil {
                ErrorView(
                    error: viewModel.error!,
                    retryAction: {
                        Task {
                            await viewModel.retry()
                        }
                    }
                )
            } else if viewModel.hasTests {
                dashboardContent
            } else {
                emptyState
            }
        }
        .navigationTitle("Dashboard")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await viewModel.fetchDashboardData()
        }
        .fullScreenCover(isPresented: $showOnboarding) {
            OnboardingContainerView()
        }
        .onReceive(NotificationCenter.default.publisher(for: .refreshCurrentView)) { _ in
            Task {
                await viewModel.refreshDashboard()
            }
        }
    }

    // MARK: - Dashboard Content

    private var dashboardContent: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                // Welcome Header
                DashboardWelcomeHeader(userName: authManager.userFullName)

                // Onboarding Skipped Info Card
                onboardingInfoCardSection

                // In-Progress Test Card
                if let activeSession = viewModel.activeTestSession {
                    InProgressTestCard(
                        session: activeSession,
                        questionsAnswered: viewModel.activeSessionQuestionsAnswered,
                        onResume: {
                            viewModel.trackTestResumed()
                            // Resume always uses fixed-form TestTakingView
                            router.push(.testTaking())
                        },
                        onAbandon: {
                            await viewModel.abandonActiveTest()
                        }
                    )
                    .inProgressCardTransition(sessionId: viewModel.activeTestSession?.id)
                }

                // Stats Grid
                statsGrid

                // Latest Test Result
                if let latest = viewModel.latestTestResult {
                    DashboardLatestTestResultCard(result: latest, dateFormatted: viewModel.latestTestDateFormatted)
                        .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.latestTestCard)
                }

                // Action Button
                DashboardActionButton(hasActiveTest: viewModel.hasActiveTest, onTap: navigateToTest)

                Spacer()
            }
            .padding(DesignSystem.Spacing.lg)
            .adaptiveContentWidth()
        }
        .refreshable {
            await viewModel.refreshDashboard()
        }
    }

    // MARK: - Onboarding Info Card

    /// Whether the onboarding info card should be displayed
    private var shouldShowOnboardingInfoCard: Bool {
        didSkipOnboarding && !hasDismissedOnboardingInfoCard && showOnboardingInfoCard
    }

    /// Info card section for users who skipped onboarding
    @ViewBuilder
    private var onboardingInfoCardSection: some View {
        if shouldShowOnboardingInfoCard {
            OnboardingSkippedInfoCard(
                onLearnMore: {
                    // Opening onboarding counts as addressing the skip, even if
                    // user dismisses partway through. Card won't reappear.
                    hasDismissedOnboardingInfoCard = true
                    didSkipOnboarding = false
                    showOnboarding = true
                },
                onDismiss: {
                    dismissOnboardingInfoCard()
                }
            )
            .transition(.asymmetric(
                insertion: .opacity,
                removal: .scale(scale: 0.95).combined(with: .opacity)
            ))
        }
    }

    /// Dismisses the onboarding info card with animation
    private func dismissOnboardingInfoCard() {
        // Persist dismissal immediately to avoid race conditions with app backgrounding
        hasDismissedOnboardingInfoCard = true
        withAnimation(DesignSystem.Animation.quick) {
            showOnboardingInfoCard = false
        }
    }

    // MARK: - Stats Grid

    private var statsGrid: some View {
        HStack(spacing: DesignSystem.Spacing.lg) {
            StatCard(
                label: "Tests Taken",
                value: "\(viewModel.testCount)",
                icon: "list.clipboard.fill",
                color: ColorPalette.statBlue,
                accessibilityId: AccessibilityIdentifiers.DashboardView.testsTakenStat
            )

            if let avgScore = viewModel.averageScore {
                StatCard(
                    label: "Average IQ",
                    value: "\(avgScore)",
                    icon: "chart.line.uptrend.xyaxis",
                    color: ColorPalette.statGreen,
                    accessibilityId: AccessibilityIdentifiers.DashboardView.averageIQStat
                )
            }
        }
    }

    // MARK: - Routing Helpers

    /// Determines the correct test route based on active session and feature flags
    /// - Returns: Resume always routes to fixed-form test; new tests respect adaptive testing flag
    private func navigateToTest() {
        if viewModel.hasActiveTest {
            router.push(.testTaking())
        } else if Constants.Features.adaptiveTesting {
            router.push(.adaptiveTestTaking)
        } else {
            router.push(.testTaking())
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                DashboardWelcomeHeader(userName: authManager.userFullName)

                // Onboarding Skipped Info Card
                onboardingInfoCardSection

                // In-Progress Test Card for empty state
                if let activeSession = viewModel.activeTestSession {
                    InProgressTestCard(
                        session: activeSession,
                        questionsAnswered: viewModel.activeSessionQuestionsAnswered,
                        onResume: {
                            // Resume always uses fixed-form TestTakingView
                            router.push(.testTaking())
                        },
                        onAbandon: {
                            await viewModel.abandonActiveTest()
                        }
                    )
                    .inProgressCardTransition(sessionId: viewModel.activeTestSession?.id)
                }

                EmptyStateView(
                    icon: viewModel.hasActiveTest ? "play.circle.fill" : "brain.head.profile",
                    title: viewModel.hasActiveTest ? "Test in Progress" : "Ready to Begin?",
                    message: viewModel.hasActiveTest ?
                        "You have a test in progress. Resume it to continue or complete it to see your results." :
                        """
                        Take your first cognitive performance assessment to establish your baseline score. \
                        Track your progress over time and discover insights about your performance.
                        """,
                    actionTitle: viewModel.hasActiveTest ? "Resume Test in Progress" : "Start Your First Test",
                    action: {
                        navigateToTest()
                    }
                )
                .padding(.vertical, DesignSystem.Spacing.xl)

                Spacer()
            }
            .padding(DesignSystem.Spacing.lg)
            .adaptiveContentWidth()
        }
        .refreshable {
            await viewModel.refreshDashboard()
        }
    }
}

// MARK: - View Modifiers

/// View modifier for applying consistent transition and animation to InProgressTestCard
private struct InProgressCardTransition: ViewModifier {
    let sessionId: Int?
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    func body(content: Content) -> some View {
        if reduceMotion {
            content
                .transition(.opacity)
                .animation(nil, value: sessionId)
        } else {
            content
                .transition(.asymmetric(
                    insertion: .scale(scale: 0.9).combined(with: .opacity),
                    removal: .scale(scale: 0.9).combined(with: .opacity)
                ))
                .animation(.spring(response: 0.4, dampingFraction: 0.8), value: sessionId)
        }
    }
}

private extension View {
    func inProgressCardTransition(sessionId: Int?) -> some View {
        modifier(InProgressCardTransition(sessionId: sessionId))
    }
}

#Preview {
    NavigationStack {
        DashboardView()
    }
}
